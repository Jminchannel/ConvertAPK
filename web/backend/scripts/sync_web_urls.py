import json
import os
from datetime import datetime
from pathlib import Path

from admin_client import check_admin_service, report_task_start
from builder import TASKS_DIR


def _load_tasks(path: Path) -> list[dict]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def main() -> None:
    ok, reason = check_admin_service()
    if not ok:
        print(f"[sync] admin service unavailable: {reason}")
        return

    tasks_path = TASKS_DIR / "tasks.json"
    if not tasks_path.exists():
        print(f"[sync] tasks not found: {tasks_path}")
        return

    dry_run = os.getenv("CONVERTAPK_SYNC_WEB_URLS_DRY_RUN", "").strip() == "1"
    tasks = _load_tasks(tasks_path)
    synced = 0
    skipped = 0

    for item in tasks:
        if not isinstance(item, dict):
            skipped += 1
            continue
        if (item.get("mode") or "").lower() != "web":
            skipped += 1
            continue
        web_url = str(item.get("web_url") or "").strip()
        if not web_url:
            skipped += 1
            continue
        task_id = str(item.get("id") or item.get("task_id") or "").strip()
        if not task_id:
            skipped += 1
            continue
        config = item.get("config") if isinstance(item.get("config"), dict) else {}
        config = dict(config or {})
        config["web_url"] = web_url
        start_time = item.get("updated_at") or item.get("created_at") or datetime.utcnow().isoformat()
        if not dry_run:
            report_task_start(task_id, str(item.get("client_id") or ""), start_time, {}, config)
        synced += 1

    mode = "dry-run" if dry_run else "done"
    print(f"[sync] {mode}: synced={synced}, skipped={skipped}, path={tasks_path}")


if __name__ == "__main__":
    main()
