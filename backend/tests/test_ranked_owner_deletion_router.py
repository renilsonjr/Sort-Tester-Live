"""The owner's delete-an-account routes over HTTP (issue #271).

Two steps, so the owner reads back who they are about to remove before it
happens: a look-up by tag, then the deletion. Both are owner-only and both
demand the owner's own Quiz Code re-entered on this device, so a borrowed
signed-in phone is not enough.
"""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}
LOOK = "/api/ranked/owner/deletions/lookup"
DELETE = "/api/ranked/owner/deletions"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerDeletionRouterTests(unittest.TestCase):
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
        self.app = create_app()
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _player(self, username):
        client = TestClient(self.app, headers=BROWSER)
        body = client.post("/api/auth/register", json={"username": username}).json()
        client.post("/api/auth/login", json={"login_id": body["login_id"]})
        tag = migrate.fetch_one(
            self.conn, "SELECT tag FROM accounts WHERE id = %s", (body["account_id"],)
        )["tag"]
        return client, body["account_id"], body["login_id"], tag

    def _owner(self):
        client, account_id, login_id, tag = self._player("the_owner")
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = TRUE WHERE id = %s", (account_id,)
        )
        self.conn.commit()
        client.post("/api/auth/reauthenticate", json={"login_id": login_id})
        return client, account_id, tag

    def _deleted_at(self, account_id):
        return migrate.fetch_one(
            self.conn, "SELECT deleted_at FROM accounts WHERE id = %s", (account_id,)
        )["deleted_at"]

    def test_the_owner_looks_the_account_up_then_deletes_it(self):
        owner, _, _ = self._owner()
        player, player_id, _, tag = self._player("leaving_sorter")

        look = owner.post(LOOK, json={"tag": tag})
        self.assertEqual(look.status_code, 200, look.text)
        self.assertEqual(look.json()["username"], "leaving_sorter")
        self.assertEqual(look.json()["tag"], tag)
        self.assertEqual(look.json()["finished_attempts"], 0)
        self.assertIs(look.json()["approved_for_prizes"], False)
        self.assertIsNone(self._deleted_at(player_id), "looking changed something")

        gone = owner.post(DELETE, json={"tag": tag, "acknowledge": True})
        self.assertEqual(gone.status_code, 200, gone.text)
        self.assertEqual(gone.json(), {"deleted": True, "tag": tag})
        # the account is locked out at once, on its own device too
        self.assertEqual(player.get("/api/auth/me").status_code, 401)

    def test_a_lower_case_tag_with_a_hash_is_accepted(self):
        owner, _, _ = self._owner()
        _, _, _, tag = self._player("casual_typist")
        look = owner.post(LOOK, json={"tag": f" #{tag.lower()} "})
        self.assertEqual(look.status_code, 200, look.text)
        self.assertEqual(look.json()["tag"], tag)

    def test_it_refuses_without_the_acknowledgement(self):
        owner, _, _ = self._owner()
        _, player_id, _, tag = self._player("still_here")
        refused = owner.post(DELETE, json={"tag": tag})
        self.assertEqual(refused.status_code, 422)
        self.assertIsNone(self._deleted_at(player_id))

    def test_it_refuses_the_owner_account(self):
        owner, owner_id, owner_tag = self._owner()
        refused = owner.post(DELETE, json={"tag": owner_tag, "acknowledge": True})
        self.assertEqual(refused.status_code, 422)
        self.assertIsNone(self._deleted_at(owner_id))

    def test_an_unknown_tag_says_so_without_deleting_anything(self):
        owner, _, _ = self._owner()
        _, player_id, _, _ = self._player("bystander")
        missing = owner.post(LOOK, json={"tag": "ZZZZZZ"})
        self.assertEqual(missing.status_code, 422)
        self.assertIsNone(self._deleted_at(player_id))

    def test_a_player_cannot_use_either_route(self):
        self._owner()
        player, _, _, _ = self._player("ordinary")
        _, victim_id, _, victim_tag = self._player("victim")
        for route, body in ((LOOK, {"tag": victim_tag}),
                            (DELETE, {"tag": victim_tag, "acknowledge": True})):
            self.assertEqual(player.post(route, json=body).status_code, 403, route)
        self.assertIsNone(self._deleted_at(victim_id))

    def test_a_stranger_cannot_use_either_route(self):
        self._owner()
        _, victim_id, _, victim_tag = self._player("victim")
        anon = TestClient(self.app, headers=BROWSER)
        for route, body in ((LOOK, {"tag": victim_tag}),
                            (DELETE, {"tag": victim_tag, "acknowledge": True})):
            self.assertEqual(anon.post(route, json=body).status_code, 401, route)
        self.assertIsNone(self._deleted_at(victim_id))

    def test_the_owner_must_re_enter_their_quiz_code(self):
        # signed in as the owner, but without the recent re-entry
        owner_client, owner_id, _, _ = self._player("fresh_owner")
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = TRUE WHERE id = %s", (owner_id,)
        )
        self.conn.commit()
        _, victim_id, _, victim_tag = self._player("victim")
        for route, body in ((LOOK, {"tag": victim_tag}),
                            (DELETE, {"tag": victim_tag, "acknowledge": True})):
            self.assertEqual(owner_client.post(route, json=body).status_code, 428, route)
        self.assertIsNone(self._deleted_at(victim_id))

    def test_deleting_the_same_account_twice_is_refused(self):
        owner, _, _ = self._owner()
        _, _, _, tag = self._player("twice_over")
        self.assertEqual(owner.post(DELETE, json={"tag": tag, "acknowledge": True}).status_code, 200)
        again = owner.post(DELETE, json={"tag": tag, "acknowledge": True})
        self.assertEqual(again.status_code, 422)


if __name__ == "__main__":
    unittest.main()
