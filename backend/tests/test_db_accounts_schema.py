"""Accounts schema contract: stable id, CI username, permanent tag."""
import re
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AccountsSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        cls.admin = settings.admin_url()
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        # rollback at teardown keeps tests isolated (no committed rows leak between tests);
        # cleanups run LIFO, so register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)

    def test_case_insensitive_username_collision_rejected(self):
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('Alice_1', 'alice_1', 'AAAAAA')")
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('ALICE_1', 'ALICE_1', 'BBBBBB')")

    def test_username_format_check(self):
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('ab', 'ab', 'CCCCCC')")  # too short
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('bad-name!', 'badname!!', 'DDDDDD')")  # bad chars

    def test_tag_format_and_uniqueness(self):
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_a', 'user_a', 'abc123')")  # lowercase tag
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_a', 'user_a', 'ABC123')")
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_b', 'user_b', 'ABC123')")

    def test_default_uuid_and_timestamps(self):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_c', 'user_c', 'DEF456') RETURNING id, created_at, deleted_at",
        )
        self.assertIsNotNone(row["id"])
        self.assertIsNone(row["deleted_at"])
