"""Pool/token unavailability surfaces as a clean 503, with no secret (#84)."""
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from backend.db import entra_token
from backend.main import create_app


class DbUnavailable503Tests(unittest.TestCase):
    def _client(self):
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_pool_timeout_becomes_503(self):
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=PoolTimeout("no conn")):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "database temporarily unavailable")

    def test_token_unavailable_becomes_503_without_secret(self):
        err = entra_token.TokenUnavailable("could not obtain an Entra token for the database")
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=err):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("token", response.text.lower())
