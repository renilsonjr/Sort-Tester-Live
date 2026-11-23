"""The owner deleting an account that should not exist (issue #271).

Self-service deletion (#47) needs the player's own Quiz Code, which the owner
does not have. This is the same deletion, authorised differently: the owner's
own Quiz Code, re-entered, and the account named by its tag — the only handle
the owner has, because #11 deliberately gave them no player list.
"""
import unittest
from datetime import datetime, timezone
from unittest import mock

from backend.auth import deletion
from backend.db import migrate, settings


class FixedClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerDeletionTests(unittest.TestCase):
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
        # after the rows this test creates: accounts carry a check that a
        # deletion cannot predate the account's own creation
        self.clock = FixedClock(datetime(2030, 1, 1, 12, 0, tzinfo=timezone.utc))
        self.noted = []
        patch = mock.patch.object(
            deletion.deletion_list,
            "record",
            side_effect=lambda account_id, moment: self.noted.append(account_id),
        )
        patch.start()
        self.addCleanup(patch.stop)
        forget = mock.patch.object(deletion.deletion_list, "forget")
        self.forget = forget.start()
        self.addCleanup(forget.stop)

    def _account(self, username, tag, *, owner=False):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (username, username.lower(), tag, owner),
        )
        self.conn.commit()
        return row["id"]

    def _row(self, account_id):
        return migrate.fetch_one(
            self.conn, "SELECT deleted_at FROM accounts WHERE id = %s", (account_id,)
        )

    def test_the_owner_deletes_an_account_without_its_quiz_code(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        target_id = self._account("leaver", "LEAVE1")
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 300)",
            (target_id,),
        )
        self.conn.commit()

        deletion.owner_delete(self.conn, owner_id, target_id, clock=self.clock)

        self.assertEqual(self._row(target_id)["deleted_at"], self.clock.now())
        # the note outside the database was written, so a restore re-applies it
        self.assertEqual(self.noted, [target_id])
        self.forget.assert_not_called()

    def test_it_revokes_the_quiz_code_and_every_session(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        target_id = self._account("leaver", "LEAVE1")
        migrate.execute(
            self.conn,
            "INSERT INTO login_credentials (account_id, lookup_key, verifier)"
            " VALUES (%s, %s, %s)",
            (target_id, "k" * 32, "verifier"),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at)"
            " VALUES (%s, %s, %s)",
            (target_id, b"t" * 32, datetime(2030, 1, 1, tzinfo=timezone.utc)),
        )
        self.conn.commit()

        deletion.owner_delete(self.conn, owner_id, target_id, clock=self.clock)

        for table in ("login_credentials", "sessions"):
            left = migrate.fetch_one(
                self.conn,
                f"SELECT COUNT(*) AS n FROM {table}"
                " WHERE account_id = %s AND revoked_at IS NULL",
                (target_id,),
            )["n"]
            self.assertEqual(left, 0, table)

    def test_the_owner_account_is_refused(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        with self.assertRaises(deletion.OwnerAccountError):
            deletion.owner_delete(self.conn, owner_id, owner_id, clock=self.clock)
        self.assertIsNone(self._row(owner_id)["deleted_at"])
        self.assertEqual(self.noted, [])

    def test_a_player_cannot_use_it_on_somebody_else(self):
        plain_id = self._account("player", "PLAIN1")
        target_id = self._account("victim", "VICTM1")
        with self.assertRaises(deletion.NotOwnerError):
            deletion.owner_delete(self.conn, plain_id, target_id, clock=self.clock)
        self.assertIsNone(self._row(target_id)["deleted_at"])
        self.assertEqual(self.noted, [])

    def test_an_account_already_deleted_is_refused(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        target_id = self._account("leaver", "LEAVE1")
        deletion.owner_delete(self.conn, owner_id, target_id, clock=self.clock)
        self.noted.clear()
        with self.assertRaises(deletion.NoSuchAccountError):
            deletion.owner_delete(self.conn, owner_id, target_id, clock=self.clock)
        self.assertEqual(self.noted, [])

    def test_nothing_changes_when_the_note_cannot_be_written(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        target_id = self._account("leaver", "LEAVE1")
        with mock.patch.object(
            deletion.deletion_list,
            "record",
            side_effect=deletion.deletion_list.DeletionListUnavailable("no store"),
        ):
            with self.assertRaises(deletion.deletion_list.DeletionListUnavailable):
                deletion.owner_delete(self.conn, owner_id, target_id, clock=self.clock)
        self.assertIsNone(self._row(target_id)["deleted_at"])

    def test_it_says_what_the_owner_is_about_to_remove(self):
        owner_id = self._account("boss", "OWNER1", owner=True)
        target_id = self._account("Busy_Player", "BUSY01")
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 450)",
            (target_id,),
        )
        self.conn.commit()

        about = deletion.describe_for_owner(self.conn, owner_id, target_id)
        self.assertEqual(about["username"], "Busy_Player")
        self.assertEqual(about["tag"], "BUSY01")
        self.assertEqual(about["finished_attempts"], 0)
        self.assertFalse(about["approved_for_prizes"])
        # nothing was changed by looking
        self.assertIsNone(self._row(target_id)["deleted_at"])

    def test_only_the_owner_may_look(self):
        plain_id = self._account("player", "PLAIN1")
        target_id = self._account("victim", "VICTM1")
        with self.assertRaises(deletion.NotOwnerError):
            deletion.describe_for_owner(self.conn, plain_id, target_id)


if __name__ == "__main__":
    unittest.main()
