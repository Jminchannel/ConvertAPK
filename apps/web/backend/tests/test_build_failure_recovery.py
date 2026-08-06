import sys
import time
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.services import builder, local_builder


class BuildFailureRecoveryTests(unittest.TestCase):
    def test_persist_cooldown_starts_after_the_previous_callback_finishes(self):
        runner = object.__new__(builder.BuildTaskRunner)
        call_count = 0

        def persist_state(force):
            nonlocal call_count
            call_count += 1
            time.sleep(0.02)

        runner.on_state_change = persist_state
        runner._last_persist = 0.0
        runner._persist_interval = 0.01

        runner._notify_state_change()
        runner._notify_state_change()

        self.assertEqual(call_count, 1)

    def test_npm_registry_is_explicitly_overridden_for_build_subprocesses(self):
        process_env = {}

        local_builder._configure_npm_registry(process_env)

        self.assertEqual(process_env["npm_config_registry"], "https://registry.npmjs.org/")
        self.assertEqual(process_env["NPM_CONFIG_REGISTRY"], "https://registry.npmjs.org/")

    def test_android_worker_does_not_emit_one_line_per_apk_entry(self):
        worker_script = (
            BACKEND_DIR.parents[2] / "workers" / "apk-worker" / "scripts" / "build.sh"
        ).read_text(encoding="utf-8")

        self.assertIn('zipalign -p -f 4 "$UNSIGNED_APK" "$ALIGNED_APK"', worker_script)
        self.assertIn('zipalign -c -p 4 "$ALIGNED_APK"', worker_script)
        self.assertNotIn('zipalign -p -f -v 4 "$UNSIGNED_APK" "$ALIGNED_APK"', worker_script)
        self.assertIn('export LANG=C.UTF-8', worker_script)
        self.assertIn('export LC_ALL=C.UTF-8', worker_script)
        self.assertIn('SIGNED_APK="$OUTPUT_DIR/app-release-signed.apk"', worker_script)
        self.assertNotIn('SIGNED_APK="$OUTPUT_DIR/${APP_NAME}-v${VERSION_NAME}.apk"', worker_script)


if __name__ == "__main__":
    unittest.main()
