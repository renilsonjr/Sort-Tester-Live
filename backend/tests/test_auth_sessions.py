import unittest
from hashlib import sha256
from uuid import UUID

from backend.auth.settings import get_auth_settings
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
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
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

    # Inactivity logout (#10). A phone put down on the sort floor should not
    # keep an account open, and the app's own timer cannot be the whole
    # rule: a page can be kept awake, a revoked session cannot.
    def _set_last_seen(self, token, minutes_ago):
        migrate.execute(
            self.conn,
            "UPDATE sessions SET last_seen_at = now() - %s * interval '1 minute'"
            " WHERE token_hash = %s",
            (minutes_ago, sha256(token.encode("ascii")).digest()),
        )

    def test_a_session_left_alone_past_the_window_is_refused(self):
        token, session_id = create_session(self.conn, self.account_id, 3600, None, None)
        self._set_last_seen(token, 16)
        self.assertIsNone(authenticate_session(self.conn, token, idle_seconds=15 * 60))
        # and it is revoked, so presenting it again is not a second chance
        row = migrate.fetch_one(
            self.conn, "SELECT revoked_at FROM sessions WHERE id = %s", (session_id,)
        )
        self.assertIsNotNone(row["revoked_at"])

    def test_a_session_inside_the_window_still_works(self):
        token, _ = create_session(self.conn, self.account_id, 3600, None, None)
        self._set_last_seen(token, 14)
        self.assertIsNotNone(
            authenticate_session(self.conn, token, idle_seconds=15 * 60)
        )

    def test_each_request_resets_the_window(self):
        """The window is since the last request, not since login."""
        token, _ = create_session(self.conn, self.account_id, 3600, None, None)
        self._set_last_seen(token, 14)
        self.assertIsNotNone(
            authenticate_session(self.conn, token, idle_seconds=15 * 60)
        )
        # that call refreshed last_seen_at, so fourteen more minutes of use
        # is still fine rather than adding up to twenty-eight
        self._set_last_seen(token, 14)
        self.assertIsNotNone(
            authenticate_session(self.conn, token, idle_seconds=15 * 60)
        )

    def test_the_window_is_fifteen_minutes_by_default(self):
        """The default is the figure the owner chose, not a test argument."""
        self.assertEqual(get_auth_settings().session_idle_seconds, 15 * 60)
        token, _ = create_session(self.conn, self.account_id, 3600, None, None)
        self._set_last_seen(token, 16)
        self.assertIsNone(authenticate_session(self.conn, token))

    def test_zero_turns_the_idle_rule_off(self):
        """So a deployment can keep the old behaviour without a code change."""
        token, _ = create_session(self.conn, self.account_id, 3600, None, None)
        self._set_last_seen(token, 10 * 60)
        self.assertIsNotNone(authenticate_session(self.conn, token, idle_seconds=0))

    def test_an_idle_session_does_not_outlive_its_own_expiry(self):
        """The eight-hour ceiling is unchanged by the idle rule."""
        token, _ = create_session(self.conn, self.account_id, 1, None, None)
        migrate.execute(
            self.conn,
            # created_at moves with it: the table requires expires_at to be
            # at or after it.
            "UPDATE sessions SET created_at = now() - interval '9 hours',"
            " expires_at = now() - interval '1 second'"
            " WHERE token_hash = %s",
            (sha256(token.encode("ascii")).digest(),),
        )
        self.assertIsNone(authenticate_session(self.conn, token, idle_seconds=0))


if __name__ == "__main__":
    unittest.main()
