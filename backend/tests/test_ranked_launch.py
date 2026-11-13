"""Official season launch, exactly once (issue #23, slice 2)."""
import tempfile
import threading
from datetime import datetime, timedelta, timezone
import unittest
from unittest import mock

from backend.db import migrate, settings
from backend.ranked import engine, launch, seasons, settlement
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
END = T0 + timedelta(days=30)
CORRECT = "GOLD"
WRONG = "YELLOW"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class LaunchTests(unittest.TestCase):
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
        self.clock = FakeClock(T0)
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())
        self.pre = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at)"
            " VALUES ('pre_season', 'Pre-Season', %s) RETURNING id",
            (T0 - timedelta(days=1),),
        )["id"]
        self.conn.commit()
        self._accounts = 0

    # --- helpers ---

    def _account(self, points=None):
        self._accounts += 1
        tag = f"L{self._accounts:05d}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"launch_{tag.lower()}", f"launch_{tag.lower()}", tag),
        )
        if points is not None:
            migrate.execute(
                self.conn,
                "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
                (row["id"], points),
            )
        self.conn.commit()
        return row["id"]

    def _start(self, account_id, conn=None):
        return engine.start_attempt(
            conn or self.conn, account_id, clock=self.clock, bank=self.bank
        )

    def _answer(self, attempt_id, seq, choice, conn=None):
        return engine.submit_answer(
            conn or self.conn, attempt_id, seq, choice, clock=self.clock, bank=self.bank
        )

    def _play_all(self, attempt_id, choice=CORRECT):
        for seq in range(1, 16):
            if not self._answer(attempt_id, seq, choice).finished:
                engine.advance(self.conn, attempt_id, clock=self.clock)

    def _launch(self, conn=None, **overrides):
        kwargs = {"label": "Peak Season 2026", "clock": self.clock, "closes_at": END}
        kwargs.update(overrides)
        return launch.launch_official_season(conn or self.conn, **kwargs)

    def _one(self, sql, params=()):
        row = migrate.fetch_one(self.conn, sql, params)
        self.conn.commit()
        return row

    def _points(self, account_id):
        return self._one(
            "SELECT current_points FROM balances WHERE account_id = %s", (account_id,)
        )["current_points"]

    def _attempt(self, attempt_id):
        row = self._one(
            "SELECT state, final_outcome, season_id FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        return (row["state"], row["final_outcome"])

    def _official_count(self):
        return self._one("SELECT COUNT(*) AS n FROM seasons WHERE phase = 'official'")["n"]

    # --- what launch does ---

    def test_launch_voids_resets_freezes_and_opens_the_official_season(self):
        player = self._account(points=850)
        bystander = self._account(points=700)  # no attempt at all
        attempt_id = self._start(player)
        self._answer(attempt_id, 1, CORRECT)

        official = self._launch()

        self.assertEqual(self._attempt(attempt_id), ("finalized", "launch_reset"))
        kept = self._one(
            "SELECT answer FROM attempt_answers WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        self.assertEqual(kept["answer"], "correct")  # history is not rewritten
        settled = self._one(
            "SELECT adjustment, season_id FROM settlements WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.assertEqual((settled["adjustment"], settled["season_id"]), (0, self.pre))
        self.assertEqual(self._points(player), 0)
        self.assertEqual(self._points(bystander), 0)
        pre = self._one(
            "SELECT closed_at, frozen_at FROM seasons WHERE id = %s", (self.pre,)
        )
        self.assertEqual((pre["closed_at"], pre["frozen_at"]), (T0, T0))
        new = self._one(
            "SELECT phase, label, opened_at, closes_at FROM seasons WHERE id = %s",
            (official,),
        )
        self.assertEqual(
            (new["phase"], new["label"], new["opened_at"], new["closes_at"]),
            ("official", "Peak Season 2026", T0, END),
        )
        self.assertEqual(seasons.admitting_season(self.conn, T0), official)

    def test_launch_voids_an_attempt_in_connection_grace(self):
        player = self._account(points=850)
        attempt_id = self._start(player)
        self.clock.advance(5)  # silent past the 3s loss, inside the 15s grace
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        self.assertEqual(self._attempt(attempt_id), ("grace", None))

        self._launch()

        self.assertEqual(self._attempt(attempt_id), ("finalized", "launch_reset"))
        settled = self._one(
            "SELECT adjustment FROM settlements WHERE attempt_id = %s", (attempt_id,)
        )
        self.assertEqual(settled["adjustment"], 0)  # no timeout deduction either
        self.assertEqual(self._points(player), 0)

    def test_an_attempt_ended_just_before_launch_keeps_its_real_result(self):
        player = self._account(points=100)
        attempt_id = self._start(player)
        self._play_all(attempt_id)  # completed, not yet settled
        self._launch()
        history = self._one(
            "SELECT adjustment, points_before, points_after FROM balance_history"
            " WHERE settlement_id = %s",
            (attempt_id,),
        )
        self.assertEqual(
            (history["adjustment"], history["points_before"], history["points_after"]),
            (300, 100, 400),
        )
        self.assertEqual(self._attempt(attempt_id), ("finalized", "completed"))
        self.assertEqual(self._points(player), 0)  # then everyone is reset

    def test_pre_season_history_is_preserved(self):
        player = self._account()
        attempt_id = self._start(player)
        self._play_all(attempt_id)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self._launch()
        counts = self._one(
            "SELECT (SELECT COUNT(*) FROM balance_history) AS history,"
            " (SELECT COUNT(*) FROM settlements) AS settlements,"
            " (SELECT COUNT(*) FROM attempt_answers) AS answers,"
            " (SELECT COUNT(*) FROM accounts) AS accounts"
        )
        self.assertEqual(
            (counts["history"], counts["settlements"], counts["answers"], counts["accounts"]),
            (1, 1, 15, 1),
        )

    def test_default_end_is_new_years_eve_2359_eastern(self):
        self.assertEqual(
            launch.DEFAULT_OFFICIAL_END,
            datetime(2027, 1, 1, 4, 59, 0, tzinfo=timezone.utc),
        )
        official = launch.launch_official_season(
            self.conn, label="Peak Season 2026", clock=self.clock
        )
        row = self._one("SELECT closes_at FROM seasons WHERE id = %s", (official,))
        self.assertEqual(row["closes_at"], launch.DEFAULT_OFFICIAL_END)

    def test_official_play_starts_from_zero_after_launch(self):
        player = self._account(points=850)
        official = self._launch()
        attempt_id = self._start(player)
        self.assertEqual(
            self._one("SELECT season_id FROM attempts WHERE id = %s", (attempt_id,))["season_id"],
            official,
        )
        self._play_all(attempt_id)
        result = settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual((result.points_before, result.points_after), (0, 300))

    # --- exactly once ---

    def test_a_second_launch_is_refused_and_changes_nothing(self):
        player = self._account(points=850)
        self._launch()
        attempt_id = self._start(player)  # official play after launch
        self._play_all(attempt_id)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        with self.assertRaises(launch.AlreadyLaunchedError):
            self._launch(label="Another Season")
        self.conn.rollback()
        self.assertEqual(self._official_count(), 1)
        self.assertEqual(self._points(player), 300)  # not reset again

    def test_an_interrupted_launch_completes_when_run_again(self):
        player = self._account(points=850)
        attempt_id = self._start(player)
        # as if the process stopped after closing the Pre-Season and voiding
        migrate.execute(
            self.conn, "UPDATE seasons SET closed_at = %s WHERE id = %s", (T0, self.pre)
        )
        self.conn.commit()
        engine.void_attempts_for_launch(self.conn, self.pre)
        self.assertEqual(self._attempt(attempt_id), ("terminal_pending", "launch_reset"))
        self.assertEqual(self._points(player), 850)  # nothing was reset yet

        self._launch()
        self.assertEqual(self._attempt(attempt_id), ("finalized", "launch_reset"))
        self.assertEqual(self._points(player), 0)
        self.assertEqual(self._official_count(), 1)

    # --- refusals ---

    def _assert_nothing_launched(self, player):
        self.conn.rollback()
        self.assertEqual(self._official_count(), 0)
        self.assertEqual(self._points(player), 850)
        self.assertEqual(seasons.admitting_season(self.conn, T0), self.pre)

    def test_blank_label_is_refused(self):
        player = self._account(points=850)
        with self.assertRaises(launch.InvalidLaunchError):
            self._launch(label="   ")
        self._assert_nothing_launched(player)

    def test_end_time_not_in_the_future_is_refused(self):
        player = self._account(points=850)
        with self.assertRaises(launch.InvalidLaunchError):
            self._launch(closes_at=T0)
        self._assert_nothing_launched(player)

    def test_launch_without_a_pre_season_is_refused(self):
        migrate.execute(self.conn, "DELETE FROM seasons")
        self.conn.commit()
        with self.assertRaises(launch.NoPreSeasonError):
            self._launch()

    # --- phase ownership ---

    def test_settling_an_attempt_of_a_frozen_season_applies_zero(self):
        player = self._account(points=500)
        attempt_id = self._start(player)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)  # would be -10
        migrate.execute(
            self.conn, "UPDATE seasons SET frozen_at = %s WHERE id = %s", (T0, self.pre)
        )
        self.conn.commit()
        result = settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual((result.adjustment, result.points_after), (0, 500))
        self.assertEqual(self._points(player), 500)

    def _race(self, first, second, pause_in):
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

    def test_launch_waits_for_an_answer_in_progress(self):
        player = self._account(points=850)
        attempt_id = self._start(player)
        results, waited = self._race(
            lambda conn: self._answer(attempt_id, 1, CORRECT, conn=conn),
            lambda conn: self._launch(conn=conn),
            pause_in="_question_for_version",
        )
        self.assertTrue(waited, "launch did not wait for the answer in progress")
        self.assertEqual(results["second"][0], "ok", results["second"])
        self.assertEqual(self._attempt(attempt_id), ("finalized", "launch_reset"))
        self.assertEqual(self._points(player), 0)

    def test_launch_waits_for_a_start_in_progress(self):
        player = self._account(points=850)
        results, waited = self._race(
            lambda conn: self._start(player, conn=conn),
            lambda conn: self._launch(conn=conn),
            pause_in="_send_question",
        )
        self.assertTrue(waited, "launch did not wait for the start in progress")
        self.assertEqual(results["first"][0], "ok", results["first"])
        self.assertEqual(results["second"][0], "ok", results["second"])
        # the Pre-Season attempt that slipped in was seen and voided by launch
        self.assertEqual(self._attempt(results["first"][1]), ("finalized", "launch_reset"))
        unfinished = self._one(
            "SELECT COUNT(*) AS n FROM attempts WHERE state <> 'finalized'"
        )["n"]
        self.assertEqual(unfinished, 0)
        self.assertEqual(self._points(player), 0)


if __name__ == "__main__":
    unittest.main()
