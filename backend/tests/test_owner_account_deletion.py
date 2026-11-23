"""The owner deletes an account that should not exist (issue #271)."""
import os
from unittest import mock

from fastapi.testclient import TestClient

from backend.auth import deletion, deletion_list
from backend.db import migrate
from backend.main import create_app
from backend.tests.browser import BROWSER
from backend.tests.test_auth_deletion import DeletionTestCase

LIST_URL = "/api/ranked/owner/accounts"


class OwnerDeletionTestCase(DeletionTestCase):
    def _owner(self, confirmed=True):
        """An owner, signed in; with the login ID entered again unless told not to."""
        client, login_id, account_id = self._player("the_owner")
        self._exec("UPDATE accounts SET is_owner = true WHERE id = %s", (account_id,))
        if confirmed:
            res = client.post("/api/auth/reauthenticate", json={"login_id": login_id})
            self.assertEqual(res.status_code, 204, res.text)
        return client, account_id

    def _tag(self, account_id):
        return self._one("SELECT tag FROM accounts WHERE id = %s", (account_id,))["tag"]

    def _remove(self, client, account_id, tag):
        return client.post(f"{LIST_URL}/{account_id}/delete", json={"confirm_tag": tag})

    def _finished_quiz(self, client):
        """One Ranked quiz that ended and was scored (the player quit it)."""
        attempt_id = self._start(client)
        res = client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        self.assertEqual(res.status_code, 200, res.text)

    def _completed_quiz(self, account_id):
        """A completed Ranked quiz and a balance: what puts a player on the board."""
        conn = migrate.connect(self.conninfo)
        season = migrate.fetch_one(conn, "SELECT id FROM seasons")["id"]
        migrate.execute(
            conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 40)"
            " ON CONFLICT (account_id) DO UPDATE SET current_points = 40",
            (account_id,),
        )
        assignment = migrate.fetch_one(
            conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, season),
        )["id"]
        migrate.execute(
            conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', now())",
            (account_id, assignment, season),
        )
        conn.commit()
        conn.close()

    def _alive(self, account_id):
        row = self._one("SELECT deleted_at FROM accounts WHERE id = %s", (account_id,))
        return row is not None and row["deleted_at"] is None


class OwnerAccountListTests(OwnerDeletionTestCase):
    def test_the_owner_sees_every_account_and_nothing_of_its_record(self):
        owner, owner_id = self._owner()
        played, _, played_id = self._player("has_played_one")
        _, _, fresh_id = self._player("never_played")
        self._finished_quiz(played)
        self._exec(
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, 'R-1')",
            (played_id,),
        )
        res = owner.get(LIST_URL)
        self.assertEqual(res.status_code, 200, res.text)
        rows = {row["account_id"]: row for row in res.json()["accounts"]}
        self.assertEqual(set(rows), {owner_id, played_id, fresh_id})
        self.assertEqual(
            set(rows[played_id]),
            {"account_id", "username", "tag", "created_at", "is_owner", "approved", "has_played"},
        )
        self.assertTrue(rows[owner_id]["is_owner"])
        self.assertEqual((rows[played_id]["approved"], rows[played_id]["has_played"]), (True, True))
        self.assertEqual((rows[fresh_id]["approved"], rows[fresh_id]["has_played"]), (False, False))

    def test_a_player_is_refused_the_list(self):
        self._owner()
        player, _, _ = self._player("curious_player")
        self.assertEqual(player.get(LIST_URL).status_code, 403)

    def test_the_list_needs_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get(LIST_URL).status_code, 401)

    def test_a_deleted_account_leaves_the_list(self):
        owner, _ = self._owner()
        _, _, gone_id = self._player("soon_gone")
        self.assertEqual(self._remove(owner, gone_id, self._tag(gone_id)).status_code, 202)
        ids = [row["account_id"] for row in owner.get(LIST_URL).json()["accounts"]]
        self.assertNotIn(gone_id, ids)

    def test_the_list_is_capped(self):
        self.assertLessEqual(deletion.MAX_ROWS, 500)
        self.assertGreater(deletion.MAX_ROWS, 0)


