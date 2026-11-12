import unittest

from fastapi.testclient import TestClient

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
        self.client = TestClient(app)

    def test_login_rate_limit_blocks_after_threshold(self):
        # Use a fresh client with a fixed IP-ish behavior. TestClient does not
        # set REMOTE_ADDR by default; the rate limiter keys on client host header.
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


if __name__ == "__main__":
    unittest.main()
