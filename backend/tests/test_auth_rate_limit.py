import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

from backend.db import migrate, settings
from backend.main import create_app


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AuthRateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        app = create_app()
        self.client = TestClient(app, headers=BROWSER)

    def test_login_rate_limit_blocks_after_threshold(self):
        # The test client has one connection address shared by every test, so
        # this test acts as if a trusted proxy reported a distinct address;
        # its failures then cannot block other tests' logins.
        trusted = mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"})
        trusted.start()
        self.addCleanup(trusted.stop)
        for i in range(12):
            response = self.client.post(
                "/api/auth/login",
                json={"login_id": "WRNG-WRNG-WRNG-WRNG"},
                headers={"X-Forwarded-For": "192.168.1.50"},
            )
            if i < 10:
                self.assertEqual(response.status_code, 401)
            else:
                self.assertEqual(response.status_code, 429)

    def _wrong_login(self, forwarded):
        return self.client.post(
            "/api/auth/login",
            json={"login_id": "WRNG-WRNG-WRNG-WRNG"},
            headers={"X-Forwarded-For": forwarded},
        ).status_code

    def test_a_forged_first_entry_cannot_evade_the_limit(self):
        # issue #78: the client invents a new first entry on every request; the
        # ingress appends the same real address each time.
        trusted = mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"})
        trusted.start()
        self.addCleanup(trusted.stop)
        codes = [self._wrong_login(f"10.99.0.{n}, 192.168.7.7") for n in range(12)]
        self.assertEqual(codes, [401] * 10 + [429] * 2)

    def test_one_address_being_blocked_does_not_block_another(self):
        trusted = mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"})
        trusted.start()
        self.addCleanup(trusted.stop)
        for _ in range(11):
            self._wrong_login("192.168.8.8")
        self.assertEqual(self._wrong_login("192.168.8.8"), 429)
        self.assertEqual(self._wrong_login("192.168.9.9"), 401)


if __name__ == "__main__":
    unittest.main()
