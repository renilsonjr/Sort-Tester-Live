"""The season clock: scheduled end, admission and derived status
(issue #23, slice 1)."""
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

from backend.db import migrate, settings
from backend.ranked import engine, seasons
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
END = T0 + timedelta(hours=1)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SeasonClockTests(unittest.TestCase):
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

    def _season(self, *, phase="official", closes_at=None, closed_at=None,
                frozen_at=None, label="season"):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at,"
            " frozen_at) VALUES (%s, %s, %s, %s, %s, %s) RETURNING id",
            (phase, label, T0 - timedelta(days=1), closes_at, closed_at, frozen_at),
        )
        self.conn.commit()
        return row["id"]

    def _season_count(self):
        return migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM seasons")["n"]

    # --- the first Pre-Season ---

    def test_ensure_pre_season_creates_it_once(self):
        first = seasons.ensure_pre_season(self.conn)
        second = seasons.ensure_pre_season(self.conn)
        self.assertEqual(first, second)
        self.assertEqual(self._season_count(), 1)
        row = migrate.fetch_one(
            self.conn, "SELECT phase, closes_at FROM seasons WHERE id = %s", (first,)
        )
        self.assertEqual((row["phase"], row["closes_at"]), ("pre_season", None))
        self.assertEqual(seasons.admitting_season(self.conn, T0), first)

    def test_ensure_pre_season_leaves_an_existing_season_alone(self):
        existing = self._season(closes_at=END)
        self.assertEqual(seasons.ensure_pre_season(self.conn), existing)
        self.assertEqual(self._season_count(), 1)

    # --- admission ---

    def test_a_season_without_an_end_admits(self):
        season_id = self._season(phase="pre_season")
        self.assertEqual(seasons.admitting_season(self.conn, T0), season_id)

    def test_admission_follows_the_scheduled_end(self):
        season_id = self._season(closes_at=END)
        one_second = timedelta(seconds=1)
        self.assertEqual(seasons.admitting_season(self.conn, END - one_second), season_id)
        self.assertIsNone(seasons.admitting_season(self.conn, END))  # the end itself
        self.assertIsNone(seasons.admitting_season(self.conn, END + one_second))

    def test_a_closed_or_frozen_season_does_not_admit(self):
        self._season(closed_at=T0, label="closed")
        self._season(closes_at=END, frozen_at=T0, label="frozen")
        self.assertIsNone(seasons.admitting_season(self.conn, T0))

    def test_no_season_at_all_does_not_admit(self):
        self.assertIsNone(seasons.admitting_season(self.conn, T0))

    # --- derived status ---

    def _status(self, season_id, now):
        return seasons.season_status(self.conn, season_id, now).status

    def test_status_moves_with_the_clock(self):
        season_id = self._season(closes_at=END)
        window = timedelta(seconds=seasons.FINISHING_WINDOW_SECONDS)
        one_second = timedelta(seconds=1)
        self.assertEqual(self._status(season_id, END - one_second), "open")
        self.assertEqual(self._status(season_id, END), "finishing")
        self.assertEqual(self._status(season_id, END + window - one_second), "finishing")
        self.assertEqual(self._status(season_id, END + window), "closed")

    def test_finishing_window_is_five_minutes(self):
        self.assertEqual(seasons.FINISHING_WINDOW_SECONDS, 300)

    def test_a_season_closed_by_hand_ends_at_that_moment(self):
        season_id = self._season(phase="pre_season", closed_at=T0)
        self.assertEqual(self._status(season_id, T0), "finishing")
        self.assertEqual(self._status(season_id, T0 + timedelta(minutes=5)), "closed")

    def test_a_frozen_season_is_frozen_whatever_the_clock_says(self):
        season_id = self._season(closes_at=END, frozen_at=END + timedelta(minutes=6))
        self.assertEqual(self._status(season_id, T0), "frozen")

    def test_status_reports_the_season_details(self):
        season_id = self._season(closes_at=END, label="Peak 2026")
        status = seasons.season_status(self.conn, season_id, T0)
        self.assertEqual(
            (status.phase, status.label, status.closes_at), ("official", "Peak 2026", END)
        )

    # --- contracts for other features (slice 4) ---

    def test_current_status_is_the_newest_season(self):
        self.assertIsNone(seasons.current_season_status(self.conn, T0))
        self._season(phase="pre_season", closed_at=T0, frozen_at=T0, label="Pre-Season")
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak 2026', %s, %s)",
            (T0, END),
        )
        self.conn.commit()
        current = seasons.current_season_status(self.conn, T0)
        self.assertEqual(
            (current.phase, current.label, current.status), ("official", "Peak 2026", "open")
        )

    def test_official_launch_is_the_durable_launch_fact(self):
        self._season(phase="pre_season", label="Pre-Season")
        self.assertIsNone(seasons.official_launch(self.conn))
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak 2026', %s, %s)",
            (T0, END),
        )
        self.conn.commit()
        fact = seasons.official_launch(self.conn)
        self.assertEqual((fact.label, fact.launched_at), ("Peak 2026", T0))
        self.assertIsNotNone(fact.season_id)

    def test_approvals_are_open_only_while_the_season_is_open(self):
        self.assertFalse(seasons.approvals_open(self.conn, T0))  # no season at all
        season_id = self._season(closes_at=END)
        window = timedelta(seconds=seasons.FINISHING_WINDOW_SECONDS)
        one_second = timedelta(seconds=1)
        self.assertTrue(seasons.approvals_open(self.conn, END - one_second))
        # from the end onward: the finishing window admits no new approval
        self.assertFalse(seasons.approvals_open(self.conn, END))
        self.assertFalse(seasons.approvals_open(self.conn, END + window))
        self.assertTrue(
            seasons.season_status(self.conn, season_id, END - one_second).approvals_open
        )
        self.assertFalse(seasons.season_status(self.conn, season_id, END).approvals_open)

    def test_approvals_are_closed_in_a_frozen_season(self):
        self._season(closes_at=END, frozen_at=END + timedelta(minutes=6))
        self.assertFalse(seasons.approvals_open(self.conn, T0))

    # --- the engine admits by the clock ---

    def _account(self, tag):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"season_{tag.lower()}", f"season_{tag.lower()}", tag),
        )
        self.conn.commit()
        return row["id"]

    def test_engine_refuses_a_start_at_the_scheduled_end(self):
        self._season(closes_at=END)
        bank = make_unconstrained_bank(tempfile.mkdtemp())
        clock = FakeClock(END - timedelta(seconds=1))
        attempt_id = engine.start_attempt(
            self.conn, self._account("C00001"), clock=clock, bank=bank
        )
        clock.advance(1)  # now exactly the end
        with self.assertRaises(engine.NoOpenSeasonError):
            engine.start_attempt(self.conn, self._account("C00002"), clock=clock, bank=bank)
        # the attempt started before the end keeps running
        result = engine.submit_answer(
            self.conn, attempt_id, 1, "GOLD", clock=clock, bank=bank
        )
        self.assertEqual(result.outcome, "correct")


if __name__ == "__main__":
    unittest.main()
