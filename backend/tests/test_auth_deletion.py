"""Self-service account deletion (issue #47, slice 3)."""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

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
        client = TestClient(create_app())
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
        return res.json()["attempt_id"]


class DeletionRequestTests(DeletionTestCase):
    def test_deletion_requires_a_session(self):
        anon = TestClient(create_app())
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
        fresh = TestClient(create_app())
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


if __name__ == "__main__":
    unittest.main()
