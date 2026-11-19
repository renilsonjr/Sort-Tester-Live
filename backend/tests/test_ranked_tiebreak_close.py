"""Closing a prize tie-break round at its deadline (issue #24, slice 4).

The first block holds the record's rules on their own, one rule per test.
The second runs real rounds through the database: scoring, the next
round, the owner's selection, Challenger exclusion, and what a player is
shown before and after the deadline.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db import migrate, settings
from backend.ranked import engine, tiebreaks
from backend.ranked.tiebreaks import RoundResult, decide_round
from backend.ranked_bank.catalog import load_reviewed_bank

BANK = load_reviewed_bank()


def completed(score):
    return RoundResult(uuid4(), "completed", score)


def incomplete():
    return RoundResult(uuid4(), "incomplete", None)


def no_show():
    return RoundResult(uuid4(), "no_show", None)


def lower(results, hats, round_number=1):
    return decide_round(results, hats, challenger=False, round_number=round_number).statuses


class DecideRoundTests(unittest.TestCase):
    """The rules, with no database."""

    def test_the_higher_score_takes_the_hat(self):
        a, b = completed(4), completed(2)
        statuses = lower([a, b], 1)
        self.assertEqual((statuses[a.account_id], statuses[b.account_id]), ("hat", "no_hat"))

    def test_a_score_level_that_fits_takes_every_hat_in_it(self):
        a, b, c = completed(5), completed(5), completed(1)
        statuses = lower([a, b, c], 2)
        self.assertEqual(
            [statuses[x.account_id] for x in (a, b, c)], ["hat", "hat", "no_hat"]
        )

    def test_still_tied_for_the_hat_means_another_round(self):
        a, b, c = completed(3), completed(3), completed(1)
        decision = decide_round([a, b, c], 1, challenger=False, round_number=1)
        self.assertEqual(decision.statuses[a.account_id], "next_round")
        self.assertEqual(decision.statuses[b.account_id], "next_round")
        self.assertEqual(decision.statuses[c.account_id], "no_hat")
        self.assertEqual(decision.next_round_hats, 1)

    def test_prior_order_is_kept_and_only_the_tied_level_plays_on(self):
        """Three for two hats: the clear winner keeps their hat, the two
        still tied play the next round for the one left."""
        a, b, c = completed(5), completed(2), completed(2)
        decision = decide_round([a, b, c], 2, challenger=False, round_number=1)
        self.assertEqual(decision.statuses[a.account_id], "hat")
        self.assertEqual(decision.next_round_hats, 1)

    def test_a_completed_zero_outranks_a_no_show(self):
        """A completed 0/5 remains completed (settled)."""
        a, b = completed(0), no_show()
        statuses = lower([a, b], 1)
        self.assertEqual((statuses[a.account_id], statuses[b.account_id]), ("hat", "no_hat"))

    def test_completed_outranks_incomplete(self):
        a, b = completed(1), incomplete()
        statuses = lower([a, b], 1)
        self.assertEqual(statuses[a.account_id], "hat")

    def test_several_incomplete_for_fewer_hats_wait_for_the_owner(self):
        """Lower ranks: no extra quiz for the incomplete group."""
        a, b = incomplete(), no_show()
        statuses = lower([a, b], 1)
        self.assertEqual(set(statuses.values()), {"owner_selection"})

    def test_incomplete_players_who_all_fit_take_the_hats(self):
        a, b = incomplete(), no_show()
        statuses = lower([a, b], 2)
        self.assertEqual(set(statuses.values()), {"hat"})

    def test_after_round_five_a_remaining_tie_goes_to_the_owner(self):
        a, b = completed(3), completed(3)
        statuses = lower([a, b], 1, round_number=5)
        self.assertEqual(set(statuses.values()), {"owner_selection"})

    def test_challenger_excludes_whoever_did_not_complete(self):
        a, b = completed(2), no_show()
        statuses = decide_round([a, b], 1, challenger=True, round_number=1).statuses
        self.assertEqual((statuses[a.account_id], statuses[b.account_id]), ("hat", "excluded"))

    def test_challenger_excludes_both_when_both_fail(self):
        a, b = incomplete(), no_show()
        statuses = decide_round([a, b], 1, challenger=True, round_number=1).statuses
        self.assertEqual(set(statuses.values()), {"excluded"})

    def test_challenger_stops_after_three_rounds(self):
        a, b = completed(4), completed(4)
        statuses = decide_round([a, b], 1, challenger=True, round_number=3).statuses
        self.assertEqual(set(statuses.values()), {"owner_selection"})

    def test_challenger_round_two_can_still_continue(self):
        a, b = completed(4), completed(4)
        decision = decide_round([a, b], 1, challenger=True, round_number=2)
        self.assertEqual(set(decision.statuses.values()), {"next_round"})


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class CloseRoundTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.t0 = datetime(2027, 1, 1, 0, 0, tzinfo=timezone.utc)
        self.clock = Clock(self.t0)
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'Peak Season', %s, %s, %s, %s) RETURNING id",
            (self.t0 - timedelta(days=60), self.t0, self.t0, self.t0),
        )["id"]
        self.conn.commit()
        self._n = 0
        self.rng = random.Random(11)

    # --- helpers ---

    def _account(self):
        self._n += 1
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
            (f"c_{self._n}", f"c_{self._n}", f"C{self._n:05d}"),
        )["id"]

    def _group(self, players, *, hats=1, points=700):
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'season_close', %s, %s, %s) RETURNING id",
            (self.season, points, hats, self.t0),
        )["id"]
        for p in players:
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
                (group, p),
            )
        round_id = tiebreaks._open_round(
            self.conn, group, self.season, 1, players, hats,
            opened_at=self.t0, deadline_at=self.t0 + timedelta(hours=24), bank=BANK, rng=self.rng,
        )
        self.conn.commit()
        return group, round_id

    def _play(self, round_id, account_id, correct):
        """Play the round as this player, getting exactly ``correct`` right."""
        attempt = engine.start_tiebreak_attempt(self.conn, account_id, round_id, clock=self.clock)
        for seq in range(1, 6):
            key = migrate.fetch_one(
                self.conn,
                "SELECT qv.bank_key FROM attempt_answers aa"
                " JOIN question_versions qv ON qv.id = aa.question_version_id"
                " WHERE aa.attempt_id = %s AND aa.seq = %s",
                (attempt, seq),
            )["bank_key"]
            right = next(q.correct_belt for q in BANK.questions if q.canonical_id == key)
            wrong = "PURPLE" if right != "PURPLE" else "BLUE"
            engine.submit_answer(
                self.conn, attempt, seq, right if seq <= correct else wrong,
                clock=self.clock, bank=BANK,
            )
        return attempt

    def _close(self, round_id):
        self.clock.moment = self.t0 + timedelta(hours=24, seconds=1)
        return tiebreaks.close_round(self.conn, round_id, clock=self.clock, bank=BANK, rng=self.rng)

    def _placement(self, group, account_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT status FROM tiebreak_placements WHERE group_id = %s AND account_id = %s",
            (group, account_id),
        )
        return None if row is None else row["status"]

    def _group_status(self, group):
        return migrate.fetch_one(
            self.conn, "SELECT status FROM tiebreak_groups WHERE id = %s", (group,)
        )["status"]

    # --- tests ---

    def test_the_round_is_scored_and_the_better_player_takes_the_hat(self):
        a, b = self._account(), self._account()
        group, round_id = self._group([a, b])
        self._play(round_id, a, 4)
        self._play(round_id, b, 2)
        self.assertTrue(self._close(round_id))
        self.assertEqual(self._placement(group, a), "hat")
        self.assertEqual(self._placement(group, b), "no_hat")
        self.assertEqual(self._group_status(group), "resolved")
        scores = {
            r["account_id"]: r["score"]
            for r in migrate.fetch_all(
                self.conn, "SELECT account_id, score FROM tiebreak_round_results WHERE round_id = %s",
                (round_id,),
            )
        }
        self.assertEqual(scores, {a: 4, b: 2})

    def test_nothing_closes_before_the_deadline(self):
        a, b = self._account(), self._account()
        _, round_id = self._group([a, b])
        self.clock.moment = self.t0 + timedelta(hours=23)
        self.assertFalse(tiebreaks.close_round(self.conn, round_id, clock=self.clock, bank=BANK))

    def test_closing_twice_changes_nothing(self):
        a, b = self._account(), self._account()
        _, round_id = self._group([a, b])
        self._play(round_id, a, 3)
        self.assertTrue(self._close(round_id))
        self.assertFalse(self._close(round_id))
        self.assertEqual(
            len(migrate.fetch_all(self.conn, "SELECT * FROM tiebreak_round_results")), 2
        )

    def test_a_tie_that_remains_opens_round_two_for_the_tied_only(self):
        a, b, c = self._account(), self._account(), self._account()
        group, round_id = self._group([a, b, c])
        self._play(round_id, a, 3)
        self._play(round_id, b, 3)
        self._play(round_id, c, 1)
        self._close(round_id)
        nxt = migrate.fetch_one(
            self.conn,
            "SELECT id, round_number, hats, deadline_at FROM tiebreak_rounds"
            " WHERE group_id = %s AND status = 'open'",
            (group,),
        )
        self.assertEqual((nxt["round_number"], nxt["hats"]), (2, 1))
        self.assertEqual(nxt["deadline_at"], self.clock.moment + timedelta(hours=24))
        players = {
            r["account_id"]
            for r in migrate.fetch_all(
                self.conn, "SELECT account_id FROM tiebreak_round_players WHERE round_id = %s",
                (nxt["id"],),
            )
        }
        self.assertEqual(players, {a, b})
        self.assertEqual(self._placement(group, c), "no_hat")
        self.assertIsNone(self._placement(group, a))  # still being decided
        self.assertEqual(self._group_status(group), "open")
        # and round two's questions are fresh
        round_one = {r["bank_key"] for r in migrate.fetch_all(
            self.conn, "SELECT bank_key FROM tiebreak_round_questions WHERE round_id = %s", (round_id,))}
        round_two = {r["bank_key"] for r in migrate.fetch_all(
            self.conn, "SELECT bank_key FROM tiebreak_round_questions WHERE round_id = %s", (nxt["id"],))}
        self.assertFalse(round_one & round_two)

    def test_an_attempt_still_running_ends_at_the_deadline(self):
        """A late start never moves the deadline."""
        a, b = self._account(), self._account()
        _, round_id = self._group([a, b])
        attempt = engine.start_tiebreak_attempt(self.conn, a, round_id, clock=self.clock)
        self._close(round_id)
        row = migrate.fetch_one(
            self.conn, "SELECT state, final_outcome FROM attempts WHERE id = %s", (attempt,)
        )
        self.assertEqual((row["state"], row["final_outcome"]), ("finalized", "round_deadline"))

    def test_lower_rank_no_shows_competing_wait_for_the_owner(self):
        a, b = self._account(), self._account()
        group, round_id = self._group([a, b])
        self._close(round_id)
        self.assertEqual(self._placement(group, a), "owner_selection")
        self.assertEqual(self._group_status(group), "owner_selection")

    def test_challenger_no_show_is_excluded_and_points_unchanged(self):
        a, b = self._account(), self._account()
        migrate.execute(
            self.conn, "INSERT INTO balances (account_id, current_points) VALUES (%s, 4500)", (b,)
        )
        group, round_id = self._group([a, b], points=4500)
        self._play(round_id, a, 1)
        self._close(round_id)
        self.assertEqual(self._placement(group, a), "hat")
        self.assertEqual(self._placement(group, b), "excluded")
        self.assertEqual(
            migrate.fetch_one(
                self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (b,)
            )["current_points"],
            4500,
        )

    def test_with_no_fresh_set_the_still_tied_wait_for_the_owner(self):
        a, b = self._account(), self._account()
        group, round_id = self._group([a, b])
        self._play(round_id, a, 2)
        self._play(round_id, b, 2)
        # use up every other fresh set this season
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
        self._close(round_id)
        self.assertEqual(self._placement(group, a), "owner_selection")
        self.assertEqual(self._group_status(group), "owner_selection")

    # --- what the player sees ---

    def test_the_score_is_hidden_until_the_deadline_then_shown(self):
        a, b = self._account(), self._account()
        _, round_id = self._group([a, b])
        attempt = self._play(round_id, a, 4)
        self.assertIsNone(tiebreaks.revealed_result(self.conn, attempt))
        self._close(round_id)
        shown = tiebreaks.revealed_result(self.conn, attempt)
        self.assertEqual((shown["score"], shown["placement"]), (4, "hat"))

    def test_the_revealed_result_is_the_players_own_only(self):
        a, b = self._account(), self._account()
        _, round_id = self._group([a, b])
        attempt = self._play(round_id, a, 4)
        self._play(round_id, b, 1)
        self._close(round_id)
        shown = tiebreaks.revealed_result(self.conn, attempt)
        self.assertEqual(set(shown), {"round", "outcome", "score", "placement"})


if __name__ == "__main__":
    unittest.main()
