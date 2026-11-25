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
        for path in ("/src/app.js", "/src/auth.js", "/assets/nunito-variable.ttf", "/assets/home-podium.jpg"):
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
            "/infra/azure/app.Dockerfile",
            "/mockups/friendly-study.html",
            "/tools/export_ranked_v1.py",
            "/src/../backend/main.py",
            "/src/%2e%2e/backend/main.py",
            "/assets/../.git/config",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_api_routes_still_answer(self) -> None:
        # this test is about routing, not the body; the version joined that
        # body in #274 and has its own checks in test_version.py
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        # an /api path that does not exist stays a JSON 404, not the home page
        response = self.client.get("/api/does-not-exist")
        self.assertEqual(response.status_code, 404)
        self.assertNotIn("text/html", response.headers.get("content-type", ""))


if __name__ == "__main__":
    unittest.main()


class StaticCachingTests(unittest.TestCase):
    """#462: a deploy has to reach a phone that already has the app open.

    Before this, src/ and assets/ went out with an ETag and no
    Cache-Control, so each browser invented a freshness window of its own.
    The home page said "ask me first"; the code behind it said nothing,
    and a returning browser could keep running modules from weeks earlier.
    """

    def setUp(self) -> None:
        self.client = TestClient(main.create_app())

    def test_every_served_file_asks_before_reusing_it(self) -> None:
        for path in (
            "/",
            "/src/app.js",
            "/src/auth.js",
            "/src/chart.js",
            "/assets/nunito-variable.ttf",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.headers.get("cache-control"), "no-cache")

    def test_an_unchanged_file_still_costs_nothing(self) -> None:
        # `no-cache` is not `no-store`: the browser keeps the copy and the
        # ETag turns the second request into a 304 with no body. If this
        # stops holding, the fix above has become a download on every
        # page view, on phones in a warehouse.
        first = self.client.get("/src/app.js")
        etag = first.headers["etag"]
        again = self.client.get("/src/app.js", headers={"if-none-match": etag})
        self.assertEqual(again.status_code, 304)
        self.assertEqual(again.content, b"")

    def test_a_changed_file_is_sent_again(self) -> None:
        # The whole point: a new build has a new ETag, so the conditional
        # request misses and the browser gets the new bytes.
        response = self.client.get(
            "/src/app.js", headers={"if-none-match": '"not-the-current-file"'}
        )
        self.assertEqual(response.status_code, 200)
        self.assertGreater(len(response.content), 0)

    def test_the_version_tag_in_the_url_no_longer_decides_freshness(self) -> None:
        # The old design. Asking for the same file under a stale tag, a
        # current tag and no tag must give the same answer and the same
        # instruction -- the URL is not what keeps it fresh any more.
        answers = [
            self.client.get(path)
            for path in (
                "/src/app.js",
                "/src/app.js?v=readcache-20261121",
                "/src/app.js?v=anything-at-all",
            )
        ]
        for response in answers:
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.headers.get("cache-control"), "no-cache")
        self.assertEqual(len({response.content for response in answers}), 1)
