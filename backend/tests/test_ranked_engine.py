"""Ranked attempt engine core happy path (issue #8, piece 3)."""
import tempfile
from datetime import datetime, timezone
import unittest

from backend.db import migrate, settings
from backend.ranked import engine
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

# every fixture question in make_unconstrained_bank has this correct belt,
# so submitting it is always the correct answer
CORRECT = "GOLD"
WRONG = "YELLOW"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RankedEngineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        # a fresh migrated database per test keeps the one-active-attempt lock
        # and committed rows from leaking between tests
        try:
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(self.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())

    def _make_account(self, tag="R00001"):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"rank_{tag.lower()}", f"rank_{tag.lower()}", tag),
        )
        self.conn.commit()
        return row["id"]

    def _open_season(self):
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'test-season')",
        )
        self.conn.commit()

    def _play_one(self, attempt_id, seq, choice=CORRECT):
        view = engine.current_question(self.conn, attempt_id, bank=self.bank)
        self.assertEqual(view.seq, seq)
        result = engine.submit_answer(
            self.conn, attempt_id, seq, choice, clock=self.clock, bank=self.bank
        )
        return engine.advance(self.conn, attempt_id, clock=self.clock)

    def test_full_happy_path_reaches_terminal_pending(self):
        self._open_season()
        account_id = self._make_account()
        attempt_id = engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )
        for seq in range(1, 16):
            adv = self._play_one(attempt_id, seq)
            if seq < 15:
                self.assertFalse(adv.finished)
                self.assertEqual(adv.next_seq, seq + 1)
            else:
                self.assertTrue(adv.finished)
        row = migrate.fetch_one(
            self.conn,
            "SELECT state, final_outcome, settled_at FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        self.assertEqual(row["state"], "terminal_pending")
        self.assertEqual(row["final_outcome"], "completed")
        self.assertIsNone(row["settled_at"])
        count = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_answers WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual(count["n"], 15)
        self.assertIsNone(engine.current_question(self.conn, attempt_id, bank=self.bank))

    def test_wrong_answer_is_graded_wrong(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        result = engine.submit_answer(
            self.conn, attempt_id, 1, WRONG, clock=self.clock, bank=self.bank
        )
        self.assertFalse(result.correct)

    def test_double_submit_is_idempotent(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        first = engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        second = engine.submit_answer(
            self.conn, attempt_id, 1, WRONG, clock=self.clock, bank=self.bank
        )
        self.assertTrue(first.correct)
        self.assertTrue(second.correct)  # stored result unchanged
        row = migrate.fetch_one(
            self.conn,
            "SELECT answer FROM attempt_answers WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        self.assertEqual(row["answer"], "correct")

    def test_cannot_answer_a_question_not_yet_sent(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        with self.assertRaises(engine.AnswerRejectedError):
            engine.submit_answer(
                self.conn, attempt_id, 2, CORRECT, clock=self.clock, bank=self.bank
            )

    def test_answer_after_deadline_is_rejected(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        self.clock.advance(11)  # past the 10-second deadline
        with self.assertRaises(engine.AnswerRejectedError):
            engine.submit_answer(
                self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
            )

    def test_advance_requires_the_current_answer(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        with self.assertRaises(engine.NotAnsweredError):
            engine.advance(self.conn, attempt_id, clock=self.clock)

    def test_start_without_open_season_is_rejected(self):
        account_id = self._make_account()
        with self.assertRaises(engine.NoOpenSeasonError):
            engine.start_attempt(self.conn, account_id, clock=self.clock, bank=self.bank)

    def test_second_active_attempt_is_rejected(self):
        self._open_season()
        account_id = self._make_account()
        engine.start_attempt(self.conn, account_id, clock=self.clock, bank=self.bank)
        with self.assertRaises(engine.ActiveAttemptExistsError):
            engine.start_attempt(self.conn, account_id, clock=self.clock, bank=self.bank)


if __name__ == "__main__":
    unittest.main()
