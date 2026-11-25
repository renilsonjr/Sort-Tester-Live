"""Signing out an account's other devices (issue #270).

The investigation on #270 found that several devices are allowed on purpose
(five at once), that the server already stops any advantage from that, and
that a player who feared someone else had their Quiz Code had no remedy of
their own. This is that remedy: end every other session, keep this one.
"""
import unittest

from fastapi.testclient import TestClient

from backend.auth.sessions import MAX_ACTIVE_SESSIONS
from backend.db import migrate, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}
ROUTE = "/api/auth/sessions/revoke-others"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RevokeOtherSessionsTests(unittest.TestCase):
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

    def _account(self, username="two_device_player"):
        client = TestClient(self.app, headers=BROWSER)
        body = client.post("/api/auth/register", json={"username": username}).json()
        if not hasattr(self, "_names"):
            self._names = {}
        self._names[body["login_id"]] = username
        return body["account_id"], body["login_id"]

    def _device(self, login_id):
        client = TestClient(self.app, headers=BROWSER)
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"username": self._names[login_id], "login_id": login_id},
            ).status_code,
            200,
        )
        return client

    def _confirmed(self, login_id):
        """A device that has re-entered its Quiz Code, as the screen does."""
        client = self._device(login_id)
        self.assertEqual(
            client.post("/api/auth/reauthenticate", json={"login_id": login_id}).status_code,
            204,
        )
        return client

    def _live(self, account_id):
        return migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM sessions"
            " WHERE account_id = %s AND revoked_at IS NULL",
            (account_id,),
        )["n"]

    def test_the_other_devices_end_and_this_one_carries_on(self):
        account_id, login_id = self._account()
        others = [self._device(login_id) for _ in range(3)]
        mine = self._confirmed(login_id)
        self.assertEqual(self._live(account_id), 4)

        answer = mine.post(ROUTE)
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json(), {"ended": 3})

        self.assertEqual(self._live(account_id), 1)
        self.assertEqual(mine.get("/api/auth/me").status_code, 200)
        for other in others:
            self.assertEqual(other.get("/api/auth/me").status_code, 401)

    def test_it_needs_the_quiz_code_re_entered_first(self):
        _, login_id = self._account()
        plain = self._device(login_id)
        refused = plain.post(ROUTE)
        self.assertEqual(refused.status_code, 428)
        # nothing changed: the other device still works
        self.assertEqual(plain.get("/api/auth/me").status_code, 200)

    def test_a_stranger_is_refused(self):
        _, login_id = self._account()
        self._device(login_id)
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.post(ROUTE).status_code, 401)

    def test_it_touches_no_other_account(self):
        _, mine = self._account("device_owner")
        other_id, theirs = self._account("device_stranger")
        self._device(theirs)
        self._confirmed(mine).post(ROUTE)
        self.assertEqual(self._live(other_id), 1)

    def test_with_no_other_device_it_ends_nothing_and_says_so(self):
        account_id, login_id = self._account()
        answer = self._confirmed(login_id).post(ROUTE)
        self.assertEqual(answer.json(), {"ended": 0})
        self.assertEqual(self._live(account_id), 1)

    def test_running_it_twice_is_harmless(self):
        account_id, login_id = self._account()
        self._device(login_id)
        mine = self._confirmed(login_id)
        self.assertEqual(mine.post(ROUTE).json(), {"ended": 1})
        self.assertEqual(mine.post(ROUTE).json(), {"ended": 0})
        self.assertEqual(self._live(account_id), 1)

    def test_it_can_clear_a_full_set_of_devices(self):
        account_id, login_id = self._account()
        for _ in range(MAX_ACTIVE_SESSIONS):
            self._device(login_id)
        mine = self._confirmed(login_id)
        # the cap already pushed the oldest out; this one is the newest
        self.assertEqual(self._live(account_id), MAX_ACTIVE_SESSIONS)
        self.assertEqual(mine.post(ROUTE).json(), {"ended": MAX_ACTIVE_SESSIONS - 1})
        self.assertEqual(self._live(account_id), 1)


if __name__ == "__main__":
    unittest.main()
