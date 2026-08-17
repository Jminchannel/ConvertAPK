import sys
import tempfile
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.domain.models import AppConfig
from app.services.local_builder import _patch_android_manifest


class KeyboardResizeContractTests(unittest.TestCase):
    def test_app_config_serializes_keyboard_resize(self):
        config = AppConfig(app_name="Keyboard Test", package_name="com.example.keyboard", keyboard_resize=True)

        self.assertTrue(config.keyboard_resize)
        self.assertTrue(config.model_dump()["keyboard_resize"])

    def test_manifest_enables_adjust_resize_on_launcher_activity(self):
        manifestText = """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <application>
        <activity android:name=".MainActivity" android:screenOrientation="portrait">
            <intent-filter>
                <action android:name="android.intent.action.MAIN" />
                <category android:name="android.intent.category.LAUNCHER" />
            </intent-filter>
        </activity>
    </application>
</manifest>"""

        with tempfile.TemporaryDirectory() as tempDir:
            manifestPath = Path(tempDir) / "AndroidManifest.xml"
            manifestPath.write_text(manifestText, encoding="utf-8")
            _patch_android_manifest(manifestPath, "portrait", [], keyboard_resize=True)
            updatedManifest = manifestPath.read_text(encoding="utf-8")

        self.assertIn('android:windowSoftInputMode="adjustResize"', updatedManifest)

    def test_builders_receive_keyboard_resize_environment_contract(self):
        projectRoot = BACKEND_DIR.parents[2]
        builderSource = (BACKEND_DIR / "app/services/builder.py").read_text(encoding="utf-8")
        localBuilderSource = (BACKEND_DIR / "app/services/local_builder.py").read_text(encoding="utf-8")
        dockerBuilderSource = (projectRoot / "workers/apk-worker/scripts/build.sh").read_text(encoding="utf-8")

        self.assertIn('"KEYBOARD_RESIZE": "true" if keyboard_resize else "false"', builderSource)
        self.assertIn("KEYBOARD_RESIZE", localBuilderSource)
        self.assertIn("KEYBOARD_RESIZE", dockerBuilderSource)
        self.assertIn("adjustResize", dockerBuilderSource)


if __name__ == "__main__":
    unittest.main()
