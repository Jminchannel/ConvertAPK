import json
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main
from app.domain.models import AppConfig, BuildStatus, BuildTask, BuildTaskCreate


class RuntimeSafetyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)

        self.original_tasks_db = dict(main.tasks_db)
        main.tasks_db.clear()
        self.addCleanup(self._restore_tasks_db)

        self.original_tasks_state_path = main.TASKS_STATE_PATH
        main.TASKS_STATE_PATH = Path(self.temp_dir.name) / "tasks.json"
        self.addCleanup(lambda: setattr(main, "TASKS_STATE_PATH", self.original_tasks_state_path))

    def _restore_tasks_db(self):
        main.tasks_db.clear()
        main.tasks_db.update(self.original_tasks_db)

    def _build_config(self):
        return AppConfig(app_name="Runtime Safety", package_name="com.example.runtime")

    def test_persist_tasks_db_serializes_nested_datetimes(self):
        now = datetime(2026, 7, 6, 9, 30, 0)
        task = BuildTask(
            id="task-1",
            client_id="client-1",
            config=self._build_config(),
            status=BuildStatus.PENDING,
            created_at=now,
            updated_at=now,
            output_expires_at=now,
            desktop_output_expires_at=now,
            risk_scan={"checked_at": now, "items": [{"seen_at": now}]},
            review_requested_at=now,
            review_decision_at=now,
        )
        main.tasks_db[task.id] = task

        main.persist_tasks_db(force=True)

        payload = json.loads(main.TASKS_STATE_PATH.read_text(encoding="utf-8"))
        saved = payload[0]
        self.assertEqual(saved["output_expires_at"], now.isoformat())
        self.assertEqual(saved["desktop_output_expires_at"], now.isoformat())
        self.assertEqual(saved["review_requested_at"], now.isoformat())
        self.assertEqual(saved["review_decision_at"], now.isoformat())
        self.assertEqual(saved["risk_scan"]["checked_at"], now.isoformat())
        self.assertEqual(saved["risk_scan"]["items"][0]["seen_at"], now.isoformat())

    async def test_create_task_does_not_wait_for_admin_asset_sync(self):
        started = threading.Event()
        release = threading.Event()

        def slow_sync(*args, **kwargs):
            started.set()
            release.wait(timeout=2)

        task_data = BuildTaskCreate(
            client_id="client-1",
            mode="web",
            web_url="https://example.com",
            compliance_ack=True,
            declared_use_case="runtime safety test",
            config=self._build_config(),
        )

        with patch.object(main, "_validate_task_compliance_or_raise", return_value=None), \
            patch.object(main, "_is_web_link_mode_enabled", return_value=True), \
            patch.object(main, "_enforce_marketplace_policy_or_raise", return_value=None), \
            patch.object(main, "_scan_task_risk_inputs", return_value={"risk_level": "normal", "hit_count": 0}), \
            patch.object(main, "_resolve_shared_ai_runtime_config", return_value={"enabled": False}), \
            patch.object(main, "_apply_ai_diag_cooldown_to_runtime_config", side_effect=lambda client_id, config, scope: (config, 0)), \
            patch.object(main, "_run_ai_marketplace_guard_for_task", return_value={"status": "rule_only"}), \
            patch.object(main, "_requires_risk_review", return_value=False), \
            patch.object(main, "_sync_task_assets_to_admin_and_flush", side_effect=slow_sync):
            start = time.perf_counter()
            task = await main.create_task(task_data)
            elapsed = time.perf_counter() - start

        try:
            self.assertEqual(task.status, BuildStatus.PENDING)
            self.assertLess(elapsed, 0.2)
            self.assertTrue(started.wait(timeout=1))
        finally:
            release.set()


if __name__ == "__main__":
    unittest.main()
