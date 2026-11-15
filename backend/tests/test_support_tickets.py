"""Player-requested Support tickets (issue #26, slice 1)."""
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

from backend.db import migrate, settings
from backend.ranked import engine, settlement
from backend.support import tickets
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class TicketTestCase(unittest.TestCase):
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
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES ('pre_season', 'Pre', %s)",
            (T0 - timedelta(days=1),),
        )
        self.conn.commit()
        self._accounts = 0

    def _account(self, points=500):
        self._accounts += 1
        tag = f"T{self._accounts:05d}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"tkt_{tag.lower()}", f"tkt_{tag.lower()}", tag),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
            (row["id"], points),
        )
        self.conn.commit()
        return row["id"]

    def _ended_attempt(self, account_id):
        attempt_id = engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.conn.commit()
        return attempt_id

    def _balance(self, account_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT current_points FROM balances WHERE account_id = %s",
            (account_id,),
        )
        self.conn.commit()
        return row["current_points"]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OpeningTests(TicketTestCase):
    def test_a_player_opens_a_ticket_about_their_own_attempt(self):
        account = self._account()
        attempt = self._ended_attempt(account)
        ticket_id = tickets.open_ticket(
            self.conn, account, attempt, description="The quiz stopped answering."
        )
        self.conn.commit()
        stored = tickets.ticket_for(self.conn, account, ticket_id)
        self.assertEqual(stored["attempt_id"], attempt)
        self.assertEqual(stored["description"], "The quiz stopped answering.")
        self.assertIsNone(stored["closed_at"])

    def test_the_description_is_optional(self):
        account = self._account()
        ticket_id = tickets.open_ticket(self.conn, account, self._ended_attempt(account))
        self.conn.commit()
        self.assertIsNone(tickets.ticket_for(self.conn, account, ticket_id)["description"])

    def test_a_blank_description_is_stored_as_none(self):
        account = self._account()
        ticket_id = tickets.open_ticket(
            self.conn, account, self._ended_attempt(account), description="   "
        )
        self.conn.commit()
        self.assertIsNone(tickets.ticket_for(self.conn, account, ticket_id)["description"])

    def test_opening_changes_no_points(self):
        account = self._account(points=640)
        attempt = self._ended_attempt(account)
        # Read the balance after the attempt has settled: quitting costs 10,
        # and that deduction belongs to the quiz, not to Support.
        before = self._balance(account)
        tickets.open_ticket(self.conn, account, attempt)
        self.conn.commit()
        self.assertEqual(self._balance(account), before)

    def test_another_players_attempt_is_refused(self):
        mine, theirs = self._account(), self._account()
        their_attempt = self._ended_attempt(theirs)
        with self.assertRaises(tickets.AttemptNotYoursError):
            tickets.open_ticket(self.conn, mine, their_attempt)
        self.conn.rollback()

    def test_an_attempt_that_does_not_exist_is_refused_the_same_way(self):
        account = self._account()
        missing = "00000000-0000-0000-0000-000000000000"
        with self.assertRaises(tickets.AttemptNotYoursError):
            tickets.open_ticket(self.conn, account, missing)
        self.conn.rollback()

    def test_a_second_request_about_the_same_attempt_is_refused(self):
        account = self._account()
        attempt = self._ended_attempt(account)
        tickets.open_ticket(self.conn, account, attempt)
        self.conn.commit()
        with self.assertRaises(tickets.TicketAlreadyOpenError):
            tickets.open_ticket(self.conn, account, attempt)
        self.conn.rollback()
        self.assertEqual(len(tickets.tickets_for(self.conn, account)), 1)

    def test_two_players_can_each_have_a_ticket_about_their_own_attempt(self):
        one, two = self._account(), self._account()
        tickets.open_ticket(self.conn, one, self._ended_attempt(one))
        tickets.open_ticket(self.conn, two, self._ended_attempt(two))
        self.conn.commit()
        self.assertEqual(len(tickets.tickets_for(self.conn, one)), 1)
        self.assertEqual(len(tickets.tickets_for(self.conn, two)), 1)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class VisibilityTests(TicketTestCase):
    def test_a_player_sees_only_their_own_tickets(self):
        mine, theirs = self._account(), self._account()
        tickets.open_ticket(self.conn, mine, self._ended_attempt(mine))
        tickets.open_ticket(self.conn, theirs, self._ended_attempt(theirs))
        self.conn.commit()
        self.assertEqual(len(tickets.tickets_for(self.conn, mine)), 1)
        self.assertEqual(len(tickets.tickets_for(self.conn, theirs)), 1)

    def test_another_players_ticket_is_not_readable_by_id(self):
        mine, theirs = self._account(), self._account()
        their_ticket = tickets.open_ticket(self.conn, theirs, self._ended_attempt(theirs))
        self.conn.commit()
        self.assertIsNone(tickets.ticket_for(self.conn, mine, their_ticket))

    def test_tickets_come_back_newest_first(self):
        account = self._account()
        first = tickets.open_ticket(self.conn, account, self._ended_attempt(account))
        self.clock.advance(60)
        self.conn.commit()
        migrate.execute(
            self.conn,
            "UPDATE support_tickets SET opened_at = %s WHERE id = %s",
            (T0 - timedelta(hours=1), first),
        )
        second = tickets.open_ticket(self.conn, account, self._ended_attempt(account))
        self.conn.commit()
        self.assertEqual(
            [row["id"] for row in tickets.tickets_for(self.conn, account)],
            [second, first],
        )

    def test_a_player_with_no_tickets_sees_none(self):
        self.assertEqual(tickets.tickets_for(self.conn, self._account()), [])


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class NoAutomaticTicketTests(TicketTestCase):
    def test_settling_an_attempt_creates_no_ticket(self):
        account = self._account()
        self._ended_attempt(account)
        self.assertEqual(tickets.tickets_for(self.conn, account), [])

    def test_a_flagged_attempt_creates_no_ticket(self):
        account = self._account()
        attempt_id = engine.start_attempt(
            self.conn, account, clock=self.clock, bank=self.bank
        )
        for _ in range(4):
            self.clock.advance(4)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.conn.commit()
        flagged = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM connection_flags WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        self.assertEqual(flagged["n"], 1, "the attempt should be flagged")
        self.assertEqual(
            tickets.tickets_for(self.conn, account),
            [],
            "a flag must never become a ticket",
        )
