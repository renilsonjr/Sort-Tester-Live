"""Ranked settlement: one ended attempt's result is applied exactly once
(issue #9, slice 2)."""
import tempfile
import threading
from datetime import datetime, timezone
import unittest
from unittest import mock

from backend.db import migrate, settings
from backend.ranked import engine, scoring, settlement
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

CORRECT = "GOLD"
WRONG = "YELLOW"


class SettlementTestCase(unittest.TestCase):
    """Shared setup: a fresh migrated database, one open season, a fake clock."""

    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        try:
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(self.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.clock = FakeClock(datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc))
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'test-season')",
        )
        self.conn.commit()
        self._accounts = 0

    # --- helpers ---

    def _account(self, points=None):
        self._accounts += 1
        tag = f"S{self._accounts:05d}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"settle_{tag.lower()}", f"settle_{tag.lower()}", tag),
        )
        if points is not None:
            migrate.execute(
                self.conn,
                "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
                (row["id"], points),
            )
        self.conn.commit()
        return row["id"]

    def _start(self, account_id, mode="normal"):
        return engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank, mode=mode
        )

    def _answer(self, attempt_id, seq, choice):
        return engine.submit_answer(
            self.conn, attempt_id, seq, choice, clock=self.clock, bank=self.bank
        )

    def _play(self, attempt_id, choices):
        """Answer questions 1..len(choices), pressing Next between them."""
        for seq, choice in enumerate(choices, start=1):
            result = self._answer(attempt_id, seq, choice)
            if not result.finished and seq < len(choices):
                engine.advance(self.conn, attempt_id, clock=self.clock)

    def _settle(self, attempt_id):
        return settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)

    def _stored_answers(self, attempt_id):
        rows = migrate.fetch_all(
            self.conn,
            "SELECT qv.difficulty, aa.answer FROM attempt_answers aa"
            " JOIN question_versions qv ON qv.id = aa.question_version_id"
            " WHERE aa.attempt_id = %s ORDER BY aa.seq",
            (attempt_id,),
        )
        return [(row["difficulty"], row["answer"]) for row in rows]

    def _points(self, account_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT current_points FROM balances WHERE account_id = %s",
            (account_id,),
        )
        return None if row is None else row["current_points"]

    def _count(self, table, attempt_id):
        column = "settlement_id" if table == "balance_history" else "attempt_id"
        row = migrate.fetch_one(
            self.conn,
            f"SELECT COUNT(*) AS n FROM {table} WHERE {column} = %s",
            (attempt_id,),
        )
        return row["n"]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SettleAttemptTests(SettlementTestCase):
    def test_perfect_attempt_from_zero_persists_every_record(self):
        account_id = self._account()  # no balance row yet
        attempt_id = self._start(account_id)
        self._play(attempt_id, [CORRECT] * 15)
        self.clock.advance(3)
        result = self._settle(attempt_id)

        self.assertEqual((result.raw_score, result.adjustment), (300, 300))
        self.assertEqual(self._points(account_id), 300)
        row = migrate.fetch_one(
            self.conn,
            "SELECT raw_score, adjustment, final_outcome, settled_at"
            " FROM settlements WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual(
            (row["raw_score"], row["adjustment"], row["final_outcome"]),
            (300, 300, "completed"),
        )
        self.assertEqual(row["settled_at"], self.clock.now())
        history = migrate.fetch_one(
            self.conn,
            "SELECT account_id, raw_score, adjustment, points_before, points_after,"
            " badge_before, badge_after FROM balance_history WHERE settlement_id = %s",
            (attempt_id,),
        )
        self.assertEqual(history["account_id"], account_id)
        self.assertEqual(
            (history["raw_score"], history["adjustment"], history["points_before"],
             history["points_after"], history["badge_before"], history["badge_after"]),
            (300, 300, 0, 300, "Iron", "Iron"),
        )
        attempt = migrate.fetch_one(
            self.conn, "SELECT state, settled_at FROM attempts WHERE id = %s", (attempt_id,)
        )
        self.assertEqual(attempt["state"], "finalized")
        self.assertEqual(attempt["settled_at"], self.clock.now())

    def test_overflow_above_the_cap_is_discarded(self):
        account_id = self._account(points=950)
        attempt_id = self._start(account_id)
        self._play(attempt_id, [CORRECT] * 15)
        result = self._settle(attempt_id)
        self.assertEqual((result.raw_score, result.adjustment), (300, 50))
        self.assertEqual(self._points(account_id), 1000)

    def test_all_wrong_can_demote(self):
        account_id = self._account(points=1010)
        attempt_id = self._start(account_id)
        self._play(attempt_id, [WRONG] * 15)
        result = self._settle(attempt_id)
        self.assertEqual((result.badge_before, result.badge_after), ("Bronze", "Iron"))
        self.assertEqual(self._points(account_id), 860)

    def test_quit_with_no_answers_costs_ten(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        result = self._settle(attempt_id)
        self.assertEqual((result.raw_score, result.adjustment), (0, -10))
        self.assertEqual(self._points(account_id), 490)

    def test_partial_outcomes_persist_what_the_maths_gives(self):
        endings = {
            "quit": lambda a: engine.quit_attempt(self.conn, a, clock=self.clock),
            "season_close": lambda a: engine.end_attempts_for_season_close(
                self.conn, self._season(a), clock=self.clock
            ),
        }
        for outcome, end in endings.items():
            with self.subTest(outcome=outcome):
                account_id = self._account(points=500)
                attempt_id = self._start(account_id)
                self._play(attempt_id, [CORRECT, WRONG, CORRECT])
                end(attempt_id)
                expected = scoring.settle(
                    500, "normal", outcome, self._stored_answers(attempt_id)
                )
                self.assertEqual(self._settle(attempt_id), expected)
                self.assertEqual(self._points(account_id), expected.points_after)

    def test_disconnect_counts_the_timed_out_question_without_a_penalty(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self.clock.advance(60)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        answers = self._stored_answers(attempt_id)
        self.assertEqual([answer for _, answer in answers], ["timeout"])
        result = self._settle(attempt_id)
        self.assertEqual(result.adjustment, scoring.answer_points(answers[0][0], "timeout"))
        self.assertEqual(self._points(account_id), 500 + result.adjustment)

    def test_void_outcomes_leave_the_balance_unchanged(self):
        voids = {
            "outage_void": lambda a: engine.void_attempts_for_outage(
                self.conn, outage_start=self.clock.now(), outage_end=self.clock.now()
            ),
            "launch_reset": lambda a: engine.void_attempts_for_launch(
                self.conn, self._season(a)
            ),
        }
        for outcome, void in voids.items():
            with self.subTest(outcome=outcome):
                account_id = self._account(points=500)
                attempt_id = self._start(account_id)
                self._play(attempt_id, [WRONG, WRONG])
                void(attempt_id)
                result = self._settle(attempt_id)
                self.assertLess(result.raw_score, 0)  # the history keeps the raw score
                self.assertEqual(result.adjustment, 0)
                self.assertEqual(self._points(account_id), 500)
                self.assertEqual(self._count("settlements", attempt_id), 1)

    def test_perfect_promotion_persists_cap_plus_one_and_the_new_badge(self):
        account_id = self._account(points=1000)
        attempt_id = self._start(account_id, mode="promotion")
        self._play(attempt_id, [CORRECT] * 15)
        result = self._settle(attempt_id)
        self.assertEqual((result.raw_score, result.adjustment), (300, 1))
        self.assertEqual(self._points(account_id), 1001)
        history = migrate.fetch_one(
            self.conn,
            "SELECT badge_before, badge_after FROM balance_history"
            " WHERE settlement_id = %s",
            (attempt_id,),
        )
        self.assertEqual(
            (history["badge_before"], history["badge_after"]), ("Iron", "Bronze")
        )

    def test_promotion_mistake_only_deducts(self):
        account_id = self._account(points=1000)
        attempt_id = self._start(account_id, mode="promotion")
        self._play(attempt_id, [WRONG] + [CORRECT] * 14)
        first_difficulty = self._stored_answers(attempt_id)[0][0]
        result = self._settle(attempt_id)
        self.assertEqual(
            result.adjustment, scoring.answer_points(first_difficulty, "wrong")
        )
        self.assertEqual(self._points(account_id), 1000 + result.adjustment)

    def test_settling_twice_applies_the_result_once(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._play(attempt_id, [CORRECT] * 15)
        first = self._settle(attempt_id)
        self.clock.advance(30)
        second = self._settle(attempt_id)
        self.assertEqual(second, first)
        self.assertEqual(self._points(account_id), 800)
        self.assertEqual(self._count("settlements", attempt_id), 1)
        self.assertEqual(self._count("balance_history", attempt_id), 1)

    def test_a_running_attempt_cannot_be_settled(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._answer(attempt_id, 1, CORRECT)
        with self.assertRaises(settlement.AttemptNotEndedError):
            self._settle(attempt_id)
        self.assertEqual(self._points(account_id), 500)
        self.assertEqual(self._count("settlements", attempt_id), 0)
        self.assertEqual(self._count("balance_history", attempt_id), 0)

    def test_a_new_attempt_can_start_after_settlement(self):
        account_id = self._account()
        attempt_id = self._start(account_id)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        with self.assertRaises(engine.ActiveAttemptExistsError):
            self._start(account_id)  # ended but not settled: still locked
        self._settle(attempt_id)
        self.assertNotEqual(self._start(account_id), attempt_id)

    def _season(self, attempt_id):
        row = migrate.fetch_one(
            self.conn, "SELECT season_id FROM attempts WHERE id = %s", (attempt_id,)
        )
        return row["season_id"]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SettlePendingTests(SettlementTestCase):
    def _ended_attempt(self, points):
        account_id = self._account(points=points)
        attempt_id = self._start(account_id)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        return account_id, attempt_id

    def test_sweep_settles_every_pending_attempt_and_nothing_else(self):
        first_account, first = self._ended_attempt(500)
        second_account, second = self._ended_attempt(700)
        done_account, done = self._ended_attempt(900)
        self._settle(done)                      # already finalized
        running_account = self._account(points=300)
        running = self._start(running_account)  # still being played

        self.assertEqual(settlement.settle_pending(self.conn, clock=self.clock), 2)
        self.assertEqual(self._points(first_account), 490)
        self.assertEqual(self._points(second_account), 690)
        self.assertEqual(self._points(done_account), 890)     # not applied twice
        self.assertEqual(self._points(running_account), 300)  # untouched
        self.assertEqual(self._count("settlements", running), 0)
        for attempt_id in (first, second, done):
            self.assertEqual(self._count("settlements", attempt_id), 1)

    def test_sweep_with_nothing_pending_does_nothing(self):
        account_id, attempt_id = self._ended_attempt(500)
        self.assertEqual(settlement.settle_pending(self.conn, clock=self.clock), 1)
        self.assertEqual(settlement.settle_pending(self.conn, clock=self.clock), 0)
        self.assertEqual(self._points(account_id), 490)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SettlementRaceTests(SettlementTestCase):
    def _race(self, first, second):
        """Run ``first`` paused in the middle of settling, then ``second``.

        The first call is paused after it has locked the attempt, while it is
        computing the result. Returns ``(results, second_waited)``.
        """
        reached, release = threading.Event(), threading.Event()
        original = scoring.settle

        def paused(*args, **kwargs):
            if threading.current_thread().name == "first" and not reached.is_set():
                reached.set()
                release.wait(10)
            return original(*args, **kwargs)

        results = {}

        def run(name, call):
            conn = migrate.connect(self.conninfo)
            try:
                results[name] = ("ok", call(conn))
            except Exception as exc:  # the outcome is asserted by the test
                results[name] = ("error", exc)
            finally:
                conn.close()

        with mock.patch.object(scoring, "settle", paused):
            one = threading.Thread(target=run, args=("first", first), name="first")
            one.start()
            self.assertTrue(reached.wait(10), "first call never reached its pause")
            two = threading.Thread(target=run, args=("second", second), name="second")
            two.start()
            two.join(0.5)
            second_waited = two.is_alive()
            release.set()
            one.join(10)
            two.join(10)
        self.assertFalse(one.is_alive() or two.is_alive(), "a call never finished")
        return results, second_waited

    def _ended(self, points):
        account_id = self._account(points=points)
        attempt_id = self._start(account_id)
        self._play(attempt_id, [CORRECT] * 15)
        return account_id, attempt_id

    def test_two_settlements_of_one_attempt_apply_the_points_once(self):
        account_id, attempt_id = self._ended(500)

        def settle(conn):
            return settlement.settle_attempt(conn, attempt_id, clock=self.clock)

        results, waited = self._race(settle, settle)
        self.assertTrue(waited, "the second settlement did not wait for the first")
        self.assertEqual(results["first"][0], "ok", results["first"])
        self.assertEqual(results["second"][0], "ok", results["second"])
        self.assertEqual(results["second"][1], results["first"][1])
        self.assertEqual(self._points(account_id), 800)  # +300 once, not twice
        self.assertEqual(self._count("settlements", attempt_id), 1)
        self.assertEqual(self._count("balance_history", attempt_id), 1)

    def test_sweep_and_a_direct_settlement_apply_the_points_once(self):
        account_id, attempt_id = self._ended(500)
        results, waited = self._race(
            lambda conn: settlement.settle_attempt(conn, attempt_id, clock=self.clock),
            lambda conn: settlement.settle_pending(conn, clock=self.clock),
        )
        self.assertTrue(waited, "the sweep did not wait for the settlement in progress")
        self.assertEqual(results["second"], ("ok", 0))  # nothing left for the sweep
        self.assertEqual(self._points(account_id), 800)
        self.assertEqual(self._count("settlements", attempt_id), 1)


if __name__ == "__main__":
    unittest.main()
