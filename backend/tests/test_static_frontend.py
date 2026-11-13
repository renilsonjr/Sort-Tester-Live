import unittest

from fastapi.testclient import TestClient

from backend import main


class StaticFrontendTests(unittest.TestCase):
    """The FastAPI app serves the reviewed frontend on the same origin as /api."""

    def setUp(self) -> None:
        self.client = TestClient(main.create_app())

    def test_home_page_is_index_html(self) -> None:
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        self.assertIn('src="src/app.js', response.text)

    def test_allowed_frontend_files_are_served(self) -> None:
        for path in ("/src/app.js", "/src/auth.js", "/assets/nunito-variable.ttf", "/assets/quiz-happy.jpg"):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 200)

    def test_javascript_modules_have_a_javascript_type(self) -> None:
        response = self.client.get("/src/app.js")
        self.assertIn("javascript", response.headers["content-type"])

    def test_files_outside_the_allowlist_are_not_served(self) -> None:
        for path in (
            "/index.html/../backend/main.py",
            "/backend/main.py",
            "/.git/config",
            "/.gitignore",
            "/README.md",
            "/dev/config.local.json",
            "/dev/index.html",
            "/tests/security.test.mjs",
            "/docs/security/2026-11-06-static-review.md",
            "/infra/azure/spike.Dockerfile",
            "/mockups/friendly-study.html",
            "/tools/export_ranked_v1.py",
            "/src/../backend/main.py",
            "/src/%2e%2e/backend/main.py",
            "/assets/../.git/config",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_api_routes_still_answer(self) -> None:
        self.assertEqual(self.client.get("/health").json(), {"status": "ok"})
        # an /api path that does not exist stays a JSON 404, not the home page
        response = self.client.get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()
