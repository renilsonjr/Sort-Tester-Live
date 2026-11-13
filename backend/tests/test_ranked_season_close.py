"""Season close: finishing window, ending, settlement and freeze
(issue #23, slice 3)."""
import tempfile
import threading
from datetime import datetime, timedelta, timezone
import unittest
from unittest import mock

from backend.db import migrate, settings
from backend.ranked import engine, scoring, season_close, seasons
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
END = T0 + timedelta(hours=1)
WINDOW = timedelta(seconds=300)
CORRECT = "GOLD"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SeasonCloseTests(unittest.TestCase):
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
        # the clock starts one minute before the season's scheduled end
        self.clock = FakeClock(END - timedelta(seconds=60))
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak Season', %s, %s) RETURNING id",
            (T0 - timedelta(days=1), END),
        )["id"]
        self.conn.commit()
        self._accounts = 0

    # --- helpers ---

    def _account(self, points=500):
        self._accounts += 1
        tag = f"E{self._accounts:05d}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"close_{tag.lower()}", f"close_{tag.lower()}", tag),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
            (row["id"], points),
        )
        self.conn.commit()
        return row["id"]

    def _start(self, account_id):
        return engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )

    def _answer(self, attempt_id, seq, conn=None):
        return engine.submit_answer(
            conn or self.conn, attempt_id, seq, CORRECT, clock=self.clock, bank=self.bank
        )

    def _keep_alive_until(self, attempt_id, moment):
        """Advance the clock to ``moment``, sending heartbeats on the way."""
        while self.clock.now() < moment:
            step = min(2.0, (moment - self.clock.now()).total_seconds())
            self.clock.advance(step)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)

    def _go_to(self, moment):
        self.clock.advance((moment - self.clock.now()).total_seconds())

    def _finish(self, conn=None):
        return season_close.finish_season(conn or self.conn, self.season, clock=self.clock)

    def _one(self, sql, params=()):
        row = migrate.fetch_one(self.conn, sql, params)
        self.conn.commit()
        return row

    def _attempt(self, attempt_id):
        row = self._one(
            "SELECT state, final_outcome FROM attempts WHERE id = %s", (attempt_id,)
        )
        return (row["state"], row["final_outcome"])

    def _points(self, account_id):
        return self._one(
            "SELECT current_points FROM balances WHERE account_id = %s", (account_id,)
        )["current_points"]

    def _season_row(self):
        return self._one(
            "SELECT closed_at, frozen_at FROM seasons WHERE id = %s", (self.season,)
        )

    def _status(self):
        status = seasons.season_status(self.conn, self.season, self.clock.now()).status
        self.conn.commit()
        return status

    def _first_difficulty(self, attempt_id):
        return self._one(
            "SELECT qv.difficulty FROM attempt_answers aa"
            " JOIN question_versions qv ON qv.id = aa.question_version_id"
            " WHERE aa.attempt_id = %s AND aa.seq = 1",
            (attempt_id,),
        )["difficulty"]

    # --- before the window is over ---

    def test_nothing_happens_before_the_end(self):
        attempt_id = self._start(self._account())
        self.assertFalse(self._finish())
        self.assertEqual(self._attempt(attempt_id), ("active", None))
        self.assertIsNone(self._season_row()["frozen_at"])

    def test_nothing_happens_during_the_finishing_window(self):
        attempt_id = self._start(self._account())
        self._answer(attempt_id, 1)
        self._keep_alive_until(attempt_id, END + WINDOW - timedelta(seconds=1))
        self.assertEqual(self._status(), "finishing")
        self.assertFalse(self._finish())
        self.assertEqual(self._attempt(attempt_id), ("active", None))
        # the attempt is still playable inside the window
        self.assertEqual(
            engine.advance(self.conn, attempt_id, clock=self.clock).next_seq, 2
        )

    # --- when the window is over ---

    def test_finish_ends_scores_and_freezes(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._answer(attempt_id, 1)
        # still playing: question 2 is sent five seconds before the window ends
        self._keep_alive_until(attempt_id, END + WINDOW - timedelta(seconds=5))
        engine.advance(self.conn, attempt_id, clock=self.clock)
        self._go_to(END + WINDOW)

        self.assertTrue(self._finish())

        self.assertEqual(self._attempt(attempt_id), ("finalized", "season_close"))
        live = self._one(
            "SELECT answer FROM attempt_answers WHERE attempt_id = %s AND seq = 2",
            (attempt_id,),
        )
        self.assertIsNone(live["answer"])  # inside its deadline: not deducted
        gained = scoring.answer_points(self._first_difficulty(attempt_id), "correct")
        self.assertEqual(self._points(account_id), 500 + gained)  # no Quit penalty
        season = self._season_row()
        self.assertEqual(season["closed_at"], END)
        self.assertEqual(season["frozen_at"], END + WINDOW)
        self.assertEqual(self._status(), "frozen")

    def test_attempt_silent_since_before_the_end_is_a_disconnect(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)  # then nothing more is heard
        self._go_to(END + WINDOW)
        self.assertTrue(self._finish())
        self.assertEqual(self._attempt(attempt_id), ("finalized", "disconnect"))
        self.assertLess(self._points(account_id), 500)  # the timed-out question

    def test_attempt_ended_before_the_window_closed_keeps_its_real_result(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)  # not yet settled
        self._go_to(END + WINDOW)
        self.assertTrue(self._finish())
        self.assertEqual(self._attempt(attempt_id), ("finalized", "quit"))
        self.assertEqual(self._points(account_id), 490)

    def test_season_with_no_attempts_still_freezes(self):
        self._go_to(END + WINDOW)
        self.assertTrue(self._finish())
        self.assertEqual(self._status(), "frozen")

    # --- exactly once ---

    def test_finishing_twice_changes_nothing(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._go_to(END + WINDOW)
        self.assertTrue(self._finish())
        points, frozen_at = self._points(account_id), self._season_row()["frozen_at"]
        self.clock.advance(3600)
        self.assertFalse(self._finish())
        self.assertEqual(self._points(account_id), points)
        self.assertEqual(self._season_row()["frozen_at"], frozen_at)
        self.assertEqual(self._attempt(attempt_id)[0], "finalized")

    def test_an_interrupted_finish_completes_when_run_again(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._answer(attempt_id, 1)
        self._keep_alive_until(attempt_id, END + WINDOW)
        # as if the process stopped after ending the attempts, before settling
        engine.end_attempts_for_season_close(self.conn, self.season, clock=self.clock)
        self.assertEqual(self._attempt(attempt_id), ("terminal_pending", "season_close"))
        self.assertIsNone(self._season_row()["frozen_at"])

        self.assertTrue(self._finish())
        self.assertEqual(self._attempt(attempt_id), ("finalized", "season_close"))
        self.assertIsNotNone(self._season_row()["frozen_at"])

    def test_no_attempt_can_start_after_the_freeze(self):
        self._go_to(END + WINDOW)
        self._finish()
        with self.assertRaises(engine.NoOpenSeasonError):
            self._start(self._account())

    # --- the sweep ---

    def test_finish_due_seasons_freezes_only_what_is_due(self):
        other = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Later Season', %s, %s) RETURNING id",
            (T0 - timedelta(days=1), END + timedelta(days=30)),
        )["id"]
        self.conn.commit()
        self.assertEqual(season_close.finish_due_seasons(self.conn, clock=self.clock), 0)
        self._go_to(END + WINDOW)
        self.assertEqual(season_close.finish_due_seasons(self.conn, clock=self.clock), 1)
        self.assertEqual(season_close.finish_due_seasons(self.conn, clock=self.clock), 0)
        self.assertIsNotNone(self._season_row()["frozen_at"])
        later = self._one("SELECT frozen_at FROM seasons WHERE id = %s", (other,))
        self.assertIsNone(later["frozen_at"])

    # --- race ---

    def test_finish_waits_for_an_answer_in_progress(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        # the player is still connected when the window ends, and a request of
        # theirs is being saved at that very moment
        self._keep_alive_until(attempt_id, END + WINDOW)
        reached, release = threading.Event(), threading.Event()
        original = engine._record_answer

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

        with mock.patch.object(engine, "_record_answer", paused):
            one = threading.Thread(
                target=run, name="first",
                args=("first", lambda conn: self._answer(attempt_id, 1, conn=conn)),
            )
            one.start()
            self.assertTrue(reached.wait(10), "the answer never reached its pause")
            two = threading.Thread(
                target=run, name="second",
                args=("second", lambda conn: self._finish(conn=conn)),
            )
            two.start()
            two.join(0.5)
            waited = two.is_alive()
            release.set()
            one.join(10)
            two.join(10)
        self.assertTrue(waited, "finish did not wait for the answer in progress")
        self.assertEqual(results["second"], ("ok", True), results)
        self.assertEqual(results["first"][0], "ok", results)
        # the request in progress was saved first, then the season ended the attempt once
        self.assertEqual(self._attempt(attempt_id), ("finalized", "season_close"))
        self.assertIsNotNone(self._season_row()["frozen_at"])


if __name__ == "__main__":
    unittest.main()
