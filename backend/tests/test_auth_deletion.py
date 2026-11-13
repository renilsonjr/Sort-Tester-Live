"""Self-service account deletion (issue #47, slice 3)."""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

from backend.db import migrate, settings
from backend.main import create_app

DELETE_URL = "/api/auth/account/delete"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class DeletionTestCase(unittest.TestCase):
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
        conn = migrate.connect(self.conninfo)
        migrate.execute(conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'Pre')")
        conn.commit()
        conn.close()

    def _player(self, username):
        """Register and sign in; return (client, login_id, account_id)."""
        client = TestClient(create_app(), headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login_id = reg.json()["login_id"]
        self.assertEqual(
            client.post("/api/auth/login", json={"login_id": login_id}).status_code, 200
        )
        return client, login_id, reg.json()["account_id"]

    def _one(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, sql, params)
        finally:
            conn.close()

    def _exec(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        migrate.execute(conn, sql, params)
        conn.commit()
        conn.close()

    def _delete(self, client, login_id, acknowledge=True):
        return client.post(DELETE_URL, json={"login_id": login_id, "acknowledge": acknowledge})

    def _start(self, client):
        res = client.post("/api/ranked/attempts")
        self.assertEqual(res.status_code, 201, res.text)
        # act as the original page: keep the capability for later requests
        client.headers["X-Attempt-Capability"] = res.json()["capability"]
        return res.json()["attempt_id"]


class DeletionRequestTests(DeletionTestCase):
    def test_deletion_requires_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        res = anon.post(DELETE_URL, json={"login_id": "AAAA-AAAA-AAAA-AAAA", "acknowledge": True})
        self.assertEqual(res.status_code, 401)

    def test_deletion_requires_the_acknowledgment(self):
        client, login_id, account_id = self._player("careful_player")
        self.assertEqual(self._delete(client, login_id, acknowledge=False).status_code, 422)
        no_ack = client.post(DELETE_URL, json={"login_id": login_id})
        self.assertEqual(no_ack.status_code, 422)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)

    def test_a_wrong_login_id_changes_nothing(self):
        client, login_id, account_id = self._player("unsure_player")
        other_client, other_login_id, _ = self._player("other_player")
        res = self._delete(client, other_login_id)  # someone else's real login ID
        self.assertEqual(res.status_code, 403)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)
        row = self._one("SELECT deleted_at FROM accounts WHERE id = %s", (account_id,))
        self.assertIsNone(row["deleted_at"])

    def test_wrong_login_ids_count_as_failed_logins(self):
        client, login_id, _ = self._player("guessing_player")
        with mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"}):
            headers = {"X-Forwarded-For": "198.51.100.77"}
            codes = [
                client.post(DELETE_URL, json={"login_id": "WRNG-WRNG-WRNG-WRNG",
                                              "acknowledge": True},
                            headers=headers).status_code
                for _ in range(11)
            ]
        self.assertEqual(codes[:10], [403] * 10)
        self.assertEqual(codes[10], 429)

    def test_the_owner_cannot_be_deleted(self):
        client, login_id, account_id = self._player("the_owner")
        self._exec("UPDATE accounts SET is_owner = true WHERE id = %s", (account_id,))
        res = self._delete(client, login_id)
        self.assertEqual(res.status_code, 409)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)

    def test_accepted_deletion_locks_the_account_out(self):
        client, login_id, account_id = self._player("leaving_player")
        res = self._delete(client, login_id)
        self.assertEqual(res.status_code, 202, res.text)
        self.assertEqual(res.json(), {"status": "accepted"})
        self.assertEqual(client.get("/api/auth/me").status_code, 401)
        fresh = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(
            fresh.post("/api/auth/login", json={"login_id": login_id}).status_code, 401
        )
        row = self._one(
            "SELECT (SELECT deleted_at FROM accounts WHERE id = %(a)s) AS deleted_at,"
            " (SELECT COUNT(*) FROM sessions WHERE account_id = %(a)s"
            "   AND revoked_at IS NULL) AS live_sessions,"
            " (SELECT COUNT(*) FROM login_credentials WHERE account_id = %(a)s"
            "   AND revoked_at IS NULL) AS live_credentials",
            {"a": account_id},
        )
        if row["deleted_at"] is not None:  # the purge may already have run
            self.assertEqual((row["live_sessions"], row["live_credentials"]), (0, 0))

    def test_the_running_quiz_ends_and_other_players_are_untouched(self):
        client, login_id, account_id = self._player("quitting_for_good")
        other, _, other_id = self._player("staying_player")
        mine = self._start(client)
        theirs = self._start(other)
        self.assertEqual(self._delete(client, login_id).status_code, 202)
        gone = self._one("SELECT COUNT(*) AS n FROM attempts WHERE id = %s", (mine,))
        self.assertEqual(gone["n"], 0)
        kept = self._one("SELECT state FROM attempts WHERE id = %s", (theirs,))
        self.assertEqual(kept["state"], "active")

    def test_a_season_marker_is_kept_for_a_linked_player(self):
        client, login_id, account_id = self._player("linked_player")
        self._exec(
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, %s)",
            (account_id, "Night shift, badge 4417"),
        )
        season = self._one("SELECT id FROM seasons LIMIT 1")["id"]
        self.assertEqual(self._delete(client, login_id).status_code, 202)
        marker = self._one(
            "SELECT season, ineligible FROM season_markers WHERE roster_reference = %s",
            ("Night shift, badge 4417",),
        )
        self.assertEqual((marker["season"], marker["ineligible"]), (str(season), True))

    def test_no_marker_without_a_participant_link(self):
        client, login_id, _ = self._player("unlinked_player")
        self.assertEqual(self._delete(client, login_id).status_code, 202)
        self.assertEqual(self._one("SELECT COUNT(*) AS n FROM season_markers")["n"], 0)


