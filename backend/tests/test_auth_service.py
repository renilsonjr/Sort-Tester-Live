import unittest
from uuid import UUID

from backend.auth.service import (
    admin_regenerate_login_id,
    issue_new_login_id,
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
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)

    def test_register_and_login_round_trip(self):
        account_id, login_id = register_account(self.conn, "alice_1")
        self.assertIsInstance(account_id, UUID)
        self.assertRegex(login_id, r"^[a-z]{3,8}-[0-9]{2}$")

        result = login_with_id(self.conn, "alice_1", login_id, 3600, "127.0.0.1", "test")
        self.assertIsNotNone(result)
        token, session_id = result
        self.assertIsInstance(session_id, UUID)

        account = get_account_by_session(self.conn, token)
        self.assertIsNotNone(account)
        self.assertEqual(account["id"], account_id)
        self.assertEqual(account["username"], "alice_1")

    def test_login_with_wrong_id_returns_none(self):
        result = login_with_id(self.conn, "nobody_here", "WRNG-WRNG-WRNG-WRNG", 3600, None, None)
        self.assertIsNone(result)

    def test_the_unchecked_admin_regenerate_is_gone(self):
        """It reset a login ID on the owner's say-so alone, which the
        settled recovery policy does not allow: recovery needs a trusted
        roster link established before the request. backend.auth.recovery
        is that route now, and an old caller fails loudly."""
        owner_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES ('owner_1', 'owner_1', 'OWN001', true) RETURNING id",
        )["id"]
        target_id, _ = register_account(self.conn, "bob_1")
        with self.assertRaises(NotImplementedError) as caught:
            admin_regenerate_login_id(self.conn, owner_id, target_id)
        self.assertIn("recovery", str(caught.exception))

    def test_issuing_a_new_login_id_replaces_the_old_one(self):
        """The piece recovery uses: the old credential and every session
        stop at the moment the new login ID starts."""
        target_id, login_id = register_account(self.conn, "bob_2")
        token, _ = login_with_id(self.conn, "bob_2", login_id, 3600, None, None)
        self.assertIsNotNone(get_account_by_session(self.conn, token))

        new_login_id = issue_new_login_id(self.conn, target_id)
        self.assertNotEqual(new_login_id, login_id)
        self.assertIsNone(get_account_by_session(self.conn, token))
        self.assertIsNone(login_with_id(self.conn, "bob_2", login_id, 3600, None, None))
        self.assertIsNotNone(login_with_id(self.conn, "bob_2", new_login_id, 3600, None, None))


if __name__ == "__main__":
    unittest.main()
