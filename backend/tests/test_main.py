import unittest

from fastapi.testclient import TestClient

from backend.main import app


class HealthEndpointTests(unittest.TestCase):
    def test_health_returns_ok(self) -> None:
        with TestClient(app) as client:
            response = client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_unknown_route_returns_404(self) -> None:
        with TestClient(app) as client:
            response = client.get("/does-not-exist")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
