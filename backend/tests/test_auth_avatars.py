"""Choosing a profile icon (issue #272).

The account stores a key, never the emoji and never anything the player
typed, so the server can only ever hand back one of a fixed set. An account
that never chose has none, and the screens fall back to what they show today.
"""
import unittest

from fastapi.testclient import TestClient

from backend.auth import avatars
from backend.db import migrate, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}
ROUTE = "/api/auth/avatar"


class AvatarListTests(unittest.TestCase):
    def test_there_are_fifteen_keys_and_no_repeats(self):
        self.assertEqual(len(avatars.KEYS), 15)
        self.assertEqual(len(set(avatars.KEYS)), 15)

    def test_a_key_is_plain_and_short(self):
        for key in avatars.KEYS:
            self.assertRegex(key, r"^[a-z][a-z_]{1,14}$", key)

    def test_only_a_listed_key_is_allowed(self):
        self.assertTrue(avatars.is_allowed(avatars.KEYS[0]))
        for refused in ("", None, "dragon", "FOX", "fox ", "🦊", "fox;drop"):
            self.assertFalse(avatars.is_allowed(refused), repr(refused))


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AvatarRouteTests(unittest.TestCase):
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

    def _player(self, username="icon_picker"):
        client = TestClient(self.app, headers=BROWSER)
        body = client.post("/api/auth/register", json={"username": username}).json()
        client.post("/api/auth/login", json={"login_id": body["login_id"]})
        return client, body["account_id"]

    def _stored(self, account_id):
        return migrate.fetch_one(
            self.conn, "SELECT avatar FROM accounts WHERE id = %s", (account_id,)
        )["avatar"]

    def test_a_new_account_has_chosen_nothing(self):
        client, account_id = self._player()
        self.assertIsNone(self._stored(account_id))
        self.assertIsNone(client.get("/api/auth/me").json()["avatar"])

    def test_choosing_one_stores_its_key_and_reports_it_back(self):
        client, account_id = self._player()
        chosen = avatars.KEYS[3]
        answer = client.put(ROUTE, json={"avatar": chosen})
        self.assertEqual(answer.status_code, 204, answer.text)
        self.assertEqual(self._stored(account_id), chosen)
        self.assertEqual(client.get("/api/auth/me").json()["avatar"], chosen)

    def test_changing_it_replaces_the_old_one(self):
        client, account_id = self._player()
        client.put(ROUTE, json={"avatar": avatars.KEYS[0]})
        client.put(ROUTE, json={"avatar": avatars.KEYS[1]})
        self.assertEqual(self._stored(account_id), avatars.KEYS[1])

    def test_clearing_it_is_allowed(self):
        client, account_id = self._player()
        client.put(ROUTE, json={"avatar": avatars.KEYS[0]})
        self.assertEqual(client.put(ROUTE, json={"avatar": None}).status_code, 204)
        self.assertIsNone(self._stored(account_id))

    def test_a_key_that_is_not_on_the_list_is_refused(self):
        client, account_id = self._player()
        for refused in ("dragon", "FOX", "🦊", "'; DROP TABLE accounts; --", "x" * 40):
            answer = client.put(ROUTE, json={"avatar": refused})
            self.assertEqual(answer.status_code, 422, f"{refused!r}: {answer.text}")
        self.assertIsNone(self._stored(account_id))

    def test_a_stranger_cannot_set_one(self):
        anon = TestClient(self.app, headers=BROWSER)
        self.assertEqual(anon.put(ROUTE, json={"avatar": avatars.KEYS[0]}).status_code, 401)

    def test_one_account_cannot_set_another_s(self):
        # there is no account id in the route: it always acts on the session's
        # own account, so this is the whole of that guarantee
        first, first_id = self._player("first_player")
        second, second_id = self._player("second_player")
        first.put(ROUTE, json={"avatar": avatars.KEYS[0]})
        second.put(ROUTE, json={"avatar": avatars.KEYS[1]})
        self.assertEqual(self._stored(first_id), avatars.KEYS[0])
        self.assertEqual(self._stored(second_id), avatars.KEYS[1])


if __name__ == "__main__":
    unittest.main()
