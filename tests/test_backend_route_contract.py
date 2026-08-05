import sys
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
BACKEND_DIR = ROOT_DIR / "apps" / "web" / "backend"

if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.main import app


EXPECTED_ROUTES = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/upload"),
    ("POST", "/api/tasks"),
    ("GET", "/api/tasks"),
    ("POST", "/api/tasks/{task_id}/start"),
    ("GET", "/api/tasks/{task_id}/logs"),
    ("GET", "/api/download/{task_id}"),
    ("GET", "/api/queue/status"),
    ("GET", "/api/adminhub/features"),
}


class BackendRouteContractTests(unittest.TestCase):
    def test_published_routes_remain_registered(self):
        actual_routes = {
            (method, route.path)
            for route in app.routes
            for method in getattr(route, "methods", set())
        }
        self.assertTrue(EXPECTED_ROUTES <= actual_routes)
        self.assertIn(("GET", "/{path:path}"), actual_routes)

    def test_operations_routes_are_registered_outside_application_entry(self):
        source = (BACKEND_DIR / "app" / "main.py").read_text(encoding="utf-8")
        self.assertIn("register_operations_routes(", source)
        self.assertNotIn('@app.get("/api/queue/status")', source)


if __name__ == "__main__":
    unittest.main()
