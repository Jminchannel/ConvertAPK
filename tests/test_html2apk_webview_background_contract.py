from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
ACTIVITY_FILE = (
    REPOSITORY_ROOT
    / "templates"
    / "android"
    / "HTML2APK"
    / "app"
    / "src"
    / "main"
    / "java"
    / "osa"
    / "cosa"
    / "html2apk"
    / "MainActivity.kt"
)


class Html2ApkWebViewBackgroundContractTests(unittest.TestCase):
    def test_webview_does_not_use_the_default_opaque_background_during_ime_resize(self):
        activity = ACTIVITY_FILE.read_text(encoding="utf-8")

        self.assertIn("setBackgroundColor(android.graphics.Color.TRANSPARENT)", activity)


if __name__ == "__main__":
    unittest.main()
