import unittest
from uuid import UUID

from backend.auth.service import (
    admin_regenerate_login_id,
    get_account_by_session,
    login_with_id,
    register_account,
)
from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AuthServiceTests(unittest.TestCase):
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

    def test_register_and_login_round_trip(self):
        account_id, login_id = register_account(self.conn, "alice_1")
        self.assertIsInstance(account_id, UUID)
        self.assertEqual(len(login_id.replace("-", "")), 16)

        result = login_with_id(self.conn, login_id, 3600, "127.0.0.1", "test")
        self.assertIsNotNone(result)
        token, session_id = result
        self.assertIsInstance(session_id, UUID)

        account = get_account_by_session(self.conn, token)
        self.assertIsNotNone(account)
        self.assertEqual(account["id"], account_id)
        self.assertEqual(account["username"], "alice_1")

    def test_login_with_wrong_id_returns_none(self):
        result = login_with_id(self.conn, "WRNG-WRNG-WRNG-WRNG", 3600, None, None)
        self.assertIsNone(result)

    def test_admin_regenerate_login_id_revokes_old_sessions(self):
        # bootstrap an owner account
        owner_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner) VALUES ('owner_1', 'owner_1', 'OWN001', true) RETURNING id",
        )["id"]
        target_id, login_id = register_account(self.conn, "bob_1")
        token, _ = login_with_id(self.conn, login_id, 3600, None, None)
        self.assertIsNotNone(get_account_by_session(self.conn, token))

        new_login_id = admin_regenerate_login_id(self.conn, owner_id, target_id)
        self.assertIsNotNone(new_login_id)
        self.assertNotEqual(new_login_id, login_id)

        # old session revoked
        self.assertIsNone(get_account_by_session(self.conn, token))
        # new login ID works
        result = login_with_id(self.conn, new_login_id, 3600, None, None)
        self.assertIsNotNone(result)

    def test_admin_regenerate_by_non_owner_returns_none(self):
        non_owner_id, _ = register_account(self.conn, "charlie_1")
        target_id, login_id = register_account(self.conn, "dave_1")
        result = admin_regenerate_login_id(self.conn, non_owner_id, target_id)
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
