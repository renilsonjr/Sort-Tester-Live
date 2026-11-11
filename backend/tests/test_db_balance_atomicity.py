"""Balance update atomicity simulation (issue #6 check 4)."""
import unittest
import uuid

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class BalanceAtomicityTests(unittest.TestCase):
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
        # self.conn only VERIFIES outcomes: it is rolled back in teardown
        # (cleanups run LIFO: rollback before close), so the test itself
        # never commits through it
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        # the transaction under test runs on a dedicated connection, and
        # PostgreSQL FK checks only see committed rows, so setup data is
        # inserted AND COMMITTED on a separate connection before any
        # commit/rollback simulation starts
        self.setup = migrate.connect(self.conninfo)
        self.addCleanup(self.setup.close)
        # every committed account is purged at teardown (the account cascade
        # removes its balance, assignments, attempts, settlements, and
        # history) so the BAT tags can restart at BAT001 in every test
        # without colliding on the unique username/tag keys
        self._committed_accounts = []
        self.addCleanup(self._purge_committed_accounts)
        self._counter = 0

    def _purge_committed_accounts(self):
        if not self._committed_accounts:
            return
        migrate.execute(
            self.setup,
            "DELETE FROM accounts WHERE id = ANY(%s)",
            (self._committed_accounts,),
        )
        self.setup.commit()

    def _unique_tag(self):
        self._counter += 1
        return f"BAT{self._counter:03d}"

    def _make_account(self, tag):
        # usernames/tags are unique keys: one account per tag per test; the
        # teardown purge keeps the tags reusable across tests (rollback
        # isolation is not available here because the rows must be committed
        # for the transaction under test to satisfy FK checks)
        username = f"atomicity_{tag.lower()}"
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (username, username, tag),
        )
        account_id = row["id"]
        self._committed_accounts.append(account_id)
        self.setup.commit()
        return account_id

    def _make_season(self):
        # label is a unique key and committed season rows are not cascaded
        # away with the account, so each call gets a uuid label
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO seasons (phase, label)"
            " VALUES ('pre_season', %s) RETURNING id",
            (f"bat_{uuid.uuid4().hex}",),
        )
        season_id = row["id"]
        self.setup.commit()
        return season_id

    def _make_assignment(self, account_id, season_id):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, season_id),
        )
        assignment_id = row["id"]
        self.setup.commit()
        return assignment_id

    def _make_attempt(self, account_id, season_id):
        # attempts.assignment_id is unique: a fresh assignment per attempt
        assignment_id = self._make_assignment(account_id, season_id)
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO attempts (account_id, assignment_id, mode, state,"
            " season_id, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', 'finalized', %s, 'quit', now())"
            " RETURNING id",
            (account_id, assignment_id, season_id),
        )
        attempt_id = row["id"]
        self.setup.commit()
        return attempt_id

    def _make_settlement(self, account_id):
        # a fresh finalized attempt per settlement: the active-attempt lock
        # (one unfinished attempt per account) does not count finalized
        # rows, so several settlements can coexist for the same account
        season_id = self._make_season()
        attempt_id = self._make_attempt(account_id, season_id)
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO settlements (attempt_id, season_id, raw_score,"
            " adjustment, final_outcome)"
            " VALUES (%s, %s, 0, 0, 'quit') RETURNING attempt_id",
            (attempt_id, season_id),
        )
        settlement_id = row["attempt_id"]
        self.setup.commit()
        return settlement_id

    def _make_balance(self, account_id, current_points=0):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO balances (account_id, current_points)"
            " VALUES (%s, %s) RETURNING account_id",
            (account_id, current_points),
        )
        balance_account_id = row["account_id"]
        self.setup.commit()
        return balance_account_id

    def _apply_settlement(self, account_id, settlement_id, raw_score,
                          adjustment, points_before, points_after):
        # the engine-shaped settlement step, simulated atomically: the
        # balance update and its history row are one committed transaction,
        # exactly the invariant the schema must let the engine preserve
        tx = migrate.connect(self.conninfo)
        try:
            migrate.execute(tx, """
                UPDATE balances SET current_points = %s, updated_at = now()
                WHERE account_id = %s
            """, (points_after, account_id))
            migrate.execute(tx, """
                INSERT INTO balance_history
                (account_id, settlement_id, raw_score, adjustment, points_before, points_after, badge_before, badge_after)
                VALUES (%s, %s, %s, %s, %s, %s, 'Iron', 'Iron')
            """, (account_id, settlement_id, raw_score, adjustment,
                  points_before, points_after))
            tx.commit()
        finally:
            tx.close()

    def test_committed_update_visible(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=0)
        settlement_id = self._make_settlement(account_id)
        tx = migrate.connect(self.conninfo)
        try:
            migrate.execute(tx, """
                UPDATE balances SET current_points = 590, updated_at = now()
                WHERE account_id = %s
            """, (account_id,))
            migrate.execute(tx, """
                INSERT INTO balance_history
                (account_id, settlement_id, raw_score, adjustment, points_before, points_after, badge_before, badge_after)
                VALUES (%s, %s, 100, -10, 500, 590, 'Bronze', 'Bronze')
            """, (account_id, settlement_id))
            tx.commit()
        finally:
            tx.close()
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 590)
        hist = migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        self.assertIsNotNone(hist)

    def test_rollback_leaves_no_trace(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=100)
        settlement_id = self._make_settlement(account_id)
        tx = migrate.connect(self.conninfo)
        try:
            migrate.execute(tx, "UPDATE balances SET current_points = 999 WHERE account_id = %s", (account_id,))
            migrate.execute(tx, """
                INSERT INTO balance_history
                (account_id, settlement_id, raw_score, adjustment, points_before, points_after, badge_before, badge_after)
                VALUES (%s, %s, 0, 0, 100, 999, 'Iron', 'Iron')
            """, (account_id, settlement_id))
            tx.rollback()
        finally:
            tx.close()
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 100)
        hist = migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        self.assertIsNone(hist)

    def test_multiple_settlements_accumulate(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=0)
        s1 = self._make_settlement(account_id)
        self._apply_settlement(account_id, s1, raw_score=100, adjustment=0, points_before=0, points_after=100)
        s2 = self._make_settlement(account_id)
        self._apply_settlement(account_id, s2, raw_score=50, adjustment=0, points_before=100, points_after=150)
        count = migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM balance_history WHERE account_id = %s", (account_id,))
        self.assertEqual(count['n'], 2)
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 150)
