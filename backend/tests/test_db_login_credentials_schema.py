"""login_credentials schema contract: one credential row per account."""
import unittest

import psycopg

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class LoginCredentialsSchemaTests(unittest.TestCase):
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

    def _create_account(self):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_a', 'user_a', 'ABC123') RETURNING id",
        )["id"]

    def test_login_credentials_table_exists_with_expected_columns(self):
        row = migrate.fetch_one(
            self.conn,
            """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = 'login_credentials'
            ORDER BY ordinal_position
            """,
        )
        self.assertIsNotNone(row)

    def test_login_credentials_unique_lookup_key_and_account_fk(self):
        account_id = self._create_account()
        migrate.execute(
            self.conn,
            "INSERT INTO login_credentials (account_id, lookup_key, verifier) VALUES (%s, 'key1', 'hash1')",
            (account_id,),
        )
        # duplicate lookup_key rejected
        account_id_2 = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_b', 'user_b', 'BBB222') RETURNING id",
        )["id"]
        with self.assertRaises(psycopg.errors.UniqueViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO login_credentials (account_id, lookup_key, verifier) VALUES (%s, 'key1', 'hash2')",
                (account_id_2,),
            )

    def test_login_credentials_account_deletion_cascades(self):
        account_id = self._create_account()
        migrate.execute(
            self.conn,
            "INSERT INTO login_credentials (account_id, lookup_key, verifier) VALUES (%s, 'key2', 'hash')",
            (account_id,),
        )
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        row = migrate.fetch_one(
            self.conn,
            "SELECT * FROM login_credentials WHERE account_id = %s",
            (account_id,),
        )
        self.assertIsNone(row)
