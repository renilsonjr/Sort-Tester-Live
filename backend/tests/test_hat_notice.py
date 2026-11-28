"""The approved player's hat notice shows once (issue #517)."""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, pool, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class HatNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        pool.close_pool()
        self.addCleanup(pool.close_pool)
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.app = create_app()
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _player(self, username):
        client = TestClient(self.app, headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": username}).json()
        login = client.post(
            "/api/auth/login", json={"username": username, "login_id": reg["login_id"]}
        )
        self.assertEqual(login.status_code, 200, login.text)
        return client, reg["account_id"]

    def _approve(self, account_id, reference):
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, %s)",
            (account_id, reference),
        )
        self.conn.commit()

    def _withdraw(self, account_id):
        migrate.execute(
            self.conn, "DELETE FROM participant_links WHERE account_id = %s", (account_id,)
        )
        self.conn.commit()

    def _shows(self, client):
        res = client.get("/api/auth/hat-notice")
        self.assertEqual(res.status_code, 200, res.text)
        return res.json()["show"]

    def test_a_player_not_approved_never_sees_it(self):
        client, _ = self._player("maria_sorter")
        self.assertFalse(self._shows(client))

    def test_an_approved_player_sees_it_until_closing_it(self):
        client, account = self._player("maria_sorter")
        self._approve(account, "roster-1")
        self.assertTrue(self._shows(client))
        self.assertTrue(self._shows(client), "opening Home again does not close it")
        self.assertEqual(client.post("/api/auth/hat-notice/seen").status_code, 204)
        self.assertFalse(self._shows(client))

    def test_closing_it_holds_on_another_device(self):
        client = TestClient(self.app, headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": "maria_sorter"}).json()
        self._approve(reg["account_id"], "roster-1")
        sign_in = {"username": "maria_sorter", "login_id": reg["login_id"]}
        phone = TestClient(self.app, headers=BROWSER)
        laptop = TestClient(self.app, headers=BROWSER)
        phone.post("/api/auth/login", json=sign_in)
        laptop.post("/api/auth/login", json=sign_in)
        self.assertTrue(self._shows(laptop))
        phone.post("/api/auth/hat-notice/seen")
        # the "seen" is on the server, not in one browser
        self.assertFalse(self._shows(laptop))

    def test_a_withdrawal_hides_it_and_a_new_approval_shows_it_again(self):
        client, account = self._player("maria_sorter")
        self._approve(account, "roster-1")
        self._withdraw(account)
        self.assertFalse(self._shows(client))
        self._approve(account, "roster-1")
        client.post("/api/auth/hat-notice/seen")
        self._withdraw(account)
        self._approve(account, "roster-1")
        self.assertTrue(self._shows(client))

    def test_one_player_closing_it_leaves_the_other_alone(self):
        maria, a = self._player("maria_sorter")
        lucia, b = self._player("lucia_sorter")
        self._approve(a, "roster-1")
        self._approve(b, "roster-2")
        maria.post("/api/auth/hat-notice/seen")
        self.assertTrue(self._shows(lucia))

    def test_signed_out_gets_401(self):
        guest = TestClient(self.app, headers=BROWSER)
        self.assertEqual(guest.get("/api/auth/hat-notice").status_code, 401)
        self.assertEqual(guest.post("/api/auth/hat-notice/seen").status_code, 401)


if __name__ == "__main__":
    unittest.main()
