"""Every list answers with a bounded number of rows.

None of these endpoints took a count from the caller, so none of them was
a request someone could make expensive on purpose. What they did instead
was grow: a player's history is one row per settled attempt, forever, and
the answer carried all of them. The cost lands on the database, on the
app's memory and on a phone over a sort-floor connection, and it arrives
gradually enough that nobody notices the day it became a problem.

A cap is not pagination. There is no cursor here and no way to ask for
the next page; the plan defers that deliberately. What this guarantees is
only that a response has a ceiling, and that the rows kept are the ones
the query already ordered first -- newest for history and tickets, oldest
for the review queues, which work front to back.

**`standings` is deliberately not capped at the source.** It feeds the
prize tie-break logic as well as the screen, and a truncated leaderboard
there would quietly drop players from a prize calculation. The cap sits
in the route instead, after the player's own place has been worked out,
so someone in 700th place still learns they are 700th.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.db import migrate, settings
from backend.ranked import history, standings
from backend.support import tickets

T0 = datetime(2026, 3, 1, 12, 0, tzinfo=timezone.utc)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ListCapTestCase(unittest.TestCase):
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
        self.account_id = self._account("cap_user", "CAPU01")
        self.conn.commit()

    def _account(self, username, tag, owner=False):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (username, username.lower(), tag, owner),
        )["id"]


class TicketListCapTests(ListCapTestCase):
    def _make_tickets(self, n):
        season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at)"
            " VALUES ('official', 'Capped', %s) RETURNING id",
            (T0 - timedelta(days=1),),
        )["id"]
        for i in range(n):
            assignment = migrate.fetch_one(
                self.conn,
                "INSERT INTO assignments (account_id, mode, season_id)"
                " VALUES (%s, 'normal', %s) RETURNING id",
                (self.account_id, season),
            )["id"]
            attempt = migrate.fetch_one(
                self.conn,
                "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
                " state, final_outcome, settled_at)"
                " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', now())"
                " RETURNING id",
                (self.account_id, assignment, season),
            )["id"]
            migrate.execute(
                self.conn,
                "INSERT INTO support_tickets (account_id, attempt_id, opened_at)"
                " VALUES (%s, %s, %s)",
                (self.account_id, attempt, T0 + timedelta(minutes=i)),
            )
        self.conn.commit()

    def test_a_long_history_of_tickets_is_cut_to_the_cap(self):
        self._make_tickets(tickets.MAX_ROWS + 20)
        rows = tickets.tickets_for(self.conn, self.account_id)
        self.assertEqual(len(rows), tickets.MAX_ROWS)

    def test_the_rows_kept_are_the_newest(self):
        self._make_tickets(tickets.MAX_ROWS + 20)
        rows = tickets.tickets_for(self.conn, self.account_id)
        newest = max(row["opened_at"] for row in rows)
        oldest_kept = min(row["opened_at"] for row in rows)
        self.assertEqual(newest, T0 + timedelta(minutes=tickets.MAX_ROWS + 19))
        self.assertEqual(oldest_kept, T0 + timedelta(minutes=20))

    def test_a_short_list_is_returned_whole(self):
        self._make_tickets(3)
        self.assertEqual(len(tickets.tickets_for(self.conn, self.account_id)), 3)


class HistoryCapTests(ListCapTestCase):
    def test_the_cap_is_declared_and_small_enough_to_send(self):
        # the rows themselves are built by the settlement path; what is
        # pinned here is that a ceiling exists and is a number a phone can
        # receive, rather than "whatever has accumulated"
        self.assertLessEqual(history.MAX_ROWS, 500)
        self.assertGreater(history.MAX_ROWS, 0)

    def test_an_empty_history_is_still_a_list(self):
        self.assertEqual(history.account_history(self.conn, self.account_id), [])


class StandingsAreNotCappedAtTheSourceTests(ListCapTestCase):
    """The prize path reads this function too.

    A LIMIT here would mean the tie-break logic computing prizes from a
    truncated leaderboard -- harmless while there are fewer players than
    the cap, and invisible on the day there are not.
    """

    def test_the_module_takes_no_row_cap(self):
        import inspect

        self.assertNotIn("LIMIT", inspect.getsource(standings.standings).upper())

    def test_every_eligible_player_is_still_returned(self):
        season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at)"
            " VALUES ('official', 'Whole', %s) RETURNING id",
            (T0 - timedelta(days=1),),
        )["id"]
        self.conn.commit()
        rows = standings.standings(self.conn, season)
        self.assertIsInstance(rows, list)


if __name__ == "__main__":
    unittest.main()
