import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from backend import main


class HealthEndpointTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_unknown_route_returns_404(self) -> None:
        with TestClient(main.app) as client:
            response = client.get("/does-not-exist")

        self.assertEqual(response.status_code, 404)


class DevelopmentCorsTests(unittest.TestCase):
    origin = "http://127.0.0.1:8000"

    def client(self, origins: str | None) -> TestClient:
        with patch.dict(os.environ):
            os.environ.pop("SORT_TEST_DEV_ORIGINS", None)
            if origins is not None:
                os.environ["SORT_TEST_DEV_ORIGINS"] = origins
            return TestClient(main.create_app())

    def test_unset_origins_does_not_authorize_cross_origin_reading(self) -> None:
        with self.client(None) as client:
            response = client.get("/health", headers={"Origin": self.origin})
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_exact_origin_is_authorized_without_credentials(self) -> None:
        with self.client(self.origin) as client:
            response = client.get("/health", headers={"Origin": self.origin})
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
        self.assertNotIn("access-control-allow-credentials", response.headers)

    def test_other_origins_are_not_authorized(self) -> None:
        with self.client(self.origin) as client:
            for origin in ("http://localhost:8000", "http://127.0.0.1:8001", "https://example.com"):
                with self.subTest(origin=origin):
                    response = client.get("/health", headers={"Origin": origin})
                    self.assertNotIn("access-control-allow-origin", response.headers)

    def test_allowed_get_preflight(self) -> None:
        with self.client(self.origin) as client:
            response = client.options("/health", headers={
                "Origin": self.origin, "Access-Control-Request-Method": "GET",
            })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["access-control-allow-origin"], self.origin)
        self.assertEqual(response.headers["access-control-allow-methods"], "GET")
        self.assertNotIn("access-control-allow-credentials", response.headers)

    def test_preflight_denies_other_origin_and_method(self) -> None:
        with self.client(self.origin) as client:
            for origin, method in (("https://example.com", "GET"), (self.origin, "POST")):
                with self.subTest(origin=origin, method=method):
                    response = client.options("/health", headers={
                        "Origin": origin, "Access-Control-Request-Method": method,
                    })
                    self.assertEqual(response.status_code, 400)

    def test_configuration_trims_comma_separated_origins(self) -> None:
        with self.client(f" {self.origin} , http://localhost:8000 ") as client:
            response = client.get("/health", headers={"Origin": "http://localhost:8000"})
        self.assertEqual(response.headers["access-control-allow-origin"], "http://localhost:8000")

    def test_blank_configuration_disables_cross_origin_reading(self) -> None:
        with self.client("   ") as client:
            response = client.get("/health", headers={"Origin": self.origin})
        self.assertNotIn("access-control-allow-origin", response.headers)

    def test_invalid_configuration_fails_at_app_creation(self) -> None:
        for origins in ("*", "https://*.example.com", "null", "127.0.0.1:8000",
                        "http://127.0.0.1:8000/path", "http://127.0.0.1:8000/",
                        "http://user:password@localhost:8000", "http://localhost:99999",
                        "http://localhost:8000?x=1", "http://localhost:8000#fragment",
                        f"{self.origin},", "http://local host:8000", "file://localhost"):
            with self.subTest(origins=origins), self.assertRaises(ValueError):
                self.client(origins)


if __name__ == "__main__":
    unittest.main()
