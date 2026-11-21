"""Recovery messages: the rule (issue #251).

A message is a note to the owner and nothing more. These tests hold the
bounds on it and who may read it.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.auth import recovery_messages
from backend.db import migrate, settings

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessageTests(unittest.TestCase):
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
        self.clock = FakeClock(T0)
        self.owner = self._account("the_owner", "OWN001", owner=True)
        self.player = self._account("dock_owl", "DCK002")
        self.conn.commit()

    def _account(self, name, tag, *, owner=False):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (name, name.lower(), tag, owner),
        )["id"]

    def _leave(self, body="I lost my login ID"):
        recovery_messages.leave_message(self.conn, body, clock=self.clock)

    def _bodies(self):
        return [m["body"] for m in recovery_messages.list_messages(self.conn, self.owner)]

    # --- leaving one ---

    def test_a_message_is_stored_trimmed(self):
        self._leave("  I am Sam from the night sort  \n")
        self.assertEqual(self._bodies(), ["I am Sam from the night sort"])

    def test_empty_and_overlong_messages_are_refused(self):
        for body in ("", "   \n ", "x" * 501, None):
            with self.assertRaises(recovery_messages.MessageRefused):
                self._leave(body)
        self._leave("x" * 500)
        self.assertEqual(len(self._bodies()), 1)

    def test_the_inbox_has_a_ceiling_of_unresolved_messages(self):
        migrate.execute(
            self.conn,
            "INSERT INTO recovery_messages (body)"
            " SELECT 'filler' FROM generate_series(1, %s)",
            (recovery_messages.MAX_UNRESOLVED,),
        )
        with self.assertRaises(recovery_messages.InboxFull):
            self._leave()
        # resolving one makes room again
        one = recovery_messages.list_messages(self.conn, self.owner, limit=1)[0]["id"]
        recovery_messages.resolve(self.conn, self.owner, one, clock=self.clock)
        self._leave("room again")

    def test_a_message_naming_an_account_touches_no_account(self):
        before = migrate.fetch_all(self.conn, "SELECT * FROM accounts ORDER BY id")
        self._leave("I am dock_owl #DCK002")
        self._leave("I am nobody_here #ZZZ999")
        after = migrate.fetch_all(self.conn, "SELECT * FROM accounts ORDER BY id")
        self.assertEqual(before, after)

    # --- reading and resolving ---

    def test_only_the_owner_may_list_or_resolve(self):
        self._leave()
        with self.assertRaises(recovery_messages.NotOwner):
            recovery_messages.list_messages(self.conn, self.player)
        with self.assertRaises(recovery_messages.NotOwner):
            recovery_messages.resolve(self.conn, self.player, uuid4(), clock=self.clock)

    def test_open_messages_come_first_then_newest(self):
        self._leave("oldest")
        self.clock.moment = T0 + timedelta(minutes=1)
        self._leave("middle")
        self.clock.moment = T0 + timedelta(minutes=2)
        self._leave("newest")
        middle = next(
            m["id"] for m in recovery_messages.list_messages(self.conn, self.owner)
            if m["body"] == "middle"
        )
        recovery_messages.resolve(self.conn, self.owner, middle, clock=self.clock)
        self.assertEqual(self._bodies(), ["newest", "oldest", "middle"])

    def test_resolving_records_when_and_is_idempotent(self):
        self._leave()
        message = recovery_messages.list_messages(self.conn, self.owner)[0]["id"]
        self.clock.moment = T0 + timedelta(hours=1)
        self.assertTrue(recovery_messages.resolve(self.conn, self.owner, message, clock=self.clock))
        self.clock.moment = T0 + timedelta(hours=5)
        self.assertTrue(recovery_messages.resolve(self.conn, self.owner, message, clock=self.clock))
        row = recovery_messages.list_messages(self.conn, self.owner)[0]
        self.assertEqual(row["resolved_at"], T0 + timedelta(hours=1))

    def test_resolving_an_unknown_message_reports_it(self):
        self.assertFalse(
            recovery_messages.resolve(self.conn, self.owner, uuid4(), clock=self.clock)
        )
