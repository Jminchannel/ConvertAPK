import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


class RepositoryStructureTests(unittest.TestCase):
    def test_tracked_source_roots_are_grouped_and_generated_roots_are_absent(self):
        expected_directories = (
            "apps/web/frontend",
            "apps/web/backend",
            "apps/desktop-electron",
            "workers/apk-worker",
            "templates/android/HTML2APK",
            "templates/android/Tubbim",
        )
        for relative_path in expected_directories:
            with self.subTest(relative_path=relative_path):
                self.assertTrue((ROOT_DIR / relative_path).is_dir())

        removed_directories = (
            "build",
            "dist",
            ".idea",
            "build-worker-docker",
            "apps/desktop-electron/build",
            "apps/desktop-electron/dist",
        )
        for relative_path in removed_directories:
            with self.subTest(relative_path=relative_path):
                self.assertFalse((ROOT_DIR / relative_path).exists())


if __name__ == "__main__":
    unittest.main()
