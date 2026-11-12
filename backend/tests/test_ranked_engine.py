"""Ranked attempt engine core happy path (issue #8, piece 3)."""
import tempfile
from datetime import datetime, timedelta, timezone
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
        view = engine.current_question(
            self.conn, attempt_id, clock=self.clock, bank=self.bank
        )
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
        # the attempt has ended: every further call is refused
        with self.assertRaises(engine.AttemptEndedError):
            engine.current_question(
                self.conn, attempt_id, clock=self.clock, bank=self.bank
            )
        with self.assertRaises(engine.AttemptEndedError):
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)

    # --- heartbeat, loss, grace and disconnect (slice 2, piece B) ---

    def _start(self):
        self._open_season()
        account_id = self._make_account()
        attempt_id = engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )
        return account_id, attempt_id

    def _attempt_row(self, attempt_id):
        return migrate.fetch_one(
            self.conn,
            "SELECT state, final_outcome, grace_deadline_at, last_heartbeat_at"
            " FROM attempts WHERE id = %s",
            (attempt_id,),
        )

    def test_start_records_the_first_heartbeat(self):
        started = self.clock.now()
        _, attempt_id = self._start()
        self.assertEqual(self._attempt_row(attempt_id)["last_heartbeat_at"], started)

    def test_heartbeats_keep_the_attempt_alive(self):
        _, attempt_id = self._start()
        for _ in range(25):  # 25 seconds, well past 3s loss + 15s grace
            self.clock.advance(1)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        row = self._attempt_row(attempt_id)
        self.assertEqual(row["state"], "active")
        self.assertEqual(row["last_heartbeat_at"], self.clock.now())

    def test_return_just_before_grace_deadline_continues(self):
        started = self.clock.now()
        _, attempt_id = self._start()
        self.clock.advance(17.9)  # silent, but back before the 18s deadline
        engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(self._attempt_row(attempt_id)["state"], "active")
        # the question clock kept running while the player was away
        view = engine.current_question(
            self.conn, attempt_id, clock=self.clock, bank=self.bank
        )
        self.assertEqual((view.deadline_at - started).total_seconds(), 10)
        result = engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        self.assertEqual(result.outcome, "timeout")

    def test_call_at_grace_deadline_ends_as_disconnect(self):
        _, attempt_id = self._start()
        self.clock.advance(18)  # exactly the grace deadline: finalization wins
        with self.assertRaises(engine.AttemptEndedError):
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        row = self._attempt_row(attempt_id)
        self.assertEqual((row["state"], row["final_outcome"]),
                         ("terminal_pending", "disconnect"))
        self.assertEqual(self._answer_of(attempt_id, 1), "timeout")
        count = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_answers WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual(count["n"], 1)  # questions never sent get no row
        with self.assertRaises(engine.AttemptEndedError):
            engine.submit_answer(
                self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
            )
        with self.assertRaises(engine.AttemptEndedError):
            engine.advance(self.conn, attempt_id, clock=self.clock)

    def test_answering_counts_as_activity(self):
        _, attempt_id = self._start()
        self.clock.advance(2)
        engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        self.clock.advance(17)  # 19s after start, but only 17s after the answer
        adv = engine.advance(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(adv.next_seq, 2)

    def test_expire_marks_grace_then_finalizes(self):
        started = self.clock.now()
        _, attempt_id = self._start()
        self.clock.advance(5)  # past the 3s loss, inside grace
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        row = self._attempt_row(attempt_id)
        self.assertEqual(row["state"], "grace")
        self.assertEqual((row["grace_deadline_at"] - started).total_seconds(), 18)
        self.clock.advance(13)  # now at the grace deadline
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        row = self._attempt_row(attempt_id)
        self.assertEqual((row["state"], row["final_outcome"]),
                         ("terminal_pending", "disconnect"))
        self.assertEqual(self._answer_of(attempt_id, 1), "timeout")

    def test_return_during_grace_goes_back_to_active(self):
        _, attempt_id = self._start()
        self.clock.advance(5)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        row = self._attempt_row(attempt_id)
        self.assertEqual(row["state"], "active")
        self.assertIsNone(row["grace_deadline_at"])

    def test_expire_leaves_a_connected_attempt_alone(self):
        _, attempt_id = self._start()
        self.clock.advance(2)  # still inside the 3s heartbeat window
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        self.assertEqual(self._attempt_row(attempt_id)["state"], "active")

    def test_starting_again_expires_an_abandoned_attempt(self):
        account_id, old_id = self._start()
        self.clock.advance(60)  # walked away long ago
        # the old attempt is closed as a disconnect, but it still awaits
        # scoring (#9), so the account cannot start a new one yet
        with self.assertRaises(engine.ActiveAttemptExistsError):
            engine.start_attempt(
                self.conn, account_id, clock=self.clock, bank=self.bank
            )
        row = self._attempt_row(old_id)
        self.assertEqual((row["state"], row["final_outcome"]),
                         ("terminal_pending", "disconnect"))
        # stand in for #9 settling the old attempt
        migrate.execute(
            self.conn,
            "UPDATE attempts SET state = 'finalized', settled_at = %s WHERE id = %s",
            (self.clock.now(), old_id),
        )
        self.conn.commit()
        new_id = engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )
        self.assertNotEqual(new_id, old_id)

    # --- explicit Quit (slice 3, piece A) ---

    def test_quit_on_a_live_question_leaves_it_unanswered(self):
        _, attempt_id = self._start()
        self.clock.advance(2)
        outcome = engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(outcome, "quit")
        row = self._attempt_row(attempt_id)
        self.assertEqual((row["state"], row["final_outcome"]),
                         ("terminal_pending", "quit"))
        self.assertIsNone(self._answer_of(attempt_id, 1))  # not deducted

    def test_quit_after_the_question_deadline_records_a_timeout(self):
        _, attempt_id = self._start()
        self.clock.advance(11)  # the question already ran out; grace has not
        outcome = engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(outcome, "quit")
        self.assertEqual(self._answer_of(attempt_id, 1), "timeout")

    def test_quit_keeps_earlier_answers_and_sends_nothing_more(self):
        _, attempt_id = self._start()
        self._play_one(attempt_id, 1)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")
        count = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_answers WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual(count["n"], 2)

    def test_quit_twice_returns_the_same_outcome(self):
        _, attempt_id = self._start()
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.clock.advance(30)
        again = engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(again, "quit")
        self.assertIsNone(self._answer_of(attempt_id, 1))  # nothing rewritten
        with self.assertRaises(engine.AttemptEndedError):
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)

    def test_quit_after_grace_expiry_is_a_disconnect(self):
        _, attempt_id = self._start()
        self.clock.advance(18)
        outcome = engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(outcome, "disconnect")
        self.assertEqual(self._attempt_row(attempt_id)["final_outcome"], "disconnect")

    def test_quit_on_a_completed_attempt_stays_completed(self):
        _, attempt_id = self._start()
        for seq in range(1, 16):
            self._play_one(attempt_id, seq)
        outcome = engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(outcome, "completed")
        self.assertEqual(self._attempt_row(attempt_id)["final_outcome"], "completed")

    # --- confirmed-outage void (slice 3, piece B) ---

    def _void(self, start_offset, end_offset):
        """Void for an outage given as seconds relative to the clock's start."""
        return engine.void_attempts_for_outage(
            self.conn,
            outage_start=self.t0 + timedelta(seconds=start_offset),
            outage_end=self.t0 + timedelta(seconds=end_offset),
        )

    def _ending(self, attempt_id):
        row = self._attempt_row(attempt_id)
        return (row["state"], row["final_outcome"])

    def test_start_records_the_engine_clock_as_started_at(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        row = migrate.fetch_one(
            self.conn, "SELECT started_at FROM attempts WHERE id = %s", (attempt_id,)
        )
        self.assertEqual(row["started_at"], self.t0)

    def test_outage_voids_a_running_attempt_and_keeps_its_answers(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        self.assertEqual(self._void(5, 20), 1)
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "outage_void"))
        self.assertEqual(self._answer_of(attempt_id, 1), "correct")  # history kept
        with self.assertRaises(engine.AttemptEndedError):
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)

    def test_outage_before_the_attempt_started_does_not_void_it(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        self.assertEqual(self._void(-60, -10), 0)
        self.assertEqual(self._ending(attempt_id), ("active", None))

    def test_outage_reclassifies_an_overlapping_unsettled_disconnect(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        self.clock.advance(18)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "disconnect"))
        # the silence ran from 0s to 18s; the outage covered part of it
        self.assertEqual(self._void(2, 30), 1)
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "outage_void"))

    def test_outage_leaves_a_disconnect_it_does_not_overlap(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        self.clock.advance(18)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        self.assertEqual(self._void(19, 40), 0)   # outage began after the grace deadline
        self.assertEqual(self._void(-30, -1), 0)  # outage ended before the silence began
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "disconnect"))

    def test_outage_leaves_a_quit_attempt(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(self._void(-5, 30), 0)
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "quit"))

    def test_outage_leaves_a_completed_attempt(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        for seq in range(1, 16):
            self._play_one(attempt_id, seq)
        self.assertEqual(self._void(-5, 30), 0)
        self.assertEqual(self._ending(attempt_id), ("terminal_pending", "completed"))

    def test_outage_never_reverses_a_settled_attempt(self):
        self.t0 = self.clock.now()
        _, attempt_id = self._start()
        self.clock.advance(18)
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        migrate.execute(  # stand in for #9 settling the disconnect
            self.conn,
            "UPDATE attempts SET state = 'finalized', settled_at = %s WHERE id = %s",
            (self.clock.now(), attempt_id),
        )
        self.conn.commit()
        self.assertEqual(self._void(2, 30), 0)
        self.assertEqual(self._ending(attempt_id), ("finalized", "disconnect"))

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

    def _answer_of(self, attempt_id, seq):
        row = migrate.fetch_one(
            self.conn,
            "SELECT answer FROM attempt_answers WHERE attempt_id = %s AND seq = %s",
            (attempt_id, seq),
        )
        return row["answer"] if row else None

    def test_late_answer_is_recorded_as_timeout(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        self.clock.advance(11)  # past the 10-second deadline
        result = engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        self.assertFalse(result.correct)
        self.assertEqual(result.outcome, "timeout")
        self.assertEqual(self._answer_of(attempt_id, 1), "timeout")
        # a later submit cannot rewrite the timeout
        again = engine.submit_answer(
            self.conn, attempt_id, 1, CORRECT, clock=self.clock, bank=self.bank
        )
        self.assertEqual(again.outcome, "timeout")

    def test_advance_moves_past_a_timed_out_question(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        self.clock.advance(11)
        adv = engine.advance(self.conn, attempt_id, clock=self.clock)
        self.assertFalse(adv.finished)
        self.assertEqual(adv.next_seq, 2)
        self.assertEqual(self._answer_of(attempt_id, 1), "timeout")

    def test_all_timeouts_still_finish_the_attempt(self):
        self._open_season()
        attempt_id = engine.start_attempt(
            self.conn, self._make_account(), clock=self.clock, bank=self.bank
        )
        adv = None
        for _ in range(15):
            self.clock.advance(11)
            adv = engine.advance(self.conn, attempt_id, clock=self.clock)
        self.assertTrue(adv.finished)
        row = migrate.fetch_one(
            self.conn,
            "SELECT state, final_outcome FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        self.assertEqual((row["state"], row["final_outcome"]),
                         ("terminal_pending", "completed"))
        count = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_answers"
            " WHERE attempt_id = %s AND answer = 'timeout'",
            (attempt_id,),
        )
        self.assertEqual(count["n"], 15)

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
