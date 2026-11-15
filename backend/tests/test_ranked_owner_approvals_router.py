"""The owner's approval screen over HTTP (issue #11, slice 2).

The rule is tested in test_auth_eligibility.py. What matters here is who
the endpoints answer, what a refusal says, and that nothing about another
account leaks through the one lookup the screen needs.
"""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerApprovalsRouterTests(unittest.TestCase):
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
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', 'Peak Season', now() - interval '1 day',"
            " now() + interval '7 days')",
        )
        self.conn.commit()
        self.owner = TestClient(create_app(), headers=BROWSER)
        owner_login = self._sign_in(self.owner, "the_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'",
        )
        self.conn.commit()
        # The owner's actions need the login ID re-entered on this session
        # (#11 box 5); these tests are about what the actions do, so the
        # owner confirms once up front. test_auth_reauth.py covers the gate.
        self.assertEqual(
            self.owner.post(
                "/api/auth/reauthenticate", json={"login_id": owner_login}
            ).status_code,
            204,
        )
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
            self.conn,
            "SELECT tag FROM accounts WHERE username_lower = %s",
            (username,),
        )["tag"]

    def _account_id(self, username):
        return migrate.fetch_one(
            self.conn,
            "SELECT id FROM accounts WHERE username_lower = %s",
            (username,),
        )["id"]

    def _approve(self, tag=None, reference="Primary Sort - Twilight - 4471", client=None):
        return (client or self.owner).post(
            "/api/ranked/owner/approvals",
            json={"tag": tag or self.player_tag, "roster_reference": reference},
        )

    # --- who may call ---

    def test_a_player_is_refused_every_call(self):
        self.assertEqual(self.player.get("/api/ranked/owner/approvals").status_code, 403)
        self.assertEqual(self._approve(client=self.player).status_code, 403)
        gone = self.player.delete(
            f"/api/ranked/owner/approvals/{self._account_id('dock_owl')}"
        )
        self.assertEqual(gone.status_code, 403)

    def test_a_signed_out_visitor_is_refused(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get("/api/ranked/owner/approvals").status_code, 401)
        self.assertEqual(
            anon.post(
                "/api/ranked/owner/approvals",
                json={"tag": self.player_tag, "roster_reference": "x"},
            ).status_code,
            401,
        )

    def test_a_refused_player_learns_nothing_about_the_approvals(self):
        self._approve()
        refusal = self.player.get("/api/ranked/owner/approvals")
        self.assertEqual(refusal.status_code, 403)
        self.assertNotIn("dock_owl", refusal.text)
        self.assertNotIn("4471", refusal.text)

    # --- approving ---

    def test_the_owner_approves_by_tag(self):
        created = self._approve()
        self.assertEqual(created.status_code, 201, created.text)
        self.assertEqual(created.json()["username"], "dock_owl")
        listed = self.owner.get("/api/ranked/owner/approvals").json()
        self.assertEqual([row["username"] for row in listed["approvals"]], ["dock_owl"])
        self.assertTrue(listed["approvals_open"])

    def test_a_tag_typed_with_a_hash_or_in_lower_case_still_works(self):
        created = self._approve(tag=f"  #{self.player_tag.lower()} ")
        self.assertEqual(created.status_code, 201, created.text)

    def test_an_unknown_tag_is_refused_in_words(self):
        refusal = self._approve(tag="ZZZZZZ")
        self.assertEqual(refusal.status_code, 422)
        self.assertEqual(refusal.json()["detail"], "No account with that tag.")

    def test_the_owner_cannot_approve_themselves(self):
        refusal = self._approve(tag=self._tag("the_owner"))
        self.assertEqual(refusal.status_code, 422)
        self.assertIn("own account", refusal.json()["detail"])

    def test_the_same_sorter_twice_is_refused_in_words(self):
        self._approve()
        second = TestClient(create_app(), headers=BROWSER)
        self._sign_in(second, "dock_owl_spare")
        refusal = self._approve(tag=self._tag("dock_owl_spare"))
        self.assertEqual(refusal.status_code, 422)
        self.assertIn("already has an approved account", refusal.json()["detail"])

    def test_a_blank_roster_reference_is_refused(self):
        refusal = self._approve(reference="   ")
        self.assertEqual(refusal.status_code, 422)

    # --- withdrawing ---

    def test_the_owner_withdraws_an_approval(self):
        self._approve()
        gone = self.owner.delete(
            f"/api/ranked/owner/approvals/{self._account_id('dock_owl')}"
        )
        self.assertEqual(gone.status_code, 204, gone.text)
        listed = self.owner.get("/api/ranked/owner/approvals").json()
        self.assertEqual(listed["approvals"], [])

    def test_withdrawing_an_account_that_is_not_approved_is_not_found(self):
        gone = self.owner.delete(
            f"/api/ranked/owner/approvals/{self._account_id('dock_owl')}"
        )
        self.assertEqual(gone.status_code, 404)

    def test_a_malformed_account_id_is_not_found_rather_than_a_crash(self):
        self.assertEqual(
            self.owner.delete("/api/ranked/owner/approvals/not-a-uuid").status_code, 404
        )

    def test_withdrawing_leaves_the_player_signed_in_and_playing(self):
        self._approve()
        self.owner.delete(f"/api/ranked/owner/approvals/{self._account_id('dock_owl')}")
        self.assertEqual(self.player.get("/api/auth/me").status_code, 200)

    # --- what the screen is not ---

    def test_an_approval_row_carries_no_points_or_history(self):
        self._approve()
        row = self.owner.get("/api/ranked/owner/approvals").json()["approvals"][0]
        self.assertEqual(
            set(row),
            {"account_id", "username", "tag", "roster_reference", "established_at"},
        )

    def test_there_is_no_player_listing_endpoint_here(self):
        """The owner may approve a tag they were given; they cannot browse
        the players, because no such power was granted."""
        for path in (
            "/api/ranked/owner/players",
            "/api/ranked/owner/accounts",
            "/api/ranked/owner/history",
        ):
            with self.subTest(path=path):
                self.assertEqual(self.owner.get(path).status_code, 404)


if __name__ == "__main__":
    unittest.main()
