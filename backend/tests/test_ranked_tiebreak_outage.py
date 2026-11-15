"""A confirmed outage during a prize tie-break round (issue #24, slice 5).

Settled Decisions 9-10: the whole current round restarts for everybody,
including players who already finished, with fresh questions and a new
24 hours. The restart keeps the round's number, so it keeps its seconds
and does not count towards the round limit. Earlier valid rounds stand.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone

from backend.db import migrate, settings
from backend.ranked import engine, outages, tiebreaks
from backend.ranked_bank.catalog import load_reviewed_bank

BANK = load_reviewed_bank()


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class TiebreakOutageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(self.conninfo)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.t0 = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.clock = Clock(self.t0)
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'Peak Season', %s, %s, %s, %s) RETURNING id",
            (self.t0 - timedelta(days=60), self.t0, self.t0, self.t0),
        )["id"]
        self.a, self.b = self._account(1), self._account(2)
        self.group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'season_close', 700, 1, %s) RETURNING id",
            (self.season, self.t0),
        )["id"]
        self.rng = random.Random(3)
        self.round = tiebreaks._open_round(
            self.conn, self.group, self.season, 4, [self.a, self.b], 1,
            opened_at=self.t0, deadline_at=self.t0 + timedelta(hours=24), bank=BANK, rng=self.rng,
        )
        self.conn.commit()

    def _account(self, n):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
            (f"o_{n}", f"o_{n}", f"OUT{n:03d}"),
        )["id"]

    def _finish(self, account_id):
        attempt = engine.start_tiebreak_attempt(self.conn, account_id, self.round, clock=self.clock)
        for seq in range(1, 6):
            engine.submit_answer(self.conn, attempt, seq, "YELLOW", clock=self.clock, bank=BANK)
        return attempt

    def _outage(self, start_minutes, end_minutes):
        self.clock.moment = self.t0 + timedelta(minutes=end_minutes + 1)
        outages.record_outage(
            self.conn,
            starts_at=self.t0 + timedelta(minutes=start_minutes),
            ends_at=self.t0 + timedelta(minutes=end_minutes),
            clock=self.clock,
        )

    def _live_round(self):
        return migrate.fetch_one(
            self.conn,
            "SELECT id, round_number, hats, deadline_at FROM tiebreak_rounds"
            " WHERE group_id = %s AND status = 'open'",
            (self.group,),
        )

    # --- the restart ---

    def test_an_interrupted_round_restarts_for_everybody(self):
        self._finish(self.a)  # already done before the outage
        running = engine.start_tiebreak_attempt(self.conn, self.b, self.round, clock=self.clock)
        self._outage(0, 2)
        status = migrate.fetch_one(
            self.conn, "SELECT status FROM tiebreak_rounds WHERE id = %s", (self.round,)
        )["status"]
        self.assertEqual(status, "void")
        live = self._live_round()
        self.assertIsNotNone(live)
        players = {
            r["account_id"] for r in migrate.fetch_all(
                self.conn, "SELECT account_id FROM tiebreak_round_players WHERE round_id = %s",
                (live["id"],),
            )
        }
        self.assertEqual(players, {self.a, self.b})
        ended = migrate.fetch_one(
            self.conn, "SELECT state, final_outcome FROM attempts WHERE id = %s", (running,)
        )
        self.assertEqual((ended["state"], ended["final_outcome"]), ("finalized", "outage_void"))

    def test_the_restart_keeps_its_round_number_and_seconds(self):
        """A void round consumes no limit and no timer step."""
        engine.start_tiebreak_attempt(self.conn, self.a, self.round, clock=self.clock)
        self._outage(0, 2)
        live = self._live_round()
        self.assertEqual((live["round_number"], live["hats"]), (4, 1))

    def test_the_restart_gets_a_fresh_set_and_a_new_24_hours(self):
        engine.start_tiebreak_attempt(self.conn, self.a, self.round, clock=self.clock)
        self._outage(0, 2)
        live = self._live_round()
        self.assertEqual(live["deadline_at"], self.clock.moment + timedelta(hours=24))
        old = {r["bank_key"] for r in migrate.fetch_all(
            self.conn, "SELECT bank_key FROM tiebreak_round_questions WHERE round_id = %s", (self.round,))}
        new = {r["bank_key"] for r in migrate.fetch_all(
            self.conn, "SELECT bank_key FROM tiebreak_round_questions WHERE round_id = %s", (live["id"],))}
        self.assertEqual(len(new), 5)
        self.assertFalse(old & new)

    def test_a_player_who_had_finished_plays_again(self):
        self._finish(self.a)
        engine.start_tiebreak_attempt(self.conn, self.b, self.round, clock=self.clock)
        self._outage(0, 2)
        live = self._live_round()
        again = engine.start_tiebreak_attempt(self.conn, self.a, live["id"], clock=self.clock)
        self.assertIsNotNone(again)

    def test_a_round_nobody_was_playing_is_not_restarted(self):
        self._outage(0, 2)
        status = migrate.fetch_one(
            self.conn, "SELECT status FROM tiebreak_rounds WHERE id = %s", (self.round,)
        )["status"]
        self.assertEqual(status, "open")

    def test_an_outage_before_anybody_started_restarts_nothing(self):
        self.clock.moment = self.t0 + timedelta(minutes=30)
        engine.start_tiebreak_attempt(self.conn, self.a, self.round, clock=self.clock)
        self._outage(0, 2)
        self.assertEqual(self._live_round()["id"], self.round)

    def test_the_voided_rounds_results_are_never_revealed(self):
        attempt = self._finish(self.a)
        engine.start_tiebreak_attempt(self.conn, self.b, self.round, clock=self.clock)
        self._outage(0, 2)
        self.clock.moment = self.t0 + timedelta(days=3)
        tiebreaks.close_due_rounds(self.conn, clock=self.clock, bank=BANK)
        self.assertIsNone(tiebreaks.revealed_result(self.conn, attempt))

    # --- the latent lock bug this slice fixed ---

    def test_an_interrupted_tiebreak_never_locks_the_account(self):
        """Before this slice, the ordinary outage path marked a tie-break
        attempt terminal_pending. Tie-breaks are never settled, so it would
        have stayed there for good, holding the one-unfinished-attempt lock:
        the player could never start another quiz."""
        engine.start_tiebreak_attempt(self.conn, self.a, self.round, clock=self.clock)
        self._outage(0, 2)
        stuck = migrate.fetch_all(
            self.conn,
            "SELECT id FROM attempts WHERE account_id = %s"
            " AND state IN ('active', 'grace', 'terminal_pending')",
            (self.a,),
        )
        self.assertEqual(stuck, [])

    def test_no_fresh_set_for_the_restart_sends_the_round_to_the_owner(self):
        engine.start_tiebreak_attempt(self.conn, self.a, self.round, clock=self.clock)
        filler = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'replacement', 1, 1, %s) RETURNING id",
            (self.season, self.t0),
        )["id"]
        while tiebreaks.fresh_sets_left(self.conn, self.season, BANK):
            rid = migrate.fetch_one(
                self.conn,
                "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at, status, hats)"
                " VALUES (%s, 1, %s, %s, 'void', 1) RETURNING id",
                (filler, self.t0, self.t0 + timedelta(hours=1)),
            )["id"]
            tiebreaks.assign_round_questions(self.conn, rid, self.season, BANK, rng=self.rng)
        self.conn.commit()
        self._outage(0, 2)
        self.assertIsNone(self._live_round())
        status = migrate.fetch_one(
            self.conn, "SELECT status FROM tiebreak_groups WHERE id = %s", (self.group,)
        )["status"]
        self.assertEqual(status, "owner_selection")


if __name__ == "__main__":
    unittest.main()
