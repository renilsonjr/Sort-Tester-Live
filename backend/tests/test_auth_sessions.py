import unittest
from uuid import UUID

from backend.auth.sessions import (
    authenticate_session,
    create_session,
    revoke_all_account_sessions,
    revoke_session,
)
from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SessionsManagerTests(unittest.TestCase):
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
        self.account_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('sess_user', 'sess_user', 'SES123') RETURNING id",
        )["id"]

    def test_create_and_authenticate_session(self):
        token, session_id = create_session(self.conn, self.account_id, 3600, "127.0.0.1", "test-agent")
        self.assertIsInstance(session_id, UUID)
        self.assertEqual(len(token), 43)  # token_urlsafe(32) length

        session = authenticate_session(self.conn, token)
        self.assertIsNotNone(session)
        self.assertEqual(session["account_id"], self.account_id)

        revoke_session(self.conn, session_id)
        self.assertIsNone(authenticate_session(self.conn, token))

    def test_authenticate_session_rejects_invalid_token(self):
        self.assertIsNone(authenticate_session(self.conn, "not-a-real-token"))

    def test_revoke_all_account_sessions(self):
        token_1, _ = create_session(self.conn, self.account_id, 3600, None, None)
        token_2, _ = create_session(self.conn, self.account_id, 3600, None, None)
        self.assertIsNotNone(authenticate_session(self.conn, token_1))
        self.assertIsNotNone(authenticate_session(self.conn, token_2))

        revoke_all_account_sessions(self.conn, self.account_id)
        self.assertIsNone(authenticate_session(self.conn, token_1))
        self.assertIsNone(authenticate_session(self.conn, token_2))


if __name__ == "__main__":
    unittest.main()
