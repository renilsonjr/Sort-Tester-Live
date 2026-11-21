"""recovery_messages: what the table itself refuses (issue #251)."""
import unittest

import psycopg

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessagesSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _insert(self, body):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO recovery_messages (body) VALUES (%s)"
            " RETURNING id, created_at, resolved_at, resolved_by",
            (body,),
        )

    def test_a_message_starts_open(self):
        row = self._insert("locked out")
        self.assertIsNotNone(row["created_at"])
        self.assertIsNone(row["resolved_at"])
        self.assertIsNone(row["resolved_by"])

    def test_empty_and_overlong_bodies_are_refused(self):
        for body in ("", "x" * 501):
            with self.assertRaises(psycopg.errors.CheckViolation):
                self._insert(body)
            self.conn.rollback()
        self._insert("x" * 500)

    def test_resolved_by_needs_resolved_at(self):
        owner = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES ('the_owner', 'the_owner', 'OWN001', true) RETURNING id",
        )["id"]
        message = self._insert("locked out")["id"]
        with self.assertRaises(psycopg.errors.CheckViolation):
            migrate.execute(
                self.conn,
                "UPDATE recovery_messages SET resolved_by = %s WHERE id = %s",
                (owner, message),
            )

    def test_deleting_the_resolver_keeps_the_message(self):
        owner = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES ('the_owner', 'the_owner', 'OWN001', true) RETURNING id",
        )["id"]
        message = self._insert("locked out")["id"]
        migrate.execute(
            self.conn,
            "UPDATE recovery_messages SET resolved_at = now(), resolved_by = %s"
            " WHERE id = %s",
            (owner, message),
        )
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (owner,))
        row = migrate.fetch_one(
            self.conn,
            "SELECT resolved_at, resolved_by FROM recovery_messages WHERE id = %s",
            (message,),
        )
        self.assertIsNotNone(row["resolved_at"])
        self.assertIsNone(row["resolved_by"])

    def test_downgrade_removes_the_table(self):
        self.conn.close()
        self.assertTrue(migrate.table_exists(self.conninfo, "recovery_messages"))
        migrate.downgrade_all(self.conninfo)
        self.assertFalse(migrate.table_exists(self.conninfo, "recovery_messages"))
