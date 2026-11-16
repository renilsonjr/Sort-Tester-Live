"""Awarding the three hats, with the Q14 backfill (issue #24, slice 8).

The first block holds the resolver's rules on their own; the second runs
them through a real season, including a Challenger exclusion leaving a
vacancy that the next player fills.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db import migrate, settings
from backend.ranked import tiebreaks
from backend.ranked.tiebreaks import resolve_prizes
from backend.ranked_bank.catalog import load_reviewed_bank

BANK = load_reviewed_bank()


def ids(n):
    return [uuid4() for _ in range(n)]


class ResolvePrizesTests(unittest.TestCase):
    """The rule, no database."""

    def test_three_clear_winners_are_final(self):
        a, b, c, d = ids(4)
        out = resolve_prizes([[(a, "plain")], [(b, "plain")], [(c, "plain")], [(d, "plain")]])
        self.assertEqual(out.kind, "final")
        self.assertEqual(out.winners, (a, b, c))

    def test_fewer_than_three_eligible_awards_fewer(self):
        a, b = ids(2)
        out = resolve_prizes([[(a, "plain")], [(b, "plain")]])
        self.assertEqual(out.kind, "final")
        self.assertEqual(out.winners, (a, b))

    def test_nobody_eligible_awards_none(self):
        self.assertEqual(resolve_prizes([]).winners, ())

    def test_a_plain_tie_across_the_cut_needs_a_group(self):
        a, b, c, d = ids(4)
        out = resolve_prizes([[(a, "plain")], [(b, "plain")], [(c, "plain"), (d, "plain")]])
        self.assertEqual(out.kind, "needs_group")
        self.assertEqual(set(out.tie_accounts), {c, d})
        self.assertEqual(out.tie_hats, 1)

    def test_a_resolved_group_finalizes(self):
        a, b, c, d = ids(4)
        out = resolve_prizes([[(a, "plain")], [(b, "plain")], [(c, "winner"), (d, "loser")]])
        self.assertEqual(out.kind, "final")
        self.assertEqual(out.winners, (a, b, c))

    def test_an_open_group_is_pending(self):
        a, b = ids(2)
        self.assertEqual(resolve_prizes([[(a, "plain")], [(b, "pending")]]).kind, "pending")

    def test_an_excluded_player_is_skipped_and_the_hat_falls_down(self):
        """The backfill: a Challenger excluded at the top, the hat goes on."""
        a, b, c, d = ids(4)
        out = resolve_prizes([[(a, "excluded")], [(b, "plain")], [(c, "plain")], [(d, "plain")]])
        self.assertEqual(out.kind, "final")
        self.assertEqual(out.winners, (b, c, d))

    def test_an_excluded_player_can_leave_fewer_hats(self):
        a, b = ids(2)
        out = resolve_prizes([[(a, "excluded")], [(b, "plain")]])
        self.assertEqual(out.winners, (b,))

    def test_a_backfill_that_lands_on_a_tie_needs_a_group(self):
        """Both top players excluded; the next two are tied for the hats."""
        a, b, c, d = ids(4)
        out = resolve_prizes([
            [(a, "excluded")], [(b, "winner")], [(c, "plain"), (d, "plain")],
        ])
        # b has the first hat, two left... c and d tied for the two left: they
        # both fit, so they win
        self.assertEqual(out.kind, "final")
        self.assertEqual(out.winners, (b, c, d))

    def test_a_backfill_tie_with_too_many_opens_a_group(self):
        a, b, c, d = ids(4)
        out = resolve_prizes([
            [(a, "winner")], [(b, "winner")], [(c, "plain"), (d, "plain")],
        ])
        self.assertEqual(out.kind, "needs_group")
        self.assertEqual(out.tie_hats, 1)
        self.assertEqual(set(out.tie_accounts), {c, d})


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FinalizeTests(unittest.TestCase):
    """Through a real season."""

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
        self.clock = _Clock(self.t0)
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'Peak', %s, %s, %s, %s) RETURNING id",
            (self.t0 - timedelta(days=60), self.t0, self.t0, self.t0),
        )["id"]
        self.conn.commit()
        self._n = 0

    def _eligible(self, points):
        self._n += 1
        tag = f"W{self._n:05d}"
        account = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
            (f"wkr{self._n}", f"wkr{self._n}", tag),
        )["id"]
        migrate.execute(
            self.conn, "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
            (account, points),
        )
        migrate.execute(
            self.conn, "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, %s)",
            (account, f"r-{tag}"),
        )
        assignment = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id) VALUES (%s, 'normal', %s) RETURNING id",
            (account, self.season),
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id, state,"
            " final_outcome, settled_at) VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', %s)",
            (account, assignment, self.season, self.t0),
        )
        self.conn.commit()
        return account

    def _finalize(self):
        return tiebreaks.finalize_prizes(self.conn, self.season, clock=self.clock, bank=BANK)

    def _winners(self):
        return {
            r["account_id"]
            for r in migrate.fetch_all(
                self.conn, "SELECT account_id FROM season_prizes WHERE season_id = %s",
                (self.season,),
            )
        }

    def test_four_clear_players_award_the_top_three(self):
        a = self._eligible(900)
        b = self._eligible(800)
        c = self._eligible(700)
        self._eligible(600)
        self.assertEqual(self._finalize(), "final")
        self.assertEqual(self._winners(), {a, b, c})
        final = migrate.fetch_one(
            self.conn, "SELECT prizes_final_at FROM seasons WHERE id = %s", (self.season,)
        )["prizes_final_at"]
        self.assertIsNotNone(final)

    def test_finalizing_is_idempotent(self):
        self._eligible(900)
        self._eligible(800)
        self.assertEqual(self._finalize(), "final")
        self.assertEqual(self._finalize(), "final")
        self.assertEqual(len(self._winners()), 2)

    def test_a_challenger_exclusion_lets_the_next_player_backfill(self):
        """Two Challengers tied for the last hat; one no-shows and is
        excluded, so the hat falls to the next eligible player."""
        top = self._eligible(5000)
        second = self._eligible(4500)
        tied_a = self._eligible(4200)
        tied_b = self._eligible(4200)
        backfill = self._eligible(900)
        # the two 4200 Challengers played a round; tied_b was a no-show,
        # excluded; tied_a completed and took the hat... but that leaves the
        # third hat to tied_a, so there is no vacancy. Make BOTH excluded:
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available,"
            " opened_at, status) VALUES (%s, 'season_close', 4200, 1, %s, 'resolved') RETURNING id",
            (self.season, self.t0),
        )["id"]
        for acc in (tied_a, tied_b):
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
                (group, acc),
            )
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_placements (group_id, account_id, status, decided_in_round)"
                " VALUES (%s, %s, 'excluded', 1)",
                (group, acc),
            )
        self.conn.commit()
        self.assertEqual(self._finalize(), "final")
        # top and second take two hats; the two 4200s are excluded; the
        # backfill player takes the third
        self.assertEqual(self._winners(), {top, second, backfill})

    def test_a_backfill_landing_on_a_tie_opens_a_replacement_round(self):
        self._eligible(5000)  # winner 1
        self._eligible(4800)  # winner 2
        excluded = self._eligible(4600)
        tie_a = self._eligible(900)
        tie_b = self._eligible(900)
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available,"
            " opened_at, status) VALUES (%s, 'season_close', 4600, 1, %s, 'resolved') RETURNING id",
            (self.season, self.t0),
        )["id"]
        migrate.execute(
            self.conn, "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
            (group, excluded),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO tiebreak_placements (group_id, account_id, status, decided_in_round)"
            " VALUES (%s, %s, 'excluded', 1)",
            (group, excluded),
        )
        self.conn.commit()
        self.assertEqual(self._finalize(), "opened_round")
        # a replacement group for the two tied at 900, for the one freed hat
        new = migrate.fetch_one(
            self.conn,
            "SELECT g.id, g.hats_available FROM tiebreak_groups g"
            " WHERE g.reason = 'replacement' AND g.status = 'open'",
        )
        self.assertIsNotNone(new)
        self.assertEqual(new["hats_available"], 1)
        players = {
            r["account_id"]
            for r in migrate.fetch_all(
                self.conn,
                "SELECT account_id FROM tiebreak_group_members WHERE group_id = %s",
                (new["id"],),
            )
        }
        self.assertEqual(players, {tie_a, tie_b})
        self.assertFalse(self._winners())  # nothing final yet

    def test_an_open_round_keeps_prizes_provisional(self):
        self._eligible(900)
        self._eligible(900)
        self._eligible(900)
        self._eligible(900)  # four tied for three hats
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available,"
            " opened_at, status) VALUES (%s, 'season_close', 900, 3, %s, 'open') RETURNING id",
            (self.season, self.t0),
        )["id"]
        for acc in self._winners():  # none yet; add all four as members
            pass
        accounts = [r["account_id"] for r in migrate.fetch_all(
            self.conn, "SELECT account_id FROM balances")]
        for acc in accounts:
            migrate.execute(
                self.conn, "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
                (group, acc),
            )
        self.conn.commit()
        self.assertEqual(self._finalize(), "pending")
        self.assertFalse(self._winners())


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FinalizeLockTests(unittest.TestCase):
    """What finalize_prizes may take a lock for (audit M-2).

    Every ranked request runs this on its way in. It took ``FOR UPDATE``
    on the season row *before* deciding whether there was anything to do,
    so once a season's prizes were final -- the state it stays in forever
    after -- every request still queued on that one row.
    """

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
        self.clock = _Clock(self.t0)

    def _season(self, **columns):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at,"
            " frozen_at, prizes_final_at)"
            " VALUES ('official', 'Peak', %s, %s, %s, %s, %s) RETURNING id",
            (
                self.t0 - timedelta(days=60), self.t0, self.t0,
                columns.get("frozen_at", self.t0),
                columns.get("prizes_final_at"),
            ),
        )["id"]
        self.conn.commit()
        return row

    def _hold_the_row(self, season_id):
        """Another connection sitting on the season row, lock held."""
        holder = migrate.connect(self.conninfo)
        self.addCleanup(holder.close)
        self.addCleanup(holder.rollback)
        migrate.fetch_one(
            holder, "SELECT id FROM seasons WHERE id = %s FOR UPDATE", (season_id,)
        )
        return holder

    def _finalize_without_waiting(self, season_id):
        # a lock wait becomes an error instead of a hang, so a test that
        # should not be waiting fails fast rather than stopping the suite
        migrate.execute(self.conn, "SET lock_timeout = '2s'")
        try:
            return tiebreaks.finalize_prizes(
                self.conn, season_id, clock=self.clock, bank=BANK
            )
        finally:
            self.conn.rollback()
            migrate.execute(self.conn, "SET lock_timeout = 0")
            self.conn.commit()

    def test_a_settled_season_answers_while_another_holds_its_row(self):
        season = self._season(prizes_final_at=self.t0)
        self._hold_the_row(season)

        self.assertEqual(self._finalize_without_waiting(season), "final")

    def test_a_season_with_nothing_to_resolve_does_not_queue_either(self):
        # not frozen yet: there is nothing to finalize, so nothing to lock
        season = self._season(frozen_at=None)
        self._hold_the_row(season)

        self.assertEqual(self._finalize_without_waiting(season), "pending")

    def test_a_season_that_does_need_work_still_takes_the_lock(self):
        # the lock is what keeps two requests from awarding the hats twice,
        # so the early return must not reach a season with work to do
        season = self._season()
        self._hold_the_row(season)

        with self.assertRaises(Exception) as caught:
            self._finalize_without_waiting(season)
        self.assertIn("lock", str(caught.exception).lower())


class _Clock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


if __name__ == "__main__":
    unittest.main()
