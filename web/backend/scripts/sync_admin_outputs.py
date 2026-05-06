import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from admin_client import upload_task_assets
from builder import TASKS_DIR


TASKS_STATE_PATH = TASKS_DIR / "tasks.json"


def _load_tasks() -> list[dict]:
    if not TASKS_STATE_PATH.exists():
        return []
    try:
        data = json.loads(TASKS_STATE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []
    return data if isinstance(data, list) else []


def sync_outputs() -> None:
    tasks = _load_tasks()
    total = 0
    synced = 0
    skipped = 0
    for item in tasks:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status", "")).lower()
        if status != "success":
            continue
        task_id = str(item.get("id", ""))
        if not task_id:
            skipped += 1
            continue
        zip_path = TASKS_DIR / task_id / "input" / "project.zip"
        icon_path = TASKS_DIR / task_id / "input" / "logo.png"
        if not zip_path.exists():
            skipped += 1
            continue
        zip_info = {"name": zip_path.name}
        try:
            zip_info["size"] = zip_path.stat().st_size
        except Exception:
            pass
        total += 1
        ok = upload_task_assets(
            task_id=task_id,
            client_id=str(item.get("client_id", "")),
            start_time=str(item.get("updated_at") or item.get("created_at") or ""),
            zip_info=zip_info,
            app_config=item.get("config") or {},
            zip_path=str(zip_path),
            icon_path=str(icon_path) if icon_path.exists() else None,
            _allow_queue=False,
        )
        if ok:
            synced += 1
        else:
            skipped += 1

    print(f"[sync_admin_outputs] total={total} synced={synced} skipped={skipped}")


if __name__ == "__main__":
    sync_outputs()
