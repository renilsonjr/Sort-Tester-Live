"""Finding the prize ties that need a quiz, and opening round 1
(issue #24, slice 1).

The owner's rule of 2026-11-15: a quiz runs only when more than three
players are competing for the three hats. The first block holds that rule
on its own, with the owner's own examples; the second holds it through a
real season freeze.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db import migrate, settings
from backend.ranked import season_close, standings, tiebreaks

T0 = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)


def _rows(*points):
    """Standings rows for these points, best first, as the board numbers them."""
    raw = [
        {"id": uuid4(), "username": f"p{i}", "tag": f"T{i:05d}", "points": p}
        for i, p in enumerate(sorted(points, reverse=True))
    ]
    return standings.place_rows(raw)


class PrizeTieRuleTests(unittest.TestCase):
    """The rule, with no database."""

    def test_two_tied_first_and_one_third_all_win_with_no_quiz(self):
        """The owner's case A: three players, three hats, nobody plays."""
        self.assertIsNone(tiebreaks.prize_tie(_rows(900, 900, 800, 700)))

    def test_two_tied_at_third_play_for_the_last_hat(self):
        """The owner's case B: four players competing for three hats."""
        tie = tiebreaks.prize_tie(_rows(900, 800, 700, 700))
        self.assertIsNotNone(tie)
        self.assertEqual(tie.tied_points, 700)
        self.assertEqual(tie.hats_available, 1)
        self.assertEqual(len(tie.account_ids), 2)

    def test_three_tied_at_second_play_for_two_hats(self):
        tie = tiebreaks.prize_tie(_rows(900, 800, 800, 800))
        self.assertEqual(tie.hats_available, 2)
        self.assertEqual(len(tie.account_ids), 3)

    def test_four_tied_at_the_top_all_play_for_three_hats(self):
        tie = tiebreaks.prize_tie(_rows(500, 500, 500, 500))
        self.assertEqual(tie.hats_available, 3)
        self.assertEqual(len(tie.account_ids), 4)

    def test_three_tied_at_the_top_share_and_nobody_plays(self):
        self.assertIsNone(tiebreaks.prize_tie(_rows(500, 500, 500, 400)))

    def test_a_tie_below_third_place_is_nobodys_business(self):
        """No quiz to order places below the prize top three."""
        self.assertIsNone(tiebreaks.prize_tie(_rows(900, 800, 700, 600, 600)))

    def test_fewer_than_three_eligible_means_no_quiz(self):
        """Fewer hats, never fabricated winners."""
        self.assertIsNone(tiebreaks.prize_tie(_rows(900, 900)))
        self.assertIsNone(tiebreaks.prize_tie(_rows(900)))
        self.assertIsNone(tiebreaks.prize_tie([]))

    def test_exactly_three_eligible_all_tied_win_with_no_quiz(self):
        self.assertIsNone(tiebreaks.prize_tie(_rows(100, 100, 100)))

    def test_negative_points_follow_the_same_rule(self):
        tie = tiebreaks.prize_tie(_rows(50, -10, -40, -40))
        self.assertEqual(tie.tied_points, -40)
        self.assertEqual(tie.hats_available, 1)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SeasonCloseTieTests(unittest.TestCase):
    """The rule through a real freeze."""

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
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak Season', %s, %s) RETURNING id",
            (T0 - timedelta(days=60), T0),
        )["id"]
        self.conn.commit()
        self._n = 0

    def _player(self, points, *, eligible=True):
        self._n += 1
        tag = f"P{self._n:05d}"
        account_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"player_{self._n}", f"player_{self._n}", tag),
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
            (account_id, points),
        )
        if eligible:
            migrate.execute(
                self.conn,
                "INSERT INTO participant_links (account_id, roster_reference)"
                " VALUES (%s, %s)",
                (account_id, f"roster-{tag}"),
            )
            assignment = migrate.fetch_one(
                self.conn,
                "INSERT INTO assignments (account_id, mode, season_id)"
                " VALUES (%s, 'normal', %s) RETURNING id",
                (account_id, self.season),
            )["id"]
            migrate.execute(
                self.conn,
                "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
                " state, final_outcome, started_at, settled_at)"
                " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', %s, %s)",
                (account_id, assignment, self.season, T0 - timedelta(days=1),
                 T0 - timedelta(days=1)),
            )
        self.conn.commit()
        return account_id

    def _freeze(self, at):
        class Clock:
            def now(self_inner):
                return at
        return season_close.finish_season(self.conn, self.season, clock=Clock())

    def _groups(self):
        return migrate.fetch_all(
            self.conn, "SELECT * FROM tiebreak_groups WHERE season_id = %s", (self.season,)
        )

    def _after_window(self):
        return T0 + timedelta(minutes=10)

    def test_a_tie_across_the_cut_opens_a_group_at_the_freeze(self):
        self._player(900)
        self._player(800)
        a = self._player(700)
        b = self._player(700)
        self.assertTrue(self._freeze(self._after_window()))
        groups = self._groups()
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]["tied_points"], 700)
        self.assertEqual(groups[0]["hats_available"], 1)
        members = {
            row["account_id"]
            for row in migrate.fetch_all(
                self.conn,
                "SELECT account_id FROM tiebreak_group_members WHERE group_id = %s",
                (groups[0]["id"],),
            )
        }
        self.assertEqual(members, {a, b})

    def test_round_one_closes_24_hours_after_the_scheduled_close(self):
        """The scheduled close, not the moment the freeze happened to run."""
        for p in (900, 800, 700, 700):
            self._player(p)
        self._freeze(T0 + timedelta(hours=3))
        round_ = migrate.fetch_one(self.conn, "SELECT * FROM tiebreak_rounds")
        self.assertEqual(round_["round_number"], 1)
        self.assertEqual(round_["deadline_at"], T0 + timedelta(hours=24))
        self.assertEqual(round_["status"], "open")

    def test_no_tie_across_the_cut_opens_nothing(self):
        for p in (900, 900, 800, 700):
            self._player(p)
        self._freeze(self._after_window())
        self.assertEqual(self._groups(), [])
        self.assertEqual(migrate.fetch_all(self.conn, "SELECT * FROM tiebreak_rounds"), [])

    def test_ineligible_players_do_not_count_towards_the_tie(self):
        """Only the eligible standings compete for hats."""
        self._player(900)
        self._player(800)
        self._player(700)
        self._player(700, eligible=False)
        self._freeze(self._after_window())
        self.assertEqual(self._groups(), [])

    def test_freezing_twice_opens_one_group(self):
        for p in (900, 800, 700, 700):
            self._player(p)
        self._freeze(self._after_window())
        self._freeze(self._after_window() + timedelta(minutes=1))
        tiebreaks.open_prize_tiebreaks(
            self.conn, self.season,
            clock=type("C", (), {"now": lambda s: self._after_window()})(),
        )
        self.conn.commit()
        self.assertEqual(len(self._groups()), 1)
        self.assertEqual(
            len(migrate.fetch_all(self.conn, "SELECT * FROM tiebreak_rounds")), 1
        )

    def test_pre_season_opens_no_tiebreak(self):
        migrate.execute(
            self.conn, "UPDATE seasons SET phase = 'pre_season' WHERE id = %s", (self.season,)
        )
        self.conn.commit()
        group = tiebreaks.open_prize_tiebreaks(
            self.conn, self.season,
            clock=type("C", (), {"now": lambda s: self._after_window()})(),
        )
        self.assertIsNone(group)

    def test_a_freeze_more_than_a_day_late_still_gives_a_full_round(self):
        """If the server was down past the scheduled deadline, the round
        still gets a playable 24 hours rather than one already over."""
        for p in (900, 800, 700, 700):
            self._player(p)
        late = T0 + timedelta(days=2)
        self._freeze(late)
        round_ = migrate.fetch_one(self.conn, "SELECT * FROM tiebreak_rounds")
        self.assertEqual(round_["deadline_at"], late + timedelta(hours=24))

    def test_the_freeze_and_the_group_are_written_together(self):
        """If opening the group fails, the season does not freeze either,
        so the next run tries both again."""
        for p in (900, 800, 700, 700):
            self._player(p)
        original = tiebreaks.open_prize_tiebreaks

        def broken(*args, **kwargs):
            raise RuntimeError("simulated failure")

        tiebreaks.open_prize_tiebreaks = broken
        try:
            with self.assertRaises(RuntimeError):
                self._freeze(self._after_window())
        finally:
            tiebreaks.open_prize_tiebreaks = original
        self.conn.rollback()
        frozen = migrate.fetch_one(
            self.conn, "SELECT frozen_at FROM seasons WHERE id = %s", (self.season,)
        )["frozen_at"]
        self.assertIsNone(frozen)
        self.assertTrue(self._freeze(self._after_window()))
        self.assertEqual(len(self._groups()), 1)


if __name__ == "__main__":
    unittest.main()
