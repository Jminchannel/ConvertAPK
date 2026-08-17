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


class Html2ApkImeBackgroundContractTests(unittest.TestCase):
    def test_keyboard_resize_frames_have_a_dark_host_background(self):
        activity = ACTIVITY_FILE.read_text(encoding="utf-8")

        self.assertIn(
            "window.decorView.setBackgroundColor(android.graphics.Color.BLACK)",
            activity,
        )
        self.assertIn(
            "Modifier.fillMaxSize().background(ComposeColor.Black)",
            activity,
        )


if __name__ == "__main__":
    unittest.main()
