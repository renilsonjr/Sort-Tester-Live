"""sessions schema contract: opaque server-side session tokens."""
import unittest
from datetime import datetime, timedelta, timezone

import psycopg

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SessionsSchemaTests(unittest.TestCase):
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
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('sess_user', 'sess_user', 'SES123') RETURNING id",
        )["id"]

    def test_sessions_table_exists_with_expected_columns(self):
        row = migrate.fetch_one(
            self.conn,
            """
            SELECT column_name, data_type
            FROM information_schema.columns
            WHERE table_name = 'sessions' AND column_name = 'token_hash'
            """,
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["data_type"], "bytea")

    def test_sessions_unique_token_hash_and_account_fk(self):
        account_id = self._create_account()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at) VALUES (%s, '\\xDEADBEEF', %s)",
            (account_id, expires_at),
        )
        with self.assertRaises(psycopg.errors.UniqueViolation):
            migrate.execute(
                self.conn,
                "INSERT INTO sessions (account_id, token_hash, expires_at) VALUES (%s, '\\xDEADBEEF', %s)",
                (account_id, expires_at),
            )

    def test_sessions_account_deletion_cascades(self):
        account_id = self._create_account()
        expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at) VALUES (%s, '\\xCAFE', %s)",
            (account_id, expires_at),
        )
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        row = migrate.fetch_one(
            self.conn,
            "SELECT * FROM sessions WHERE account_id = %s",
            (account_id,),
        )
        self.assertIsNone(row)
