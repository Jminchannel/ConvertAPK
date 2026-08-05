"""持续集成质量门禁的静态契约测试。"""

from pathlib import Path
import unittest


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]


class QualityWorkflowContractTests(unittest.TestCase):
    """确保仓库持续保留可执行的基础质量检查。"""

    def test_quality_workflow_checks_frontend_and_backend(self):
        workflow = REPOSITORY_ROOT / ".github" / "workflows" / "quality.yml"

        self.assertTrue(workflow.is_file(), "缺少 GitHub Actions 质量检查工作流")
        content = workflow.read_text(encoding="utf-8")

        self.assertIn("npm ci", content)
        self.assertIn("npm run check", content)
        self.assertIn("python -m unittest discover -s apps/web/backend/tests -v", content)
        self.assertIn("python -m unittest discover -s workers/apk-worker/tests -v", content)
        self.assertIn("docker compose -f docker-compose.yml config --no-interpolate", content)


if __name__ == "__main__":
    unittest.main()
