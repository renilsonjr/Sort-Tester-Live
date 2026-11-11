"""Emails schema contract: per-address uniqueness without alias folding, consent gate."""
import itertools
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class EmailsSchemaTests(unittest.TestCase):
    _tag_counter = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        cls.admin = settings.admin_url()
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        # rollback at teardown keeps tests isolated (no committed rows leak between
        # tests; only the migration's schema is committed); cleanups run LIFO, so
        # register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self.account_id = self._make_account("email_user")

    def _make_account(self, name):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
            (name, name, f"A{next(self._tag_counter):05d}"),
        )
        return row["id"]

    def _insert_email(self, account_id, address, normalized, state, opt_in=False, opt_in_at=None):
        return migrate.execute(
            self.conn,
            "INSERT INTO emails (account_id, address, address_normalized, state, reminder_opt_in, reminder_opt_in_at)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (account_id, address, normalized, state, opt_in, opt_in_at),
        )

    def test_alias_addresses_are_distinct(self):
        # dots and plus-tags are never folded: a.b@, ab@ and a+b@ all coexist
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('email_user2', 'email_user2', 'B00001')")
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('email_user3', 'email_user3', 'B00002')")
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('email_user4', 'email_user4', 'B00003')")
        second = migrate.fetch_one(self.conn, "SELECT id FROM accounts WHERE username_lower = 'email_user2'")["id"]
        third = migrate.fetch_one(self.conn, "SELECT id FROM accounts WHERE username_lower = 'email_user3'")["id"]
        fourth = migrate.fetch_one(self.conn, "SELECT id FROM accounts WHERE username_lower = 'email_user4'")["id"]
        self._insert_email(self.account_id, "a.b@x.com", "a.b@x.com", "verified")
        self._insert_email(second, "ab@x.com", "ab@x.com", "verified")
        self._insert_email(third, "a+b@x.com", "a+b@x.com", "verified")
        # case IS folded: a.b@X.COM normalizes to a.b@x.com and collides with
        # the first row, but not with the dot-less/plus-tagged neighbours
        with self.assertRaises(migrate.IntegrityError):
            self._insert_email(fourth, "a.b@X.COM", "a.b@x.com", "pending")

    def test_one_active_email_per_account(self):
        self._insert_email(self.account_id, "first@x.com", "first@x.com", "verified")
        with self.assertRaises(migrate.IntegrityError):
            self._insert_email(self.account_id, "second@x.com", "second@x.com", "pending")

    def test_retired_address_reusable(self):
        self._insert_email(self.account_id, "a.b@x.com", "a.b@x.com", "verified")
        migrate.execute(self.conn, "UPDATE emails SET state = 'retired' WHERE account_id = %s AND address_normalized = %s", (self.account_id, "a.b@x.com"))
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('email_user2', 'email_user2', 'B00004')")
        second = migrate.fetch_one(self.conn, "SELECT id FROM accounts WHERE username_lower = 'email_user2'")["id"]
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO emails (account_id, address, address_normalized, state, verified_at)"
            " VALUES (%s, %s, %s, %s, now()) RETURNING id, state",
            (second, "a.b@x.com", "a.b@x.com", "verified"),
        )
        self.assertEqual(row["state"], "verified")

    def test_consent_requires_verified(self):
        # opt-in on a pending row violates the consent CHECK
        with self.assertRaises(migrate.IntegrityError):
            self._insert_email(self.account_id, "a.b@x.com", "a.b@x.com", "pending", opt_in=True, opt_in_at="2026-11-11T00:00:00Z")
        # verified + opt-in but no timestamp still violates the consent CHECK
        with self.assertRaises(migrate.IntegrityError):
            self._insert_email(self.account_id, "a.b@x.com", "a.b@x.com", "verified", opt_in=True)
        # verified + opt-in + timestamp passes
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO emails (account_id, address, address_normalized, state, reminder_opt_in, reminder_opt_in_at, consent_season)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING state, reminder_opt_in",
            (self.account_id, "a.b@x.com", "a.b@x.com", "verified", True, "2026-11-11T00:00:00Z", None),
        )
        self.assertEqual(row["state"], "verified")
        self.assertTrue(row["reminder_opt_in"])
