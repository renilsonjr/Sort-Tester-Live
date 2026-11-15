"""Access recovery over HTTP (issue #11, box 2).

The rule is tested in test_auth_recovery.py. What matters here is who the
endpoints answer, and that the login ID crosses the wire exactly once.
"""
import unittest
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryRouterTests(unittest.TestCase):
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
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.owner = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.owner, "the_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'",
        )
        self.conn.commit()
        self.player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.player, "dock_owl")
        self.player_tag = self._tag("dock_owl")

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login = client.post("/api/auth/login", json={"login_id": reg.json()["login_id"]})
        self.assertEqual(login.status_code, 200, login.text)
        return reg.json()["login_id"]

    def _tag(self, username):
        return migrate.fetch_one(
            self.conn, "SELECT tag FROM accounts WHERE username_lower = %s", (username,)
        )["tag"]

    def _link(self, username, *, days_ago=30):
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = %s", (username,)
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference, established_at)"
            " VALUES (%s, %s, now() - %s * interval '1 day')",
            (account_id, f"roster-{username}", days_ago),
        )
        self.conn.commit()

    def _open(self, tag=None, client=None):
        return (client or self.owner).post(
            "/api/ranked/owner/recoveries", json={"tag": tag or self.player_tag}
        )

    # --- who may call ---

    def test_a_player_is_refused_every_call(self):
        self.assertEqual(self.player.get("/api/ranked/owner/recoveries").status_code, 403)
        self.assertEqual(self._open(client=self.player).status_code, 403)

    def test_a_signed_out_visitor_is_refused(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get("/api/ranked/owner/recoveries").status_code, 401)
        self.assertEqual(
            anon.post("/api/ranked/owner/recoveries", json={"tag": "AAAAAA"}).status_code,
            401,
        )

    # --- the two steps ---

    def test_opening_a_recovery_issues_nothing(self):
        self._link("dock_owl")
        opened = self._open()
        self.assertEqual(opened.status_code, 201, opened.text)
        self.assertNotIn("login_id", opened.text)

    def test_the_handover_returns_the_login_id_once(self):
        self._link("dock_owl")
        request_id = self._open().json()["id"]
        first = self.owner.post(f"/api/ranked/owner/recoveries/{request_id}/handover")
        self.assertEqual(first.status_code, 200, first.text)
        login_id = first.json()["login_id"]
        self.assertEqual(len(login_id.replace("-", "")), 16)

        second = self.owner.post(f"/api/ranked/owner/recoveries/{request_id}/handover")
        self.assertEqual(second.status_code, 422)
        self.assertNotIn(login_id, second.text)

    def test_the_issued_login_id_signs_that_account_in(self):
        self._link("dock_owl")
        request_id = self._open().json()["id"]
        login_id = self.owner.post(
            f"/api/ranked/owner/recoveries/{request_id}/handover"
        ).json()["login_id"]
        fresh = TestClient(create_app(), headers=BROWSER)
        signed_in = fresh.post("/api/auth/login", json={"login_id": login_id})
        self.assertEqual(signed_in.status_code, 200, signed_in.text)
        self.assertEqual(signed_in.json()["username"], "dock_owl")

    def test_the_old_session_stops_working(self):
        self._link("dock_owl")
        self.assertEqual(self.player.get("/api/auth/me").status_code, 200)
        request_id = self._open().json()["id"]
        self.owner.post(f"/api/ranked/owner/recoveries/{request_id}/handover")
        self.assertEqual(self.player.get("/api/auth/me").status_code, 401)

    # --- the rule, carried over HTTP ---

    def test_without_a_prior_link_the_handover_is_refused_in_words(self):
        request_id = self._open().json()["id"]
        refusal = self.owner.post(f"/api/ranked/owner/recoveries/{request_id}/handover")
        self.assertEqual(refusal.status_code, 422)
        self.assertIn("before the request", refusal.json()["detail"])
        self.assertNotIn("login_id", refusal.text)

    def test_an_unknown_tag_is_refused(self):
        refusal = self._open(tag="ZZZZZZ")
        self.assertEqual(refusal.status_code, 422)
        self.assertIn("No account with that tag", refusal.json()["detail"])

    def test_a_malformed_recovery_id_is_not_found(self):
        self.assertEqual(
            self.owner.post("/api/ranked/owner/recoveries/not-a-uuid/handover").status_code,
            404,
        )

    # --- the record ---

    def test_the_listing_says_who_and_when_and_keeps_no_login_id(self):
        self._link("dock_owl")
        request_id = self._open().json()["id"]
        login_id = self.owner.post(
            f"/api/ranked/owner/recoveries/{request_id}/handover"
        ).json()["login_id"]
        listed = self.owner.get("/api/ranked/owner/recoveries")
        self.assertEqual(listed.status_code, 200)
        row = listed.json()["recoveries"][0]
        self.assertEqual(
            set(row), {"id", "username", "tag", "opened_at", "completed_at"}
        )
        self.assertNotIn(login_id, listed.text)

    def test_the_withdrawn_route_is_gone_but_this_one_works(self):
        """The old reset-on-say-so endpoint and its replacement, side by
        side, so a regression that revives the first one is loud."""
        self._link("dock_owl")
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = 'dock_owl'"
        )["id"]
        old = self.owner.post(
            "/api/auth/admin/regenerate", json={"account_id": str(account_id)}
        )
        self.assertEqual(old.status_code, 410)
        self.assertEqual(self._open().status_code, 201)


if __name__ == "__main__":
    unittest.main()