class OwnerDeletesAnAccountTests(OwnerDeletionTestCase):
    def test_the_account_is_deleted_and_its_sessions_end(self):
        owner, _ = self._owner()
        player, login_id, account_id = self._player("test_account")
        second = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(second.post("/api/auth/login", json={"login_id": login_id}).status_code, 200)
        tag = self._tag(account_id)
        res = self._remove(owner, account_id, tag)
        self.assertEqual(res.status_code, 202, res.text)
        self.assertEqual(res.json(), {"status": "accepted", "username": "test_account", "tag": tag})
        # both devices are out, and the code opens nothing any more
        self.assertEqual(player.get("/api/auth/me").status_code, 401)
        self.assertEqual(second.get("/api/auth/me").status_code, 401)
        again = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(again.post("/api/auth/login", json={"login_id": login_id}).status_code, 401)
        self.assertFalse(self._alive(account_id))
        # the owner is untouched
        self.assertEqual(owner.get("/api/auth/me").status_code, 200)

    def test_the_tag_may_be_typed_the_way_people_type_it(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("typed_loosely")
        res = self._remove(owner, account_id, f"  #{self._tag(account_id).lower()} ")
        self.assertEqual(res.status_code, 202, res.text)

    def test_a_wrong_tag_changes_nothing(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("kept_account")
        _, _, other_id = self._player("other_account")
        for typed in ("", "ZZZZZZ", self._tag(other_id)):
            with self.subTest(typed=typed):
                self.assertEqual(self._remove(owner, account_id, typed).status_code, 422)
        self.assertTrue(self._alive(account_id))
        self.assertTrue(self._alive(other_id))

    def test_a_player_cannot_delete_somebody_else(self):
        self._owner()
        player, login_id, _ = self._player("not_the_owner")
        player.post("/api/auth/reauthenticate", json={"login_id": login_id})
        _, _, victim_id = self._player("the_victim")
        res = self._remove(player, victim_id, self._tag(victim_id))
        self.assertEqual(res.status_code, 403)
        self.assertTrue(self._alive(victim_id))

    def test_the_rule_itself_refuses_a_player_whatever_the_route_does(self):
        _, _, player_id = self._player("direct_caller")
        _, _, victim_id = self._player("direct_victim")
        conn = migrate.connect(self.conninfo)
        self.addCleanup(conn.close)
        with self.assertRaises(deletion.NotOwnerError):
            deletion.delete_by_owner(conn, player_id, victim_id, self._tag(victim_id))
        with self.assertRaises(deletion.NotOwnerError):
            deletion.accounts_for_owner(conn, player_id)
        self.assertTrue(self._alive(victim_id))

    def test_the_owner_account_is_never_deleted(self):
        owner, owner_id = self._owner()
        res = self._remove(owner, owner_id, self._tag(owner_id))
        self.assertEqual(res.status_code, 409)
        self.assertTrue(self._alive(owner_id))

    def test_the_login_id_must_have_been_entered_again(self):
        owner, _ = self._owner(confirmed=False)
        _, _, account_id = self._player("needs_reauth")
        res = self._remove(owner, account_id, self._tag(account_id))
        self.assertEqual(res.status_code, 428)
        self.assertTrue(self._alive(account_id))

    def test_an_account_already_gone_or_never_there_is_not_found(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("gone_twice")
        tag = self._tag(account_id)
        self.assertEqual(self._remove(owner, account_id, tag).status_code, 202)
        self.assertEqual(self._remove(owner, account_id, tag).status_code, 404)
        self.assertEqual(
            self._remove(owner, "00000000-0000-0000-0000-000000000000", tag).status_code, 404
        )
        self.assertEqual(self._remove(owner, "not-an-id", tag).status_code, 404)

    def test_an_attempt_in_progress_is_removed_without_a_score(self):
        owner, _ = self._owner()
        player, _, account_id = self._player("mid_quiz")
        self._start(player)
        self.assertEqual(self._remove(owner, account_id, self._tag(account_id)).status_code, 202)
        row = self._one("SELECT COUNT(*) AS n FROM attempts WHERE account_id = %s", (account_id,))
        self.assertEqual(row["n"], 0)
        self.assertEqual(self._one("SELECT COUNT(*) AS n FROM settlements")["n"], 0)

    def test_an_approved_sorter_stays_out_of_the_season(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("approved_one")
        self._exec(
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, 'R-77')",
            (account_id,),
        )
        self.assertEqual(self._remove(owner, account_id, self._tag(account_id)).status_code, 202)
        marker = self._one("SELECT ineligible FROM season_markers WHERE roster_reference = 'R-77'")
        self.assertTrue(marker["ineligible"])

    def test_the_account_leaves_the_leaderboard(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("on_the_board")
        self._completed_quiz(account_id)
        names = [row["username"] for row in owner.get("/api/ranked/leaderboard").json()["rows"]]
        self.assertIn("on_the_board", names)
        self.assertEqual(self._remove(owner, account_id, self._tag(account_id)).status_code, 202)
        names = [row["username"] for row in owner.get("/api/ranked/leaderboard").json()["rows"]]
        self.assertNotIn("on_the_board", names)


class OwnerDeletionNoteTests(OwnerDeletionTestCase):
    """The off-database note comes first, as for the player's own deletion (#13)."""

    CONTAINER = "https://stsortdel.blob.core.windows.net/deletions"

    def setUp(self):
        super().setUp()
        from backend.db import entra_token

        entra_token.reset_cache()
        entra_token.set_token_fetcher(lambda: {"access_token": "tok", "expires_on": "9999999999"})
        self.addCleanup(entra_token.set_token_fetcher, None)
        self.addCleanup(entra_token.reset_cache)
        self.addCleanup(deletion_list.set_transport, None)
        patcher = mock.patch.dict(os.environ, {deletion_list.ENV_VAR: self.CONTAINER})
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_the_note_is_written_before_the_database_confirms(self):
        owner, _ = self._owner()
        _, _, account_id = self._player("noted_by_owner")
        seen = []

        def blob(method, url, headers, body):
            seen.append((method, url, self._alive(account_id)))
            return 201

        deletion_list.set_transport(blob)
        self.assertEqual(self._remove(owner, account_id, self._tag(account_id)).status_code, 202)
        self.assertEqual(seen, [("PUT", f"{self.CONTAINER}/{account_id}", True)])

    def test_a_failed_note_refuses_the_deletion_and_changes_nothing(self):
        owner, _ = self._owner()
        player, _, account_id = self._player("note_failed")
        deletion_list.set_transport(lambda *a: 503)
        res = self._remove(owner, account_id, self._tag(account_id))
        self.assertEqual(res.status_code, 503, res.text)
        self.assertTrue(self._alive(account_id))
        self.assertEqual(player.get("/api/auth/me").status_code, 200)

    def test_a_refusal_writes_no_note(self):
        owner, owner_id = self._owner()
        _, _, account_id = self._player("no_note")
        calls = []
        deletion_list.set_transport(lambda *a: calls.append(a) or 201)
        self.assertEqual(self._remove(owner, account_id, "ZZZZZZ").status_code, 422)
        self.assertEqual(self._remove(owner, owner_id, self._tag(owner_id)).status_code, 409)
        self.assertEqual(calls, [])

    def test_a_database_failure_after_the_note_removes_the_note(self):
        _, owner_id = self._owner()
        _, _, account_id = self._player("half_done")
        tag = self._tag(account_id)
        calls = []
        deletion_list.set_transport(lambda m, u, h, b: calls.append((m, u)) or 201)
        conn = migrate.connect(self.conninfo)
        self.addCleanup(conn.close)
        real_execute = migrate.execute

        def failing_execute(connection, sql, params=()):
            if sql.startswith("UPDATE accounts SET deleted_at"):
                raise RuntimeError("database went away")
            return real_execute(connection, sql, params)

        with mock.patch.object(deletion.migrate, "execute", failing_execute):
            with self.assertRaises(RuntimeError):
                deletion.delete_by_owner(conn, owner_id, account_id, tag)
        blob = f"{self.CONTAINER}/{account_id}"
        self.assertEqual(calls, [("PUT", blob), ("DELETE", blob)])
        self.assertTrue(self._alive(account_id))
