"""Player-requested Support tickets (issue #26, slice 1)."""
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

from backend.db import migrate, settings
from backend.auth.deletion import purge_deleted_accounts
from backend.ranked import engine, settlement
from backend.support import retention, tickets
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
            migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
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


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ReviewTests(TicketTestCase):
    def _owner(self):
        account = self._account()
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = true WHERE id = %s", (account,)
        )
        self.conn.commit()
        return account

    def _open(self, account=None, description=None):
        account = account or self._account()
        ticket = tickets.open_ticket(
            self.conn, account, self._ended_attempt(account), description=description
        )
        self.conn.commit()
        return account, ticket

    def test_a_reviewer_sees_open_tickets_with_their_evidence(self):
        owner = self._owner()
        account, ticket = self._open(description="It cut out.")
        rows = tickets.open_tickets_for_review(self.conn, owner)
        self.conn.commit()
        self.assertEqual([row["id"] for row in rows], [ticket])
        self.assertEqual(rows[0]["description"], "It cut out.")
        self.assertIn("events", rows[0])

    def test_review_returns_only_display_identity(self):
        owner = self._owner()
        self._open()
        row = tickets.open_tickets_for_review(self.conn, owner)[0]
        self.conn.commit()
        self.assertEqual(
            set(row) - {"events"},
            {"id", "attempt_id", "description", "opened_at", "username", "tag"},
        )

    def test_an_ordinary_player_cannot_review(self):
        account, _ = self._open()
        with self.assertRaises(tickets.NotAuthorizedError):
            tickets.open_tickets_for_review(self.conn, account)
        self.conn.rollback()

    def test_an_ordinary_player_cannot_close(self):
        owner = self._owner()
        account, ticket = self._open()
        with self.assertRaises(tickets.NotAuthorizedError):
            tickets.close_ticket(
                self.conn, account, ticket, "network_instability", clock=self.clock
            )
        self.conn.rollback()
        self.assertIsNone(tickets.ticket_for(self.conn, account, ticket)["closed_at"])

    def test_closing_as_network_instability(self):
        owner = self._owner()
        account, ticket = self._open()
        outcome = tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        stored = tickets.ticket_for(self.conn, account, ticket)
        self.assertEqual(outcome, "network_instability")
        self.assertEqual(stored["closed_outcome"], "network_instability")
        self.assertEqual(stored["closed_at"], self.clock.now())

    def test_closing_as_insufficient_evidence(self):
        owner = self._owner()
        account, ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, ticket, "insufficient_evidence", clock=self.clock
        )
        self.conn.commit()
        self.assertEqual(
            tickets.ticket_for(self.conn, account, ticket)["closed_outcome"],
            "insufficient_evidence",
        )

    def test_an_unknown_outcome_is_refused(self):
        owner = self._owner()
        _, ticket = self._open()
        with self.assertRaises(ValueError):
            tickets.close_ticket(self.conn, owner, ticket, "cheating", clock=self.clock)
        self.conn.rollback()

    def test_closing_twice_keeps_the_first_decision_and_time(self):
        owner = self._owner()
        account, ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        first = tickets.ticket_for(self.conn, account, ticket)["closed_at"]
        self.clock.advance(3600)
        again = tickets.close_ticket(
            self.conn, owner, ticket, "insufficient_evidence", clock=self.clock
        )
        self.conn.commit()
        stored = tickets.ticket_for(self.conn, account, ticket)
        self.assertEqual(again, "network_instability")
        self.assertEqual(stored["closed_outcome"], "network_instability")
        self.assertEqual(stored["closed_at"], first)

    def test_closing_changes_no_points(self):
        owner = self._owner()
        account, ticket = self._open()
        before = self._balance(account)
        tickets.close_ticket(
            self.conn, owner, ticket, "insufficient_evidence", clock=self.clock
        )
        self.conn.commit()
        self.assertEqual(self._balance(account), before)

    def test_closing_changes_no_account_access(self):
        owner = self._owner()
        account, ticket = self._open()
        before = migrate.fetch_one(
            self.conn,
            "SELECT is_owner, deleted_at FROM accounts WHERE id = %s",
            (account,),
        )
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        after = migrate.fetch_one(
            self.conn,
            "SELECT is_owner, deleted_at FROM accounts WHERE id = %s",
            (account,),
        )
        self.conn.commit()
        self.assertEqual(before, after)

    def test_a_closed_ticket_leaves_the_review_queue(self):
        owner = self._owner()
        _, ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.assertEqual(tickets.open_tickets_for_review(self.conn, owner), [])

    def test_reopening_puts_it_back_and_clears_the_closure(self):
        owner = self._owner()
        account, ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        tickets.reopen_ticket(self.conn, owner, ticket)
        self.conn.commit()
        stored = tickets.ticket_for(self.conn, account, ticket)
        self.assertIsNone(stored["closed_at"])
        self.assertIsNone(stored["closed_outcome"])
        self.assertEqual(
            [row["id"] for row in tickets.open_tickets_for_review(self.conn, owner)],
            [ticket],
        )

    def test_an_ordinary_player_cannot_reopen(self):
        owner = self._owner()
        account, ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        with self.assertRaises(tickets.NotAuthorizedError):
            tickets.reopen_ticket(self.conn, account, ticket)
        self.conn.rollback()

    def test_a_player_still_sees_only_their_own_after_closure(self):
        owner = self._owner()
        mine, my_ticket = self._open()
        theirs, their_ticket = self._open()
        tickets.close_ticket(
            self.conn, owner, their_ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.assertEqual([r["id"] for r in tickets.tickets_for(self.conn, mine)], [my_ticket])
        self.assertIsNone(tickets.ticket_for(self.conn, mine, their_ticket))


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RetentionTests(TicketTestCase):
    """A ticket and a flag about one attempt share one connection log."""

    DAY = 86400

    def _owner(self):
        account = self._account()
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = true WHERE id = %s", (account,)
        )
        self.conn.commit()
        return account

    def _flapping_attempt(self, account):
        """An ended attempt that earned a connection flag, with its events."""
        attempt_id = engine.start_attempt(
            self.conn, account, clock=self.clock, bank=self.bank
        )
        for _ in range(4):
            self.clock.advance(4)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.conn.commit()
        return attempt_id

    def _events(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return row["n"]

    def _flag_rows(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM connection_flags WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return row["n"]

    def _sweep(self):
        result = retention.purge_due_cases(self.conn, clock=self.clock)
        self.conn.commit()
        return result

    def test_a_closed_ticket_keeps_its_description_for_fourteen_days(self):
        owner = self._owner()
        account = self._account()
        ticket = tickets.open_ticket(
            self.conn, account, self._ended_attempt(account), description="It cut out."
        )
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(15 * self.DAY - 1)
        self.assertEqual(self._sweep()["descriptions"], 0)
        self.assertEqual(
            tickets.ticket_for(self.conn, account, ticket)["description"], "It cut out."
        )

    def test_a_closed_ticket_loses_its_description_after_fifteen_days(self):
        owner = self._owner()
        account = self._account()
        ticket = tickets.open_ticket(
            self.conn, account, self._ended_attempt(account), description="It cut out."
        )
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(15 * self.DAY)
        self.assertEqual(self._sweep()["descriptions"], 1)
        stored = tickets.ticket_for(self.conn, account, ticket)
        self.assertIsNone(stored["description"])
        # the ticket itself stays: the player still sees that they asked and
        # what the outcome was
        self.assertEqual(stored["closed_outcome"], "network_instability")

    def test_an_open_ticket_keeps_its_description_forever(self):
        account = self._account()
        ticket = tickets.open_ticket(
            self.conn, account, self._ended_attempt(account), description="Still open."
        )
        self.conn.commit()
        self.clock.advance(60 * self.DAY)
        self._sweep()
        self.assertEqual(
            tickets.ticket_for(self.conn, account, ticket)["description"], "Still open."
        )

    def test_an_open_ticket_holds_the_log_of_a_long_closed_flag(self):
        """The bug this slice exists to prevent."""
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt)
        self.conn.commit()
        from backend.ranked import flags

        flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        self.conn.commit()
        self.clock.advance(60 * self.DAY)
        self.assertEqual(self._sweep()["logs"], 0)
        self.assertGreater(self._events(attempt), 0)
        self.assertEqual(self._flag_rows(attempt), 1)
        self.assertIsNone(retention.shared_log_deletion_date(self.conn, attempt))

    def test_the_log_goes_fifteen_days_after_the_last_case_closes(self):
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt)
        self.conn.commit()
        from backend.ranked import flags

        flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        self.conn.commit()
        self.clock.advance(30 * self.DAY)
        tickets.close_ticket(
            self.conn, owner, ticket, "insufficient_evidence", clock=self.clock
        )
        self.conn.commit()
        last_closure = self.clock.now()
        self.assertEqual(
            retention.shared_log_deletion_date(self.conn, attempt),
            last_closure + timedelta(days=15),
        )
        self.clock.advance(15 * self.DAY - 1)
        self.assertEqual(self._sweep()["logs"], 0)
        self.assertGreater(self._events(attempt), 0)
        self.clock.advance(1)
        self.assertEqual(self._sweep()["logs"], 1)
        self.assertEqual(self._events(attempt), 0)
        self.assertEqual(self._flag_rows(attempt), 0)

    def test_reopening_a_ticket_stops_the_log_clock(self):
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt)
        self.conn.commit()
        from backend.ranked import flags

        flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(14 * self.DAY)
        tickets.reopen_ticket(self.conn, owner, ticket)
        self.conn.commit()
        self.clock.advance(60 * self.DAY)
        self.assertEqual(self._sweep()["logs"], 0)
        self.assertGreater(self._events(attempt), 0)
        self.assertIsNone(retention.shared_log_deletion_date(self.conn, attempt))

    def test_one_players_due_log_does_not_take_anothers(self):
        owner = self._owner()
        due_account, held_account = self._account(), self._account()
        due = self._flapping_attempt(due_account)
        held = self._flapping_attempt(held_account)
        from backend.ranked import flags

        flags.close_flag(self.conn, due, "network_instability", clock=self.clock)
        self.conn.commit()
        tickets.open_ticket(self.conn, held_account, held)
        self.conn.commit()
        self.clock.advance(60 * self.DAY)
        self.assertEqual(self._sweep()["logs"], 1)
        self.assertEqual(self._events(due), 0)
        self.assertGreater(self._events(held), 0)

    def test_an_attempt_with_no_case_keeps_its_events(self):
        account = self._account()
        attempt = engine.start_attempt(
            self.conn, account, clock=self.clock, bank=self.bank
        )
        self.clock.advance(4)
        engine.heartbeat(self.conn, attempt, clock=self.clock)
        engine.quit_attempt(self.conn, attempt, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt, clock=self.clock)
        self.conn.commit()
        before = self._events(attempt)
        self.clock.advance(60 * self.DAY)
        self._sweep()
        self.assertEqual(self._events(attempt), before)

    def test_scores_and_history_survive_the_sweep(self):
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt)
        from backend.ranked import flags

        flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(20 * self.DAY)
        self._sweep()
        kept = migrate.fetch_one(
            self.conn,
            "SELECT (SELECT COUNT(*) FROM attempts WHERE id = %(a)s) AS attempts,"
            " (SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = %(a)s) AS answers,"
            " (SELECT COUNT(*) FROM settlements WHERE attempt_id = %(a)s) AS settlements",
            {"a": attempt},
        )
        self.conn.commit()
        self.assertEqual(
            (kept["attempts"], kept["answers"], kept["settlements"]), (1, 1, 1)
        )
        # and the ticket row itself, so the player still sees the case existed
        self.assertIsNotNone(tickets.ticket_for(self.conn, account, ticket))

    def test_a_repeat_sweep_finds_nothing(self):
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt, description="x")
        from backend.ranked import flags

        flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(20 * self.DAY)
        self.assertEqual(self._sweep(), {"descriptions": 1, "logs": 1})
        self.assertEqual(self._sweep(), {"descriptions": 0, "logs": 0})


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AccountDeletionTests(TicketTestCase):
    """A confirmed wipe takes the account's own case detail, and nobody else's."""

    def _owner(self):
        account = self._account()
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = true WHERE id = %s", (account,)
        )
        self.conn.commit()
        return account

    def _flapping_attempt(self, account):
        attempt_id = engine.start_attempt(
            self.conn, account, clock=self.clock, bank=self.bank
        )
        for _ in range(4):
            self.clock.advance(4)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.conn.commit()
        return attempt_id

    def _count(self, sql, params):
        row = migrate.fetch_one(self.conn, sql, params)
        self.conn.commit()
        return row["n"]

    def _delete_and_purge(self, account):
        migrate.execute(
            self.conn,
            "UPDATE accounts SET deleted_at = now() WHERE id = %s",
            (account,),
        )
        self.conn.commit()
        return purge_deleted_accounts(self.conn)

    def test_an_open_ticket_does_not_block_the_wipe(self):
        account = self._account()
        attempt = self._flapping_attempt(account)
        tickets.open_ticket(self.conn, account, attempt, description="still open")
        self.conn.commit()
        self.assertEqual(self._delete_and_purge(account), 1)
        self.assertEqual(
            self._count("SELECT COUNT(*) AS n FROM accounts WHERE id=%s", (account,)), 0
        )

    def test_the_wipe_takes_the_ticket_and_its_evidence(self):
        account = self._account()
        attempt = self._flapping_attempt(account)
        tickets.open_ticket(self.conn, account, attempt, description="private note")
        self.conn.commit()
        self._delete_and_purge(account)
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM support_tickets WHERE account_id=%s",
                (account,),
            ),
            0,
        )
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id=%s",
                (attempt,),
            ),
            0,
        )
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM connection_flags WHERE attempt_id=%s",
                (attempt,),
            ),
            0,
        )

    def test_a_closed_case_is_wiped_too_even_inside_the_fifteen_days(self):
        owner = self._owner()
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt, description="note")
        tickets.close_ticket(
            self.conn, owner, ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self.clock.advance(86400)  # one day: far inside the retention window
        self._delete_and_purge(account)
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM support_tickets WHERE id=%s", (ticket,)
            ),
            0,
        )

    def test_another_players_case_survives_the_wipe(self):
        going, staying = self._account(), self._account()
        going_attempt = self._flapping_attempt(going)
        staying_attempt = self._flapping_attempt(staying)
        tickets.open_ticket(self.conn, going, going_attempt, description="mine")
        staying_ticket = tickets.open_ticket(
            self.conn, staying, staying_attempt, description="theirs"
        )
        self.conn.commit()
        self._delete_and_purge(going)
        kept = tickets.ticket_for(self.conn, staying, staying_ticket)
        self.assertIsNotNone(kept)
        self.assertEqual(kept["description"], "theirs")
        self.assertGreater(
            self._count(
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id=%s",
                (staying_attempt,),
            ),
            0,
        )
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM connection_flags WHERE attempt_id=%s",
                (staying_attempt,),
            ),
            1,
        )

    def test_the_review_queue_loses_only_the_deleted_players_case(self):
        owner = self._owner()
        going, staying = self._account(), self._account()
        tickets.open_ticket(self.conn, going, self._ended_attempt(going))
        staying_ticket = tickets.open_ticket(
            self.conn, staying, self._ended_attempt(staying)
        )
        self.conn.commit()
        self._delete_and_purge(going)
        self.assertEqual(
            [row["id"] for row in tickets.open_tickets_for_review(self.conn, owner)],
            [staying_ticket],
        )

    def test_the_retention_sweep_still_runs_after_a_wipe(self):
        owner = self._owner()
        going, staying = self._account(), self._account()
        going_attempt = self._flapping_attempt(going)
        staying_attempt = self._flapping_attempt(staying)
        going_ticket = tickets.open_ticket(self.conn, going, going_attempt)
        staying_ticket = tickets.open_ticket(self.conn, staying, staying_attempt)
        from backend.ranked import flags

        flags.close_flag(self.conn, going_attempt, "network_instability", clock=self.clock)
        flags.close_flag(
            self.conn, staying_attempt, "network_instability", clock=self.clock
        )
        tickets.close_ticket(
            self.conn, owner, staying_ticket, "network_instability", clock=self.clock
        )
        self.conn.commit()
        self._delete_and_purge(going)
        self.clock.advance(20 * 86400)
        result = retention.purge_due_cases(self.conn, clock=self.clock)
        self.conn.commit()
        # the remaining player's case is due and swept; the deleted one left
        # nothing behind for the sweep to trip on
        self.assertEqual(result["logs"], 1)
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id=%s",
                (staying_attempt,),
            ),
            0,
        )

    def test_the_database_refuses_a_ticket_about_another_accounts_attempt(self):
        """Defence in depth: open_ticket refuses it, and so does the schema.

        Every Support read filters by account_id. A ticket pointing at
        another player's attempt would pass every ownership check — the
        check is on the ticket — while showing a reviewer that player's
        connection events.
        """
        mine, theirs = self._account(), self._account()
        their_attempt = self._ended_attempt(theirs)
        with self.assertRaises(Exception) as caught:
            migrate.execute(
                self.conn,
                "INSERT INTO support_tickets (account_id, attempt_id) VALUES (%s, %s)",
                (mine, their_attempt),
            )
        self.conn.rollback()
        self.assertIn("support_tickets_attempt_same_account", str(caught.exception))

    def test_automatic_handling_runs_with_no_reviewer(self):
        """#26 box 6: admins offline.

        Nothing waits for a reviewer. An open ticket stays open for ever
        without one, and the retention sweep keeps working around it.
        """
        account = self._account()
        attempt = self._flapping_attempt(account)
        ticket = tickets.open_ticket(self.conn, account, attempt, description="note")
        self.conn.commit()
        # no owner exists at all, so no review is possible
        self.assertEqual(
            self._count("SELECT COUNT(*) AS n FROM accounts WHERE is_owner", ()), 0
        )
        self.clock.advance(365 * 86400)
        result = retention.purge_due_cases(self.conn, clock=self.clock)
        self.conn.commit()
        self.assertEqual(result, {"descriptions": 0, "logs": 0})
        still = tickets.ticket_for(self.conn, account, ticket)
        self.assertIsNone(still["closed_at"])
        self.assertEqual(still["description"], "note")
        self.assertGreater(
            self._count(
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id=%s",
                (attempt,),
            ),
            0,
        )

    def test_a_wipe_during_the_retention_window_takes_the_case_with_it(self):
        """#26 box 6: a deletion racing the retention clock.

        A case closed but not yet purged, and the account deleted before the
        fifteen days are up. The wipe wins: nothing of that account is left
        for the sweep to find, and the sweep still runs cleanly afterwards.
        """
        owner = self._owner()
        going, staying = self._account(), self._account()
        going_attempt = self._flapping_attempt(going)
        staying_attempt = self._flapping_attempt(staying)
        going_ticket = tickets.open_ticket(self.conn, going, going_attempt, description="x")
        staying_ticket = tickets.open_ticket(self.conn, staying, staying_attempt, description="y")
        from backend.ranked import flags

        for attempt in (going_attempt, staying_attempt):
            flags.close_flag(self.conn, attempt, "network_instability", clock=self.clock)
        for ticket in (going_ticket, staying_ticket):
            tickets.close_ticket(
                self.conn, owner, ticket, "network_instability", clock=self.clock
            )
        self.conn.commit()

        self.clock.advance(7 * 86400)  # halfway through the window
        self._delete_and_purge(going)

        # nothing of the deleted account survives, window or not
        for table, column in (
            ("support_tickets", "account_id"),
            ("attempts", "account_id"),
        ):
            self.assertEqual(
                self._count(
                    f"SELECT COUNT(*) AS n FROM {table} WHERE {column}=%s", (going,)
                ),
                0,
                table,
            )
        self.assertEqual(
            self._count(
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id=%s",
                (going_attempt,),
            ),
            0,
        )

        # and the other player's case is still on its own clock
        self.clock.advance(8 * 86400)
        result = retention.purge_due_cases(self.conn, clock=self.clock)
        self.conn.commit()
        self.assertEqual(result, {"descriptions": 1, "logs": 1})
        self.assertIsNone(
            tickets.ticket_for(self.conn, staying, staying_ticket)["description"]
        )