class PurgeTests(DeletionTestCase):
    def _played_and_scored(self, client):
        attempt_id = self._start(client)
        quit_res = client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        self.assertEqual(quit_res.status_code, 200, quit_res.text)
        return attempt_id

    def _purge(self):
        from backend.auth import deletion

        conn = migrate.connect(self.conninfo)
        try:
            return deletion.purge_deleted_accounts(conn)
        finally:
            conn.close()

    def _traces(self, account_id, attempt_id):
        return self._one(
            "SELECT"
            " (SELECT COUNT(*) FROM accounts WHERE id = %(a)s) AS accounts,"
            " (SELECT COUNT(*) FROM login_credentials WHERE account_id = %(a)s) AS credentials,"
            " (SELECT COUNT(*) FROM sessions WHERE account_id = %(a)s) AS sessions,"
            " (SELECT COUNT(*) FROM participant_links WHERE account_id = %(a)s) AS links,"
            " (SELECT COUNT(*) FROM balances WHERE account_id = %(a)s) AS balances,"
            " (SELECT COUNT(*) FROM balance_history WHERE account_id = %(a)s) AS history,"
            " (SELECT COUNT(*) FROM attempts WHERE account_id = %(a)s) AS attempts,"
            " (SELECT COUNT(*) FROM assignments WHERE account_id = %(a)s) AS assignments,"
            " (SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = %(t)s) AS answers,"
            " (SELECT COUNT(*) FROM settlements WHERE attempt_id = %(t)s) AS settlements,"
            " (SELECT COUNT(*) FROM attempt_connection_events WHERE attempt_id = %(t)s) AS events,"
            " (SELECT COUNT(*) FROM connection_flags WHERE attempt_id = %(t)s) AS flags",
            {"a": account_id, "t": attempt_id},
        )

    def test_the_purge_leaves_nothing_of_the_player_but_the_marker(self):
        client, login_id, account_id = self._player("vanishing_player")
        attempt_id = self._played_and_scored(client)
        self._exec(
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, %s)",
            (account_id, "Day shift, badge 1203"),
        )
        self._exec(
            "INSERT INTO attempt_connection_events (attempt_id, kind, occurred_at)"
            " VALUES (%s, 'loss', now())",
            (attempt_id,),
        )
        self._exec(
            "INSERT INTO connection_flags (attempt_id, first_loss_at, last_loss_at, flagged_at)"
            " VALUES (%s, now(), now(), now())",
            (attempt_id,),
        )
        before = self._traces(account_id, attempt_id)
        self.assertEqual(before["settlements"], 1)  # there really was data to remove

        self.assertEqual(self._delete(client, login_id).status_code, 202)
        self.assertEqual(self._purge(), 1)

        self.assertEqual(set(self._traces(account_id, attempt_id).values()), {0})
        marker = self._one(
            "SELECT COUNT(*) AS n FROM season_markers WHERE roster_reference = %s",
            ("Day shift, badge 1203",),
        )
        self.assertEqual(marker["n"], 1)

    def test_other_players_and_shared_questions_are_untouched(self):
        client, login_id, account_id = self._player("leaving_for_good")
        other, _, other_id = self._player("loyal_player")
        self._played_and_scored(client)
        theirs = self._played_and_scored(other)
        versions = self._one("SELECT COUNT(*) AS n FROM question_versions")["n"]

        self._delete(client, login_id)
        self._purge()

        self.assertEqual(self._one("SELECT COUNT(*) AS n FROM question_versions")["n"], versions)
        kept = self._traces(other_id, theirs)
        self.assertEqual(
            (kept["accounts"], kept["balances"], kept["history"], kept["attempts"],
             kept["settlements"], kept["answers"]),
            (1, 1, 1, 1, 1, 1),
        )
        self.assertEqual(other.get("/api/auth/me").status_code, 200)

    def test_the_purge_only_touches_accounts_pending_deletion(self):
        self._player("ordinary_player")
        self.assertEqual(self._purge(), 0)
        self.assertEqual(self._one("SELECT COUNT(*) AS n FROM accounts")["n"], 1)

    def test_any_request_runs_the_purge(self):
        client, login_id, account_id = self._player("swept_player")
        self.assertEqual(self._delete(client, login_id).status_code, 202)
        passer_by, _, _ = self._player("passer_by")
        passer_by.get("/api/ranked/entry")
        gone = self._one("SELECT COUNT(*) AS n FROM accounts WHERE id = %s", (account_id,))
        self.assertEqual(gone["n"], 0)


if __name__ == "__main__":
    unittest.main()
