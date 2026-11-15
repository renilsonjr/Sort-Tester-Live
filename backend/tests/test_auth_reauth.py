"""Recent login-ID reauthentication for the owner's actions (issue #11,
box 5). Named after the rules in the settled design rather than the
functions."""
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
class ReauthTests(unittest.TestCase):
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
        self.owner_login = self._sign_in(self.owner, "the_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'",
        )
        self.conn.commit()
        self.player = TestClient(create_app(), headers=BROWSER)
        self.player_login = self._sign_in(self.player, "dock_owl")
        self.player_tag = migrate.fetch_one(
            self.conn, "SELECT tag FROM accounts WHERE username_lower = 'dock_owl'"
        )["tag"]

    # --- helpers ---

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login_id = reg.json()["login_id"]
        self.assertEqual(
            client.post("/api/auth/login", json={"login_id": login_id}).status_code, 200
        )
        return login_id

    def _reauth(self, client, login_id):
        return client.post("/api/auth/reauthenticate", json={"login_id": login_id})

    def _approve(self, client=None):
        return (client or self.owner).post(
            "/api/ranked/owner/approvals",
            json={"tag": self.player_tag, "roster_reference": "twilight-4471"},
        )

    def _age_reauth(self, minutes):
        migrate.execute(
            self.conn,
            "UPDATE sessions SET reauthenticated_at = reauthenticated_at"
            " - %s * interval '1 minute' WHERE reauthenticated_at IS NOT NULL",
            (minutes,),
        )
        self.conn.commit()

    # --- the rule ---

    def test_an_owner_action_needs_a_fresh_login_id(self):
        refused = self._approve()
        self.assertEqual(refused.status_code, 428)
        self.assertIn("Re-enter your login ID", refused.json()["detail"])
        self.assertEqual(
            migrate.fetch_all(self.conn, "SELECT * FROM participant_links"), []
        )

    def test_after_reauthenticating_the_action_goes_through(self):
        self.assertEqual(self._reauth(self.owner, self.owner_login).status_code, 204)
        self.assertEqual(self._approve().status_code, 201)

    def test_the_proof_lasts_five_minutes(self):
        self._reauth(self.owner, self.owner_login)
        self._age_reauth(4)
        self.assertEqual(self._approve().status_code, 201)

    def test_after_five_minutes_it_must_be_entered_again(self):
        self._reauth(self.owner, self.owner_login)
        self._age_reauth(6)
        self.assertEqual(self._approve().status_code, 428)

    def test_one_reauthentication_covers_a_run_of_actions(self):
        """Asking before every click would teach the owner to type the
        login ID without reading."""
        self._reauth(self.owner, self.owner_login)
        self.assertEqual(self._approve().status_code, 201)
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = 'dock_owl'"
        )["id"]
        self.assertEqual(
            self.owner.delete(f"/api/ranked/owner/approvals/{account_id}").status_code, 204
        )

    def test_the_proof_belongs_to_one_session_only(self):
        """A cookie on another device starts with nothing."""
        self._reauth(self.owner, self.owner_login)
        laptop = TestClient(create_app(), headers=BROWSER)
        laptop.post("/api/auth/login", json={"login_id": self.owner_login})
        self.assertEqual(self._approve(client=laptop).status_code, 428)

    # --- what the login ID check refuses ---

    def test_a_wrong_login_id_is_refused_and_records_nothing(self):
        refused = self._reauth(self.owner, "AAAA-BBBB-CCCC-DDDD")
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(self._approve().status_code, 428)

    def test_another_accounts_login_id_does_not_count(self):
        """The check is against this session's own account, so it cannot
        be used to test whether somebody else's login ID is valid."""
        refused = self._reauth(self.owner, self.player_login)
        self.assertEqual(refused.status_code, 403)
        self.assertEqual(self._approve().status_code, 428)

    def test_the_refusal_says_the_same_whatever_was_wrong(self):
        malformed = self._reauth(self.owner, "not a login id")
        someone_elses = self._reauth(self.owner, self.player_login)
        self.assertEqual(malformed.json(), someone_elses.json())

    def test_reauthenticating_needs_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(self._reauth(anon, self.owner_login).status_code, 401)

    def test_the_login_id_is_never_stored(self):
        self._reauth(self.owner, self.owner_login)
        for table in ("sessions", "login_credentials", "recovery_requests"):
            for row in migrate.fetch_all(self.conn, f"SELECT * FROM {table}"):
                for value in row.values():
                    self.assertNotIn(self.owner_login, str(value), table)

    # --- which actions it guards ---

    def test_a_player_is_refused_before_the_reauth_step(self):
        """A player is told they are not allowed, not that they should
        re-enter a login ID: the second would hint at a door."""
        self._reauth(self.player, self.player_login)
        self.assertEqual(self._approve(client=self.player).status_code, 403)

    def test_recovery_handover_needs_it_too(self):
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = 'dock_owl'"
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference, established_at)"
            " VALUES (%s, 'twilight-4471', now() - interval '30 days')",
            (account_id,),
        )
        self.conn.commit()
        opened = self.owner.post(
            "/api/ranked/owner/recoveries", json={"tag": self.player_tag}
        )
        self.assertEqual(opened.status_code, 201, opened.text)
        handover = f"/api/ranked/owner/recoveries/{opened.json()['id']}/handover"
        self.assertEqual(self.owner.post(handover).status_code, 428)
        self._reauth(self.owner, self.owner_login)
        self.assertEqual(self.owner.post(handover).status_code, 200)

    def test_reading_needs_no_reauthentication(self):
        """Only actions that change something are guarded; looking at the
        approvals or the recovery record is not one of them."""
        self.assertEqual(self.owner.get("/api/ranked/owner/approvals").status_code, 200)
        self.assertEqual(self.owner.get("/api/ranked/owner/recoveries").status_code, 200)


if __name__ == "__main__":
    unittest.main()
