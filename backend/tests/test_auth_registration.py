"""Registration hardening (issue #47, slice 2)."""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.auth.rate_limit import _client_key
from backend.db import migrate, settings
from backend.main import create_app


class _Request:
    """The two parts of a request that _client_key reads."""

    def __init__(self, host, forwarded=None):
        self.headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
        self.client = type("Client", (), {"host": host})()


class ClientAddressTests(unittest.TestCase):
    def test_forwarded_header_is_ignored_without_a_trusted_proxy(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SORT_TEST_TRUST_PROXY", None)
            key = _client_key(_Request("10.0.0.5", forwarded="203.0.113.9"))
        self.assertEqual(key, "10.0.0.5")

    def test_forwarded_header_is_used_behind_a_trusted_proxy(self):
        with mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"}):
            key = _client_key(_Request("10.0.0.5", forwarded="203.0.113.9, 10.0.0.1"))
        self.assertEqual(key, "203.0.113.9")

    def test_no_header_uses_the_connection_address(self):
        with mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"}):
            key = _client_key(_Request("10.0.0.5"))
        self.assertEqual(key, "10.0.0.5")


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class UsernameAnswerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(self.conninfo)
        self.client = TestClient(create_app())

    def _accounts(self):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, "SELECT COUNT(*) AS n FROM accounts")["n"]
        finally:
            conn.close()

    def _register(self, username):
        return self.client.post("/api/auth/register", json={"username": username})

    def test_a_taken_username_in_any_case_is_a_conflict(self):
        self.assertEqual(self._register("Sorter_One").status_code, 200)
        taken = self._register("sorter_one")
        self.assertEqual(taken.status_code, 409)
        self.assertEqual(taken.json()["detail"], "Username taken")
        self.assertEqual(self._accounts(), 1)

    def test_names_breaking_the_rule_are_refused(self):
        for bad in ("ab", "x" * 25, "has space", "josé", ""):
            with self.subTest(name=bad):
                self.assertEqual(self._register(bad).status_code, 422)
        self.assertEqual(self._accounts(), 0)

    def test_a_valid_name_still_registers(self):
        res = self._register("Night_Sorter_42")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("login_id", res.json())


if __name__ == "__main__":
    unittest.main()
