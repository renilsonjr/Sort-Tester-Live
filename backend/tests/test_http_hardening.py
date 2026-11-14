"""HTTP hardening found by the 2026-11-14 security sweep. No database needed."""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main

SAME_ORIGIN = {"Origin": "http://testserver"}


def client(**environment):
    with patch.dict(os.environ, environment, clear=True):
        return TestClient(main.create_app(), raise_server_exceptions=False)


class ApiDocumentationTests(unittest.TestCase):
    """The generated API docs list every route, owner and admin ones included."""

    def test_docs_are_not_served_by_default(self):
        for path in ("/docs", "/redoc", "/openapi.json", "/docs/oauth2-redirect"):
            with self.subTest(path=path):
                self.assertEqual(client().get(path).status_code, 404)

    def test_docs_can_be_turned_on_for_development(self):
        dev = client(SORT_TESTER_API_DOCS="1")
        for path in ("/docs", "/openapi.json"):
            with self.subTest(path=path):
                self.assertEqual(dev.get(path).status_code, 200)

    def test_only_the_exact_value_turns_them_on(self):
        for value in ("0", "true", "yes", ""):
            with self.subTest(value=value):
                self.assertEqual(client(SORT_TESTER_API_DOCS=value).get("/docs").status_code, 404)


class SecurityHeaderTests(unittest.TestCase):
    # /api/auth/me needs the database; an unknown /api path exercises the same prefix.
    PATHS = ("/", "/src/app.js", "/health", "/api/does-not-exist", "/does-not-exist")

    def test_every_response_carries_the_fixed_headers(self):
        app = client()
        for path in self.PATHS:
            with self.subTest(path=path):
                headers = app.get(path).headers
                self.assertEqual(headers["x-content-type-options"], "nosniff")
                self.assertEqual(headers["x-frame-options"], "DENY")
                self.assertEqual(headers["referrer-policy"], "same-origin")
                self.assertIn("max-age=", headers["strict-transport-security"])

    def test_refusals_carry_them_too(self):
        refused = client().post("/api/auth/login", json={}, headers={"Origin": "https://evil.example"})
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(refused.headers["x-content-type-options"], "nosniff")

    def test_content_security_policy_allows_only_what_the_page_uses(self):
        policy = client().get("/").headers["content-security-policy"]
        directives = dict(part.strip().split(" ", 1) for part in policy.split(";") if " " in part.strip())
        self.assertEqual(directives["default-src"], "'self'")
        # The one outside script is the pinned spreadsheet library.
        self.assertEqual(directives["script-src"], "'self' https://cdn.sheetjs.com")
        self.assertEqual(directives["connect-src"], "'self'")
        self.assertEqual(directives["frame-ancestors"], "'none'")
        self.assertEqual(directives["object-src"], "'none'")
        self.assertEqual(directives["base-uri"], "'self'")
        self.assertEqual(directives["form-action"], "'self'")
        for directive in ("default-src", "script-src", "connect-src"):
            self.assertNotIn("unsafe", directives[directive])
            self.assertNotIn("*", directives[directive])

    def test_api_answers_are_never_cached(self):
        app = client()
        for path in ("/api/does-not-exist", "/health"):
            with self.subTest(path=path):
                self.assertEqual(app.get(path).headers["cache-control"], "no-store")
        self.assertNotEqual(app.get("/src/app.js").headers.get("cache-control"), "no-store")

    def test_the_server_software_is_not_advertised(self):
        self.assertNotIn("uvicorn", client().get("/").headers.get("server", "").lower())


class RequestSizeTests(unittest.TestCase):
    def test_an_oversized_declared_body_is_refused_before_it_is_read(self):
        response = client().post(
            "/api/auth/register",
            content=b"x" * 10,
            headers={**SAME_ORIGIN, "Content-Type": "application/json", "Content-Length": "5000000"},
        )
        self.assertEqual(response.status_code, 413)

    def test_an_oversized_actual_body_is_refused(self):
        response = client().post(
            "/api/auth/register",
            content=b'{"username":"' + b"a" * 200_000 + b'"}',
            headers={**SAME_ORIGIN, "Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 413)

    def test_a_nonsense_length_is_refused(self):
        response = client().post(
            "/api/auth/register",
            content=b"{}",
            headers={**SAME_ORIGIN, "Content-Type": "application/json", "Content-Length": "abc"},
        )
        self.assertIn(response.status_code, (400, 413))

    def test_ordinary_requests_are_not_affected(self):
        # Without a database the route itself fails; what matters here is that
        # a small body is let through to it rather than refused.
        response = client().post("/api/auth/login", json={"login_id": "AAAA"}, headers=SAME_ORIGIN)
        self.assertNotIn(response.status_code, (400, 413))

    def test_a_body_just_under_the_cap_is_let_through(self):
        body = b'{"username":"' + b"a" * 60_000 + b'"}'
        response = client().post(
            "/api/auth/register", content=body, headers={**SAME_ORIGIN, "Content-Type": "application/json"}
        )
        self.assertNotIn(response.status_code, (400, 413))


if __name__ == "__main__":
    unittest.main()
