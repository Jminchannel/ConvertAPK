from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_ROOT = REPOSITORY_ROOT / "templates" / "android" / "HTML2APK"


class Html2ApkKeyboardInsetsContractTests(unittest.TestCase):
    def test_webview_template_resizes_for_the_software_keyboard(self):
        manifest = (TEMPLATE_ROOT / "app" / "src" / "main" / "AndroidManifest.xml").read_text(encoding="utf-8")
        activity = (
            TEMPLATE_ROOT
            / "app"
            / "src"
            / "main"
            / "java"
            / "osa"
            / "cosa"
            / "html2apk"
            / "MainActivity.kt"
        ).read_text(encoding="utf-8")

        self.assertIn('android:windowSoftInputMode="adjustResize"', manifest)
        self.assertIn("import androidx.compose.foundation.layout.imePadding", activity)
        self.assertIn(".imePadding(),", activity)


if __name__ == "__main__":
    unittest.main()
