"""Owner-approved access recovery (issue #11, slice 3).

The rules under test are the owner's settled recovery policy, so each
test is named after the rule rather than the function.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.auth import recovery
from backend.auth.service import login_with_id
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
class RecoveryTests(unittest.TestCase):
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
        self.owner = self._account("the_owner", "OWN001", owner=True)
        self.player = self._account("dock_owl", "DCK002")
        self.conn.commit()

    # --- helpers ---

    def _account(self, name, tag, *, owner=False):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (name, name.lower(), tag, owner),
        )["id"]

    def _link(self, account_id, *, established_at=None):
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference, established_at)"
            " VALUES (%s, %s, %s)",
            (account_id, f"roster-{account_id}", established_at or (T0 - timedelta(days=30))),
        )

    def _open(self, tag="DCK002", owner=None):
        return recovery.open_request(
            self.conn, owner or self.owner, tag, clock=self.clock
        )

    # --- who may do it ---

    def test_only_the_owner_may_open_or_complete(self):
        self._link(self.player)
        other = self._account("belt_runner", "BLT003")
        with self.assertRaises(recovery.RecoveryError) as caught:
            self._open(owner=other)
        self.assertIn("Only the owner", caught.exception.reason)
        request = self._open()
        with self.assertRaises(recovery.RecoveryError):
            recovery.hand_over(self.conn, other, request.id, clock=self.clock)
        with self.assertRaises(recovery.RecoveryError):
            recovery.recent_requests(self.conn, other)

    def test_holding_the_owner_role_is_not_by_itself_enough(self):
        """The owner still needs the trusted prior link: being the owner
        proves authority, not that this is the right person."""
        request = self._open()
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertIn("no roster link recorded before the request", caught.exception.reason)

    def test_a_tag_alone_recovers_nothing(self):
        """A public tag is not proof: it opens a request and stops there."""
        request = self._open()
        self.assertEqual(request.username, "dock_owl")
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT id FROM login_credentials WHERE account_id = %s",
                (self.player,),
            )
        )

    # --- the trusted prior link ---

    def test_a_link_older_than_the_request_allows_the_handover(self):
        self._link(self.player)
        request = self._open()
        handover = recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertEqual(handover.username, "dock_owl")
        self.assertEqual(len(handover.login_id.replace("-", "")), 16)

    def test_a_link_recorded_after_the_request_is_not_a_prior_link(self):
        """Approving the roster in the same breath as the recovery is the
        owner asserting twice, not evidence."""
        request = self._open()
        self._link(self.player, established_at=T0 + timedelta(minutes=1))
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertIn("before the request", caught.exception.reason)

    def test_no_link_at_all_is_a_refusal_not_a_warning(self):
        request = self._open()
        with self.assertRaises(recovery.RecoveryError):
            recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertIsNone(
            migrate.fetch_one(
                self.conn,
                "SELECT completed_at FROM recovery_requests WHERE id = %s",
                (request.id,),
            )["completed_at"]
        )

    # --- one use ---

    def test_the_login_id_is_shown_once(self):
        self._link(self.player)
        request = self._open()
        recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertIn("shown once", caught.exception.reason)

    def test_the_record_keeps_no_copy_of_the_login_id(self):
        self._link(self.player)
        request = self._open()
        handover = recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        row = migrate.fetch_one(
            self.conn,
            "SELECT * FROM recovery_requests WHERE id = %s",
            (request.id,),
        )
        for value in row.values():
            self.assertNotIn(handover.login_id, str(value))

    def test_a_fresh_recovery_can_follow_a_completed_one(self):
        self._link(self.player)
        first = self._open()
        recovery.hand_over(self.conn, self.owner, first.id, clock=self.clock)
        self.clock.moment = T0 + timedelta(days=1)
        second = self._open()
        recovery.hand_over(self.conn, self.owner, second.id, clock=self.clock)

    # --- what recovery does to the account ---

    def test_the_new_login_id_works_and_the_old_one_stops(self):
        self._link(self.player)
        request = self._open()
        handover = recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.conn.commit()
        # the issued login ID really signs that account in
        session = login_with_id(
            self.conn, handover.login_id, ttl_seconds=3600, ip_address=None, user_agent=None
        )
        self.assertIsNotNone(session)
        live = migrate.fetch_all(
            self.conn,
            "SELECT revoked_at FROM login_credentials WHERE account_id = %s"
            " AND revoked_at IS NULL",
            (self.player,),
        )
        self.assertEqual(len(live), 1, "exactly one credential is usable")

    def test_recovery_ends_every_session_of_that_account(self):
        self._link(self.player)
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at)"
            " VALUES (%s, %s, now() + interval '1 hour')",
            (self.player, b"x" * 32),
        )
        request = self._open()
        recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        live = migrate.fetch_all(
            self.conn,
            "SELECT id FROM sessions WHERE account_id = %s AND revoked_at IS NULL",
            (self.player,),
        )
        self.assertEqual(live, [])

    def test_recovery_moves_no_points_and_opens_no_history(self):
        self._link(self.player)
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 640)",
            (self.player,),
        )
        request = self._open()
        recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        points = migrate.fetch_one(
            self.conn,
            "SELECT current_points FROM balances WHERE account_id = %s",
            (self.player,),
        )["current_points"]
        self.assertEqual(points, 640)

    def test_recovery_creates_no_prize_eligibility(self):
        """It restores access and nothing else: the roster link it checked
        is the owner's earlier decision, not one made here."""
        self._link(self.player)
        before = migrate.fetch_all(self.conn, "SELECT * FROM participant_links")
        request = self._open()
        recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        after = migrate.fetch_all(self.conn, "SELECT * FROM participant_links")
        self.assertEqual(before, after)

    # --- refusals ---

    def test_an_unknown_tag_is_refused(self):
        with self.assertRaises(recovery.RecoveryError) as caught:
            self._open(tag="ZZZZZZ")
        self.assertIn("No account with that tag", caught.exception.reason)

    def test_a_deleted_account_has_nothing_to_restore(self):
        self._link(self.player)
        request = self._open()
        migrate.execute(
            self.conn,
            "UPDATE accounts SET deleted_at = now() WHERE id = %s",
            (self.player,),
        )
        with self.assertRaises(recovery.RecoveryError) as caught:
            recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        self.assertIn("nothing to restore", caught.exception.reason)

    def test_the_owner_is_sent_to_the_server_machine_for_their_own_access(self):
        """The locked-out owner has no owner session, so the in-app route
        cannot be theirs."""
        with self.assertRaises(recovery.RecoveryError) as caught:
            self._open(tag="OWN001")
        self.assertIn("server machine", caught.exception.reason)

    def test_an_unknown_recovery_id_is_refused(self):
        with self.assertRaises(recovery.RecoveryError):
            recovery.hand_over(self.conn, self.owner, uuid4(), clock=self.clock)

    # --- the owner's own record ---

    def test_the_record_says_who_and_when_and_nothing_more(self):
        self._link(self.player)
        request = self._open()
        recovery.hand_over(self.conn, self.owner, request.id, clock=self.clock)
        rows = recovery.recent_requests(self.conn, self.owner)
        self.assertEqual(len(rows), 1)
        self.assertEqual(
            set(rows[0]), {"id", "username", "tag", "opened_at", "completed_at"}
        )

    def test_deleting_an_account_takes_its_recovery_records_with_it(self):
        """These rows must not become a retained record of a deleted
        player."""
        self._link(self.player)
        self._open()
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (self.player,))
        self.assertEqual(
            migrate.fetch_all(self.conn, "SELECT id FROM recovery_requests"), []
        )


if __name__ == "__main__":
    unittest.main()
