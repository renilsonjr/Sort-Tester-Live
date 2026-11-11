"""Balance ledger schema contract (issue #6 check 4)."""
import unittest

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class BalanceLedgerTests(unittest.TestCase):
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
        # rollback at teardown keeps tests isolated (no committed rows leak
        # between tests; only the migration's schema is committed); cleanups
        # run LIFO, so register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        # usernames/tags are unique keys: one account per test in setUp plus
        # any extra accounts a test creates need distinct values (rollback
        # isolation makes cross-test reuse safe, not intra-test reuse)
        self._account_n = 0
        self.account_id = self._make_account()
        # the first season is already closed: cutover opens the next row
        self.season_id = self._make_season(
            label="pre_season",
            opened_at="2026-01-01T00:00:00Z",
            closed_at="2026-01-15T00:00:00Z",
        )

    def _make_account(self):
        self._account_n += 1
        suffix = "" if self._account_n == 1 else str(self._account_n)
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (
                f"ledger_user{suffix}",
                f"ledger_user{suffix}",
                f"C{self._account_n:05d}",
            ),
        )
        return row["id"]

    def _make_season(self, label="pre_season", phase="pre_season",
                     opened_at=None, closed_at=None):
        columns = ["phase", "label"]
        values = [phase, label]
        if opened_at is not None:
            columns.append("opened_at")
            values.append(opened_at)
        if closed_at is not None:
            columns.append("closed_at")
            values.append(closed_at)
        placeholders = ", ".join(["%s"] * len(values))
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons ({}) VALUES ({}) RETURNING id".format(
                ", ".join(columns), placeholders
            ),
            values,
        )
        return row["id"]

    def _make_assignment(self, account_id=None, season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id or self.account_id, season_id or self.season_id),
        )
        return row["id"]

    def _make_attempt(self, account_id=None, season_id=None):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, state,"
            " season_id, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', 'terminal_pending', %s, 'quit', now())"
            " RETURNING id",
            (account_id or self.account_id,
             self._make_assignment(account_id, season_id),
             season_id or self.season_id),
        )
        return row["id"]

    def _make_settlement(self, account_id=None, season_id=None, raw_score=120,
                         adjustment=0, final_outcome="quit"):
        attempt_id = self._make_attempt(account_id, season_id)
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO settlements (attempt_id, season_id, raw_score,"
            " adjustment, final_outcome)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING attempt_id",
            (attempt_id, season_id or self.season_id, raw_score, adjustment,
             final_outcome),
        )
        return row["attempt_id"]

    def _make_balance(self, account_id, current_points=0):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO balances (account_id, current_points)"
            " VALUES (%s, %s) RETURNING account_id",
            (account_id, current_points),
        )
        return row["account_id"]

    def _make_history(self, settlement_id=None, raw_score=100, adjustment=-10,
                      points_before=500, points_after=590,
                      badge_before="Bronze", badge_after="Bronze"):
        if settlement_id is None:
            settlement_id = self._make_settlement()
        # the account is not a free parameter: it is the settled attempt's
        # account, so the row cannot point a history entry at a third party
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO balance_history"
            " (account_id, settlement_id, raw_score, adjustment,"
            " points_before, points_after, badge_before, badge_after)"
            " SELECT a.account_id, %s, %s, %s, %s, %s, %s, %s"
            " FROM settlements s JOIN attempts a ON a.id = s.attempt_id"
            " WHERE s.attempt_id = %s"
            " RETURNING id",
            (settlement_id, raw_score, adjustment, points_before,
             points_after, badge_before, badge_after, settlement_id),
        )
        return row

    def test_one_balance_per_account(self):
        account_id = self._make_account()
        self._make_balance(account_id, current_points=0)
        with self.assertRaises(migrate.IntegrityError):
            self._make_balance(account_id, current_points=100)

    def test_history_unique_per_settlement(self):
        settlement_id = self._make_settlement()
        self._make_history(settlement_id, raw_score=100, adjustment=-10,
                           points_before=500, points_after=590,
                           badge_before='Bronze', badge_after='Bronze')
        with self.assertRaises(migrate.IntegrityError):
            self._make_history(settlement_id, raw_score=0, adjustment=0,
                               points_before=0, points_after=0,
                               badge_before='Iron', badge_after='Iron')

    def test_history_preserves_raw_adjustment_before_after(self):
        row = self._make_history(raw_score=100, adjustment=-10,
                                 points_before=500, points_after=590,
                                 badge_before='Bronze', badge_after='Bronze')
        fetched = migrate.fetch_one(
            self.conn, "SELECT * FROM balance_history WHERE id = %s",
            (row['id'],)
        )
        self.assertEqual(fetched['raw_score'], 100)
        self.assertEqual(fetched['adjustment'], -10)
        self.assertEqual(fetched['points_before'], 500)
        self.assertEqual(fetched['points_after'], 590)
        self.assertEqual(fetched['badge_before'], 'Bronze')
        self.assertEqual(fetched['badge_after'], 'Bronze')

    def test_cascade_deletes_balance_and_history(self):
        account_id = self._make_account()
        self._make_balance(account_id, current_points=0)
        settlement_id = self._make_settlement(account_id=account_id)
        self._make_history(settlement_id)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s",
                        (account_id,))
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM balances WHERE account_id = %s", (account_id,))
        )
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        )
