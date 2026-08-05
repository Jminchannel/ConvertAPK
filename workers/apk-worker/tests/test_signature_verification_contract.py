import re
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT_DIR / "apk-worker" / "scripts" / "build.sh"


class SignatureVerificationContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUILD_SCRIPT.read_text(encoding="utf-8")

    def test_aab_verification_is_not_verbose_per_entry(self):
        self.assertNotIn("jarsigner -verify -verbose -certs", self.source)
        self.assertRegex(
            self.source,
            r"runSignatureVerification\s+\"AAB[^\"]*\"\s+jarsigner\s+-verify\s+\"\$SIGNED_AAB\"",
        )

    def test_signature_verification_has_timeout_guard(self):
        self.assertIn("SIGNATURE_VERIFY_TIMEOUT_SECONDS", self.source)
        self.assertRegex(
            self.source,
            r"timeout\s+\"\$SIGNATURE_VERIFY_TIMEOUT_SECONDS\"",
        )

    def test_apk_verification_uses_same_timeout_wrapper(self):
        self.assertRegex(
            self.source,
            r"runSignatureVerification\s+\"APK[^\"]*\"\s+apksigner\s+verify\s+\"\$SIGNED_APK\"",
        )
        self.assertIsNone(
            re.search(r"^\s*apksigner\s+verify\s+--verbose\s+\"\$SIGNED_APK\"", self.source, re.MULTILINE)
        )


if __name__ == "__main__":
    unittest.main()
