"""Concurrent requests for one ranked attempt are handled one at a time
(issue #8, slice 7).

Each test runs two engine calls on two database connections and two threads.
The first call is paused in the middle of its work, after it has locked the
attempt. The second call is then started; it must wait for the first to
finish and then act on the first call's committed result.
"""
import tempfile
import threading
from datetime import datetime, timezone
import unittest
from unittest import mock

from backend.db import migrate, settings
from backend.ranked import engine
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

CORRECT = "GOLD"
WRONG = "YELLOW"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RankedRaceTests(unittest.TestCase):
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
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES ('race_player', 'race_player', 'X00001') RETURNING id",
        )
        self.conn.commit()
        self.account_id = row["id"]

    # --- helpers ---

    def _start(self):
        return engine.start_attempt(
            self.conn, self.account_id, clock=self.clock, bank=self.bank
        )

    def _answer(self, conn, attempt_id, seq, choice):
        return engine.submit_answer(
            conn, attempt_id, seq, choice, clock=self.clock, bank=self.bank
        )

    def _play_to(self, attempt_id, last_seq):
        """Answer and advance until question ``last_seq`` is the live one."""
        for seq in range(1, last_seq):
            self._answer(self.conn, attempt_id, seq, CORRECT)
            engine.advance(self.conn, attempt_id, clock=self.clock)

    def _race(self, first, second, pause_in):
        """Run ``first`` paused inside ``engine.<pause_in>``, then ``second``.

        Returns ``(results, second_waited)``. ``results`` maps "first" and
        "second" to ``("ok", value)`` or ``("error", exception)``;
        ``second_waited`` says whether the second call was still blocked
        while the first was paused.
        """
        reached, release = threading.Event(), threading.Event()
        original = getattr(engine, pause_in)

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

        with mock.patch.object(engine, pause_in, paused):
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

    def _answer_of(self, attempt_id, seq):
        row = migrate.fetch_one(
            self.conn,
            "SELECT answer FROM attempt_answers WHERE attempt_id = %s AND seq = %s",
            (attempt_id, seq),
        )
        self.conn.commit()
        return row["answer"] if row else None

    def _ending(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT state, final_outcome FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return (row["state"], row["final_outcome"])

    def _rows(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_answers WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return row["n"]

    # --- races ---

    def test_two_answers_keep_the_first_and_agree(self):
        attempt_id = self._start()
        results, waited = self._race(
            lambda conn: self._answer(conn, attempt_id, 1, CORRECT),
            lambda conn: self._answer(conn, attempt_id, 1, WRONG),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "the second answer did not wait for the first")
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")
        self.assertEqual(results["first"][1].outcome, "correct")
        # the second caller is told the stored result, not its own grading
        self.assertEqual(results["second"][0], "ok", results["second"])
        self.assertEqual(results["second"][1].outcome, "correct")

    def test_two_next_requests_send_exactly_one_question(self):
        attempt_id = self._start()
        self._answer(self.conn, attempt_id, 1, CORRECT)
        results, waited = self._race(
            lambda conn: engine.advance(conn, attempt_id, clock=self.clock),
            lambda conn: engine.advance(conn, attempt_id, clock=self.clock),
            pause_in="_send_question",
        )
        self.assertTrue(waited, "the second Next did not wait for the first")
        self.assertEqual(results["first"][0], "ok", results["first"])
        self.assertEqual(results["first"][1].next_seq, 2)
        self.assertEqual(results["second"][0], "error")
        self.assertIsInstance(results["second"][1], engine.NotAnsweredError)
        self.assertEqual(self._rows(attempt_id), 2)

    def test_quit_waits_for_an_answer_in_progress(self):
        attempt_id = self._start()
        results, waited = self._race(
            lambda conn: self._answer(conn, attempt_id, 1, CORRECT),
            lambda conn: engine.quit_attempt(conn, attempt_id, clock=self.clock),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "Quit did not wait for the answer in progress")
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")
        self.assertEqual(results["second"], ("ok", "quit"))
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "quit"))

    def test_quit_and_final_answer_record_one_ending(self):
        attempt_id = self._start()
        self._play_to(attempt_id, 15)
        results, waited = self._race(
            lambda conn: self._answer(conn, attempt_id, 15, CORRECT),
            lambda conn: engine.quit_attempt(conn, attempt_id, clock=self.clock),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "Quit did not wait for the final answer")
        self.assertTrue(results["first"][1].finished)
        # the final answer completed the attempt; the Quit reports that ending
        self.assertEqual(results["second"], ("ok", "completed"))
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "completed"))

    def test_two_starts_admit_exactly_one_attempt(self):
        def start(conn):
            return engine.start_attempt(
                conn, self.account_id, clock=self.clock, bank=self.bank
            )

        results, _ = self._race(start, start, pause_in="_send_question")
        outcomes = sorted(kind for kind, _ in results.values())
        self.assertEqual(outcomes, ["error", "ok"], results)
        error = next(value for kind, value in results.values() if kind == "error")
        self.assertIsInstance(error, engine.ActiveAttemptExistsError)
        row = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempts WHERE account_id = %s",
            (self.account_id,),
        )
        self.assertEqual(row["n"], 1)

    def test_return_just_inside_grace_beats_a_concurrent_expiry_sweep(self):
        attempt_id = self._start()
        self.clock.advance(17.9)  # silent, but back before the 18s grace deadline
        # the sweep's clock is already past that old grace deadline
        late = FakeClock(self.clock.now())
        late.advance(1)
        results, waited = self._race(
            lambda conn: engine.heartbeat(conn, attempt_id, clock=self.clock),
            lambda conn: engine.expire_stale_attempts(conn, clock=late),
            pause_in="_complete_if_final_question_timed_out",
        )
        self.assertTrue(waited, "the sweep did not wait for the return in progress")
        self.assertEqual(results["first"][0], "ok", results["first"])
        self.assertEqual(results["second"][0], "ok", results["second"])
        # the sweep saw the new heartbeat: the attempt was not disconnected
        self.assertEqual(self._ending(attempt_id), ("active", None))

    def _season_id(self, attempt_id):
        row = migrate.fetch_one(
            self.conn, "SELECT season_id FROM attempts WHERE id = %s", (attempt_id,)
        )
        self.conn.commit()
        return row["season_id"]

    def test_season_close_waits_for_an_answer_in_progress(self):
        attempt_id = self._start()
        season_id = self._season_id(attempt_id)
        results, waited = self._race(
            lambda conn: self._answer(conn, attempt_id, 1, CORRECT),
            lambda conn: engine.end_attempts_for_season_close(
                conn, season_id, clock=self.clock
            ),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "season close did not wait for the answer in progress")
        # the answer was accepted first, then the cutover ended the attempt once
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")
        self.assertEqual(results["second"], ("ok", 1))
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "season_close"))

    def test_outage_void_waits_for_an_answer_in_progress(self):
        attempt_id = self._start()
        now = self.clock.now()
        results, waited = self._race(
            lambda conn: self._answer(conn, attempt_id, 1, CORRECT),
            lambda conn: engine.void_attempts_for_outage(
                conn, outage_start=now, outage_end=now
            ),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "outage void did not wait for the answer in progress")
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")  # kept as history
        self.assertEqual(results["second"], ("ok", 1))
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "outage_void"))

    def test_an_ended_attempt_keeps_its_one_ending(self):
        attempt_id = self._start()
        season_id = self._season_id(attempt_id)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        # every later ending finds the attempt already ended and changes nothing
        self.clock.advance(60)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        self.assertEqual(
            engine.end_attempts_for_season_close(self.conn, season_id, clock=self.clock), 0
        )
        self.assertEqual(engine.void_attempts_for_launch(self.conn, season_id), 0)
        self.assertEqual(
            engine.quit_attempt(self.conn, attempt_id, clock=self.clock), "quit"
        )
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "quit"))

    # --- no question without a running deadline ---

    def test_no_next_question_exists_before_next_is_accepted(self):
        attempt_id = self._start()
        self._answer(self.conn, attempt_id, 1, CORRECT)
        view = engine.current_question(
            self.conn, attempt_id, clock=self.clock, bank=self.bank
        )
        self.assertIsNone(view)  # feedback is showing: nothing is live
        self.assertEqual(self._rows(attempt_id), 1)  # question 2 was not created


if __name__ == "__main__":
    unittest.main()
