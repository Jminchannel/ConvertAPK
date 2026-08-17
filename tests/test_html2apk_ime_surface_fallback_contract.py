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


class Html2ApkImeSurfaceFallbackContractTests(unittest.TestCase):
    def test_webview_installs_a_temporary_surface_background_fallback_for_ime_resize(self):
        activity = ACTIVITY_FILE.read_text(encoding="utf-8")

        self.assertIn("view.evaluateJavascript(INJECT_IME_SURFACE_FALLBACK, null)", activity)
        self.assertIn("window.__convertApkImeSurfaceFallback", activity)
        self.assertIn("focusin", activity)
        self.assertIn("focusout", activity)
        self.assertIn("backgroundImage", activity)


if __name__ == "__main__":
    unittest.main()
