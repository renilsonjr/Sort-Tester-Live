"""Who the official leaderboard includes, and in what order (issue #12).

The rules under test are the owner's settled Q5 and Q6, so each test is
named after the rule it holds rather than after the function it calls.
Attempts are written straight into the tables here: this slice is about who
the board includes, and building real attempts through the engine would
test the engine instead.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db import migrate, settings
from backend.ranked import standings

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class StandingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        try:
            migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.season = self._season("official", "Peak Season")
        self.pre_season = self._season("pre_season", "Pre-Season")
        self._accounts = 0

    # --- helpers ---

    def _season(self, phase, label):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (phase, label, T0 - timedelta(days=1), T0 + timedelta(days=7)),
        )["id"]

    def _account(self, name, points=None, *, approved=True, deleted=False):
        self._accounts += 1
        tag = f"S{self._accounts:05d}"
        account_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (name, name.lower(), tag),
        )["id"]
        if points is not None:
            migrate.execute(
                self.conn,
                "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
                (account_id, points),
            )
        if approved:
            migrate.execute(
                self.conn,
                "INSERT INTO participant_links (account_id, roster_reference)"
                " VALUES (%s, %s)",
                (account_id, f"twilight-primary-{tag}"),
            )
        if deleted:
            migrate.execute(
                self.conn,
                "UPDATE accounts SET deleted_at = now() WHERE id = %s",
                (account_id,),
            )
        return account_id

    def _attempt(
        self,
        account_id,
        *,
        season=None,
        mode="normal",
        state="finalized",
        outcome="completed",
    ):
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, %s, %s) RETURNING id",
            (account_id, mode, season or self.season),
        )["id"]
        settled = T0 if state == "finalized" else None
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts"
            " (account_id, assignment_id, mode, season_id, state, final_outcome,"
            "  started_at, settled_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, %s) RETURNING id",
            (
                account_id,
                assignment_id,
                mode,
                season or self.season,
                state,
                outcome,
                T0,
                settled,
            ),
        )["id"]

    def _board(self):
        return standings.standings(self.conn, self.season)

    def _names(self):
        return [(row.place, row.username, row.points) for row in self._board()]

    # --- who the board includes ---

    def test_an_approved_player_with_a_completed_quiz_is_in(self):
        account_id = self._account("dock_owl", 1420)
        self._attempt(account_id)
        self.assertEqual(self._names(), [(1, "dock_owl", 1420)])

    def test_approval_alone_is_not_enough(self):
        """One valid completed Ranked quiz is also required (settled Q5)."""
        self._account("belt_runner", 900)
        self.assertEqual(self._board(), [])

    def test_a_completed_quiz_alone_is_not_enough(self):
        """Without the owner's approval there is no competition position."""
        account_id = self._account("tape_gull", 2000, approved=False)
        self._attempt(account_id)
        self.assertEqual(self._board(), [])

    def test_a_negative_score_still_qualifies(self):
        """The minimum is finishing a quiz, not doing well at one."""
        account_id = self._account("chute_hare", -40)
        self._attempt(account_id)
        self.assertEqual(self._names(), [(1, "chute_hare", -40)])

    def test_a_promotion_quiz_qualifies(self):
        account_id = self._account("ramp_moth", 1001)
        self._attempt(account_id, mode="promotion")
        self.assertEqual(self._names(), [(1, "ramp_moth", 1001)])

    def test_a_pre_season_quiz_does_not_qualify(self):
        account_id = self._account("dock_owl", 700)
        self._attempt(account_id, season=self.pre_season)
        self.assertEqual(self._board(), [])

    def test_a_tiebreak_attempt_alone_does_not_qualify(self):
        account_id = self._account("belt_runner", 700)
        self._attempt(account_id, mode="tiebreak")
        self.assertEqual(self._board(), [])

    def test_an_unfinished_attempt_does_not_qualify(self):
        account_id = self._account("tape_gull", 700)
        self._attempt(account_id, state="active", outcome=None)
        self.assertEqual(self._board(), [])

    def test_an_ended_or_void_attempt_does_not_qualify(self):
        """Quit, lost connection, ended at the close, void: none is completed."""
        for outcome in ("quit", "disconnect", "season_close", "outage_void", "launch_reset"):
            with self.subTest(outcome=outcome):
                account_id = self._account(f"ended_{outcome}", 700)
                self._attempt(account_id, outcome=outcome)
                self.assertEqual(
                    [row.username for row in self._board()], [], outcome
                )
                migrate.execute(
                    self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,)
                )

    def test_a_deleted_account_leaves_the_board(self):
        """Deleting before prizes are finalized withdraws the account."""
        account_id = self._account("dock_owl", 1420)
        self._attempt(account_id)
        kept = self._account("belt_runner", 900)
        self._attempt(kept)
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (account_id,)
        )
        self.assertEqual(self._names(), [(1, "belt_runner", 900)])

    def test_one_player_appears_once_however_many_quizzes(self):
        account_id = self._account("dock_owl", 1420)
        for _ in range(3):
            self._attempt(account_id)
        self.assertEqual(len(self._board()), 1)

    def test_a_player_with_no_balance_row_stands_at_zero(self):
        account_id = self._account("new_sorter", None)
        self._attempt(account_id)
        self.assertEqual(self._names(), [(1, "new_sorter", 0)])

    # --- order and places ---

    def test_the_board_runs_from_most_points_down(self):
        for name, points in (("tape_gull", 505), ("dock_owl", 1420), ("belt_runner", 910)):
            account_id = self._account(name, points)
            self._attempt(account_id)
        self.assertEqual(
            self._names(),
            [(1, "dock_owl", 1420), (2, "belt_runner", 910), (3, "tape_gull", 505)],
        )

    def test_equal_points_share_a_place_and_the_next_one_skips(self):
        """Nobody is second when two players are first: saying so would
        claim one of them is ahead, which only a tie-break quiz decides."""
        for name, points in (("dock_owl", 900), ("belt_runner", 900), ("tape_gull", 800)):
            account_id = self._account(name, points)
            self._attempt(account_id)
        # The two tied rows are listed alphabetically, which is only a
        # steady order to print them in: both carry place 1.
        self.assertEqual(
            self._names(),
            [(1, "belt_runner", 900), (1, "dock_owl", 900), (3, "tape_gull", 800)],
        )

    def test_a_tie_is_listed_in_the_same_order_every_time(self):
        """Not an order of merit: a board that reshuffled on each load would
        look like one player overtaking another without playing."""
        for name, points in (("dock_owl", 900), ("belt_runner", 900)):
            self._attempt(self._account(name, points))
        first = [row.username for row in self._board()]
        self.assertEqual(first, [row.username for row in self._board()])
        self.assertEqual(first, ["belt_runner", "dock_owl"])

    def test_a_tied_row_says_it_is_tied(self):
        for name, points in (("dock_owl", 900), ("belt_runner", 900), ("tape_gull", 800)):
            account_id = self._account(name, points)
            self._attempt(account_id)
        self.assertEqual([row.tied for row in self._board()], [True, True, False])

    def test_the_badge_comes_from_the_points_on_the_board(self):
        for name, points in (("dock_owl", 4001), ("belt_runner", 1500), ("tape_gull", 10)):
            account_id = self._account(name, points)
            self._attempt(account_id)
        self.assertEqual(
            [row.badge for row in self._board()], ["Challenger", "Bronze", "Iron"]
        )

    def test_place_of_finds_a_player_and_admits_when_it_cannot(self):
        account_id = self._account("dock_owl", 900)
        self._attempt(account_id)
        outsider = self._account("tape_gull", 5000, approved=False)
        board = self._board()
        self.assertEqual(standings.place_of(board, account_id), 1)
        self.assertIsNone(standings.place_of(board, outsider))
        self.assertIsNone(standings.place_of(board, uuid4()))

    def test_eligible_accounts_matches_the_board(self):
        account_id = self._account("dock_owl", 900)
        self._attempt(account_id)
        self._account("belt_runner", 5000)  # approved, no completed quiz
        self.assertEqual(standings.eligible_accounts(self.conn, self.season), [account_id])

    # --- the numbering rule on its own ---

    def test_places_are_numbered_without_a_database(self):
        rows = [
            {"id": uuid4(), "username": "a", "tag": "AAAAAA", "points": 10},
            {"id": uuid4(), "username": "b", "tag": "BBBBBB", "points": 10},
            {"id": uuid4(), "username": "c", "tag": "CCCCCC", "points": 10},
            {"id": uuid4(), "username": "d", "tag": "DDDDDD", "points": 5},
        ]
        placed = standings.place_rows(rows)
        self.assertEqual([row.place for row in placed], [1, 1, 1, 4])
        self.assertEqual([row.tied for row in placed], [True, True, True, False])

    def test_an_empty_season_has_an_empty_board(self):
        self.assertEqual(standings.place_rows([]), [])
        self.assertEqual(self._board(), [])

    # --- what the board must not carry ---

    def test_a_row_carries_no_private_field(self):
        """Tickets, flags and connection details never reach the board."""
        account_id = self._account("dock_owl", 900)
        self._attempt(account_id)
        row = self._board()[0]
        self.assertEqual(
            set(row.__dict__),
            {"place", "account_id", "username", "tag", "points", "badge", "tied"},
        )


if __name__ == "__main__":
    unittest.main()
