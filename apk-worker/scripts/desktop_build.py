import os
import sys
import traceback
from pathlib import Path

from local_builder import run_local_build


def log(message: str) -> None:
    print(message, flush=True)


def main() -> int:
    env = dict(os.environ)
    env.setdefault("TASK_MODE", "desktop")
    env.setdefault("OUTPUT_FORMAT", "exe")
    env.setdefault("DESKTOP_INSTALLER_MODE", "portable")
    env.setdefault("TASK_INPUT_DIR", env.get("INPUT_DIR", "/workspace/input"))
    env.setdefault("TASK_OUTPUT_DIR", env.get("OUTPUT_DIR", "/workspace/output"))
    env.setdefault("TASK_KEYSTORE_DIR", env.get("KEYSTORE_DIR", "/workspace/keystore"))

    task_output_dir = Path(env["TASK_OUTPUT_DIR"])
    task_output_dir.mkdir(parents=True, exist_ok=True)

    result = run_local_build(
        env=env,
        task_output_dir=task_output_dir,
        on_log=log,
    )
    output_file = str(result.get("output_file") or "").strip()
    if not output_file:
        raise RuntimeError("Electron build completed but output file was not returned")

    print(f"[DesktopBuilder] output: {output_file}", flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:
        print(f"[DesktopBuilder] error: {exc}", file=sys.stderr, flush=True)
        traceback.print_exc()
        raise SystemExit(1)
