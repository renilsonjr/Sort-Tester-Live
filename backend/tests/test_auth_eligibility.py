"""Recording the owner's prize-eligibility approval (issue #11, slice 1).

Each test is named after the rule it holds, because the rules are the
owner's settled Q5 rather than decisions made in the code.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.auth import eligibility
from backend.db import migrate, settings
from backend.ranked import standings

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class FixedClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class EligibilityTests(unittest.TestCase):
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
        self.clock = FixedClock(T0)
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak Season', %s, %s) RETURNING id",
            (T0 - timedelta(days=1), T0 + timedelta(days=7)),
        )["id"]
        self.owner = self._account("the_owner", owner=True)
        self.player = self._account("dock_owl")
        self.conn.commit()
        self._accounts = 0

    def _account(self, name, *, owner=False):
        tag = f"{name[:3].upper()}{abs(hash(name)) % 1000:03d}"
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (name, name.lower(), tag, owner),
        )["id"]

    def _approve(self, account_id=None, reference="twilight-primary-1", owner=None):
        return eligibility.approve(
            self.conn,
            owner or self.owner,
            account_id or self.player,
            reference,
            clock=self.clock,
        )

    # --- who may approve ---

    def test_the_owner_approves_a_sorter(self):
        approval = self._approve()
        self.assertEqual(approval.username, "dock_owl")
        self.assertEqual(approval.roster_reference, "twilight-primary-1")

    def test_a_player_cannot_approve_anybody(self):
        """There is no delegation: the owner flag is the whole authority."""
        other = self._account("belt_runner")
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(owner=other)
        self.assertIn("Only the owner", caught.exception.reason)
        self.assertEqual(self._links(), [])

    def test_a_player_cannot_withdraw_or_list(self):
        self._approve()
        other = self._account("belt_runner")
        for call in (
            lambda: eligibility.withdraw(self.conn, other, self.player),
            lambda: eligibility.approvals(self.conn, other),
        ):
            with self.assertRaises(eligibility.EligibilityError):
                call()

    def test_the_owner_cannot_approve_themselves(self):
        """Deciding who wins and winning is the one combination the rule
        cannot allow."""
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(account_id=self.owner)
        self.assertIn("own account", caught.exception.reason)
        self.assertEqual(self._links(), [])

    def test_a_deleted_owner_account_approves_nothing(self):
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (self.owner,)
        )
        with self.assertRaises(eligibility.EligibilityError):
            self._approve()

    # --- one sorter, one account ---

    def test_the_same_sorter_cannot_hold_two_approved_accounts(self):
        """One prize-eligible account and at most one hat per sorter."""
        self._approve()
        second = self._account("dock_owl_spare")
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(account_id=second, reference="twilight-primary-1")
        self.assertIn("already has an approved account", caught.exception.reason)
        self.assertEqual(len(self._links()), 1)

    def test_approving_the_same_account_twice_is_refused(self):
        self._approve()
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(reference="twilight-primary-2")
        self.assertIn("already approved", caught.exception.reason)

    def test_a_mistyped_tag_can_be_corrected(self):
        """The owner approved the wrong account and withdrew it straight
        away. Nothing was played on it, so the right account can take the
        place. This is a correction, not a swap."""
        wrong = self._account("belt_runner")
        self._approve(account_id=wrong)
        eligibility.withdraw(self.conn, self.owner, wrong)
        self._approve(account_id=self.player, reference="twilight-primary-1")
        self.assertEqual([row.username for row in self._all()], ["dock_owl"])

    def test_the_approval_cannot_move_once_the_sorter_has_played(self):
        """The approved account is fixed for the official season: no
        eligibility swap. Points earned on one account cannot become
        eligibility on another."""
        self._approve()
        self._completed_quiz(self.player)
        eligibility.withdraw(self.conn, self.owner, self.player)
        replacement = self._account("dock_owl_two")
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(account_id=replacement, reference="twilight-primary-1")
        self.assertIn("already played this season", caught.exception.reason)
        self.assertEqual(self._all(), [])

    def test_the_same_account_can_be_approved_again_after_a_withdrawal(self):
        """Recovery uses the same account, so putting back an approval the
        owner took back by mistake is not a swap, played or not."""
        self._approve()
        self._completed_quiz(self.player)
        eligibility.withdraw(self.conn, self.owner, self.player)
        self._approve(reference="twilight-primary-1")
        self.assertEqual([row.username for row in self._all()], ["dock_owl"])

    def test_a_deleted_sorter_cannot_come_back_on_a_fresh_account(self):
        """Deletion withdraws the account from the season, and a new
        account "cannot regain this season's prizes". The season marker
        says so after the account itself is gone."""
        migrate.execute(
            self.conn,
            "INSERT INTO season_markers (roster_reference, season, ineligible)"
            " VALUES (%s, %s, true)",
            ("twilight-primary-1", str(self.season)),
        )
        fresh = self._account("dock_owl_fresh")
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(account_id=fresh, reference="twilight-primary-1")
        self.assertIn("out of this season", caught.exception.reason)

    def test_a_tiebreak_attempt_does_not_count_as_having_played(self):
        """A tie-break alone never satisfied the one-quiz minimum, so it
        cannot stand for accumulation either."""
        self._approve()
        self._completed_quiz(self.player, mode="tiebreak")
        eligibility.withdraw(self.conn, self.owner, self.player)
        replacement = self._account("dock_owl_two")
        self._approve(account_id=replacement, reference="twilight-primary-1")
        self.assertEqual([row.username for row in self._all()], ["dock_owl_two"])

    # --- when approval is open ---

    def test_no_approval_after_the_season_ends(self):
        """From the end onward, including the finishing window (#23)."""
        self.clock.moment = T0 + timedelta(days=8)
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve()
        self.assertIn("no longer open", caught.exception.reason)

    def test_an_approval_recorded_before_the_end_stands_afterwards(self):
        self._approve()
        self.clock.moment = T0 + timedelta(days=8)
        self.assertEqual(len(self._all()), 1)

    def test_withdrawal_still_works_after_the_season_ends(self):
        """A wrong approval must be removable even once the season closed:
        leaving it in would hand a hat to somebody not entitled to it."""
        self._approve()
        self.clock.moment = T0 + timedelta(days=8)
        eligibility.withdraw(self.conn, self.owner, self.player)
        self.assertEqual(self._all(), [])

    # --- what approving does not do ---

    def test_approving_changes_no_points_and_no_badge(self):
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 640)",
            (self.player,),
        )
        self._approve()
        points = migrate.fetch_one(
            self.conn,
            "SELECT current_points FROM balances WHERE account_id = %s",
            (self.player,),
        )["current_points"]
        self.assertEqual(points, 640)

    def test_approving_alone_does_not_put_anybody_in_the_standings(self):
        """The second half of the rule, one completed quiz, is still
        required: approval is necessary, not sufficient."""
        self._approve()
        self.assertEqual(standings.standings(self.conn, self.season), [])

    def test_withdrawing_leaves_the_account_able_to_play(self):
        self._approve()
        eligibility.withdraw(self.conn, self.owner, self.player)
        row = migrate.fetch_one(
            self.conn, "SELECT deleted_at FROM accounts WHERE id = %s", (self.player,)
        )
        self.assertIsNone(row["deleted_at"])

    def test_the_listing_carries_no_points_or_history(self):
        self._approve()
        row = self._all()[0]
        self.assertEqual(
            set(row.__dict__),
            {"account_id", "username", "tag", "roster_reference", "established_at"},
        )

    # --- refusals that say only what the asker already knows ---

    def test_an_unknown_account_is_refused(self):
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(account_id=uuid4())
        self.assertIn("No such account", caught.exception.reason)

    def test_a_deleted_account_cannot_be_approved(self):
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (self.player,)
        )
        with self.assertRaises(eligibility.EligibilityError):
            self._approve()

    def test_a_blank_roster_reference_is_refused(self):
        for blank in ("", "   ", None):
            with self.subTest(reference=blank):
                with self.assertRaises(eligibility.EligibilityError):
                    self._approve(reference=blank)

    def test_a_reference_longer_than_the_column_is_refused(self):
        with self.assertRaises(eligibility.EligibilityError) as caught:
            self._approve(reference="x" * 129)
        self.assertIn("too long", caught.exception.reason)

    def test_surrounding_space_is_trimmed_rather_than_stored(self):
        approval = self._approve(reference="  twilight-primary-9  ")
        self.assertEqual(approval.roster_reference, "twilight-primary-9")

    def test_withdrawing_an_account_that_is_not_approved_is_refused(self):
        with self.assertRaises(eligibility.EligibilityError):
            eligibility.withdraw(self.conn, self.owner, self.player)

    # --- helpers ---

    def _completed_quiz(self, account_id, mode="normal"):
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, %s, %s) RETURNING id",
            (account_id, mode, self.season),
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at)"
            " VALUES (%s, %s, %s, %s, 'finalized', 'completed', now())",
            (account_id, assignment_id, mode, self.season),
        )

    def _links(self):
        return migrate.fetch_all(self.conn, "SELECT * FROM participant_links")

    def _all(self):
        return eligibility.approvals(self.conn, self.owner)


if __name__ == "__main__":
    unittest.main()
