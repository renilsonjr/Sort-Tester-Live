"""Cross-site writes are rejected before they reach a route (issue #77).

These tests need no database: the guard answers before routing, and an
allowed request is proved by it reaching FastAPI's own 422 for a body
the route rejects.
"""
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main

# TestClient sends Host: testserver for this base URL.
SAME_ORIGIN = "http://testserver"
WRITE_PATHS = (
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/logout",
    "/api/auth/account/delete",
    "/api/auth/admin/regenerate",
    "/api/ranked/attempts",
    "/api/ranked/attempts/abc/answer",
    "/api/ranked/attempts/abc/quit",
    "/api/ranked/season/launch",
)


def client(dev_origins=None, app_origin=None):
    environment = {}
    if dev_origins is not None:
        environment["SORT_TEST_DEV_ORIGINS"] = dev_origins
    if app_origin is not None:
        environment["SORT_TESTER_APP_ORIGIN"] = app_origin
    with patch.dict(os.environ, environment, clear=True):
        # An allowed write reaches a route that wants the database, which is
        # not configured here; let that surface as a response, not a raise.
        return TestClient(main.create_app(), raise_server_exceptions=False)


class RejectedWritesTests(unittest.TestCase):
    def setUp(self):
        self.client = client()

    def test_foreign_origin_is_rejected_on_every_write_path(self):
        for path in WRITE_PATHS:
            with self.subTest(path=path):
                response = self.client.post(path, json={}, headers={"Origin": "https://evil.example"})
                self.assertEqual(response.status_code, 403)

    def test_no_origin_and_no_referer_is_rejected(self):
        self.assertEqual(self.client.post("/api/auth/login", json={}).status_code, 403)

    def test_foreign_referer_is_rejected_when_origin_is_absent(self):
        response = self.client.post(
            "/api/auth/login", json={}, headers={"Referer": "https://evil.example/page"}
        )
        self.assertEqual(response.status_code, 403)

    def test_lookalike_origins_are_rejected(self):
        for origin in (
            "http://testserver.evil.example",
            "http://evil.example/testserver",
            "http://nottestserver",
            "http://testserver:9999",
            "null",
        ):
            with self.subTest(origin=origin):
                response = self.client.post("/api/auth/login", json={}, headers={"Origin": origin})
                self.assertEqual(response.status_code, 403)

    def test_other_write_methods_are_guarded(self):
        foreign = {"Origin": "https://evil.example"}
        for method in ("put", "patch", "delete"):
            with self.subTest(method=method):
                response = getattr(self.client, method)("/api/ranked/attempts", headers=foreign)
                self.assertEqual(response.status_code, 403)

    def test_refusal_body_is_generic(self):
        response = self.client.post("/api/auth/login", json={}, headers={"Origin": "https://evil.example"})
        body = response.text.lower()
        self.assertNotIn("evil.example", body)
        self.assertNotIn("testserver", body)


class AllowedRequestsTests(unittest.TestCase):
    """An allowed write reaches the route, so it is anything but a 403."""

    def assertAllowed(self, response):
        self.assertNotEqual(response.status_code, 403, response.text)

    def test_same_origin_write_is_allowed(self):
        self.assertAllowed(
            client().post("/api/auth/login", json={}, headers={"Origin": SAME_ORIGIN})
        )

    def test_same_origin_referer_is_allowed_when_origin_is_absent(self):
        self.assertAllowed(
            client().post("/api/auth/login", json={}, headers={"Referer": f"{SAME_ORIGIN}/index.html"})
        )

    def test_https_origin_behind_a_proxy_is_allowed(self):
        # The ingress terminates TLS, so the browser sends an https Origin
        # while the app sees a plain http request for the same host.
        self.assertAllowed(
            client().post("/api/auth/login", json={}, headers={"Origin": "https://testserver"})
        )

    def test_configured_development_origin_is_allowed(self):
        self.assertAllowed(
            client(dev_origins="http://127.0.0.1:8000").post(
                "/api/auth/login", json={}, headers={"Origin": "http://127.0.0.1:8000"}
            )
        )

    def test_configured_app_origin_is_allowed(self):
        self.assertAllowed(
            client(app_origin="https://sortlab.example.com").post(
                "/api/auth/login", json={}, headers={"Origin": "https://sortlab.example.com"}
            )
        )

    def test_configuring_an_app_origin_does_not_allow_other_origins(self):
        response = client(app_origin="https://sortlab.example.com").post(
            "/api/auth/login", json={}, headers={"Origin": "https://evil.example"}
        )
        self.assertEqual(response.status_code, 403)

    def test_reads_are_never_blocked(self):
        foreign = {"Origin": "https://evil.example"}
        for path in ("/health", "/", "/src/auth.js"):
            with self.subTest(path=path):
                self.assertAllowed(client().get(path, headers=foreign))

    def test_preflight_is_not_blocked(self):
        self.assertAllowed(
            client(dev_origins="http://127.0.0.1:8000").options(
                "/api/auth/login",
                headers={
                    "Origin": "http://127.0.0.1:8000",
                    "Access-Control-Request-Method": "POST",
                },
            )
        )


if __name__ == "__main__":
    unittest.main()
