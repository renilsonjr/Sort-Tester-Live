"""Participant links and season marker schema contract (migration 0004)."""
import itertools
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class LinksMarkerSchemaTests(unittest.TestCase):
    _counter = itertools.count(1)

    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        cls.admin = settings.admin_url()
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        # rollback at teardown keeps tests isolated (no committed rows leak
        # between tests; only the migration's schema is committed); cleanups
        # run LIFO, so register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)

    def _make_account(self):
        n = next(self._counter)
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"link_user{n}", f"link_user{n}", f"L{n:05d}"),
        )
        return row["id"]

    def _insert_link(self, account_id, roster_reference):
        return migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference)"
            " VALUES (%s, %s)",
            (account_id, roster_reference),
        )

    def _insert_marker(self, roster_reference, season, ineligible=False):
        return migrate.execute(
            self.conn,
            "INSERT INTO season_markers (roster_reference, season, ineligible)"
            " VALUES (%s, %s, %s)",
            (roster_reference, season, ineligible),
        )

    def test_link_is_one_per_account_and_owner_only(self):
        account_id = self._make_account()
        self._insert_link(account_id, "REF-A")
        # one link per account: a second insert violates the account_id UNIQUE
        with self.assertRaises(migrate.IntegrityError):
            self._insert_link(account_id, "REF-A2")
        # a second account can hold its own (different) link
        second = self._make_account()
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference)"
            " VALUES (%s, %s) RETURNING account_id, roster_reference",
            (second, "REF-B"),
        )
        self.assertEqual(row["account_id"], second)
        self.assertEqual(row["roster_reference"], "REF-B")

    def test_link_cascades_with_account(self):
        account_id = self._make_account()
        self._insert_link(account_id, "REF-CASCADE")
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT 1 FROM participant_links WHERE account_id = %s",
                (account_id,),
            )
        )

    def test_marker_survives_account_deletion(self):
        # Q10 structural boundary: the marker shares only the opaque
        # roster_reference with the account's link — no FK — so deleting the
        # account (and cascading the link) leaves the marker in place
        account_id = self._make_account()
        self._insert_link(account_id, "REF-SURVIVOR")
        self._insert_marker("REF-SURVIVOR", "2026", ineligible=True)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT 1 FROM participant_links WHERE account_id = %s",
                (account_id,),
            )
        )
        row = migrate.fetch_one(
            self.conn,
            "SELECT roster_reference, season, ineligible FROM season_markers"
            " WHERE roster_reference = %s",
            ("REF-SURVIVOR",),
        )
        self.assertIsNotNone(row)
        self.assertEqual(row["season"], "2026")
        self.assertTrue(row["ineligible"])

    def test_marker_column_set_is_minimal(self):
        rows = migrate.execute(
            self.conn,
            "SELECT column_name FROM information_schema.columns"
            " WHERE table_schema = 'public' AND table_name = 'season_markers'",
        ).fetchall()
        names = sorted(row["column_name"] for row in rows)
        # exactly these columns and nothing else — no username, email, tag or
        # any other credential-capable column exists
        self.assertEqual(names, ["id", "ineligible", "roster_reference", "season"])

    def test_marker_unique_per_reference_and_season(self):
        self._insert_marker("REF-UNIQUE", "2026")
        with self.assertRaises(migrate.IntegrityError):
            self._insert_marker("REF-UNIQUE", "2026")
        # a different season for the same reference is allowed
        row = migrate.fetch_one(
            self.conn,
            "SELECT roster_reference, season FROM season_markers WHERE season = %s",
            ("2027",),
        )
        self.assertIsNone(row)
        self._insert_marker("REF-UNIQUE", "2027")
        row = migrate.fetch_one(
            self.conn,
            "SELECT roster_reference, season FROM season_markers WHERE season = %s",
            ("2027",),
        )
        self.assertEqual(row["roster_reference"], "REF-UNIQUE")
