"""Username + word code sign-in, and changing one's own code (2026-11-25).

Owner decisions: sign-in asks for username + Quiz Code; new codes are one
English word and two digits; codes issued before keep working with the
username; a signed-in player may change their own code behind re-entry.
"""
import re
import unittest

from fastapi.testclient import TestClient

from backend.auth.credentials import hash_login_id
from backend.db import migrate, settings
from backend.main import create_app

BROWSER = {"User-Agent": "test/1.0", "Origin": "http://testserver"}
LOGIN = "/api/auth/login"
CHANGE = "/api/auth/login-id/change"
WORD_CODE = re.compile(r"^[a-z]{3,8}-[0-9]{2}$")


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class WordCodeLoginTests(unittest.TestCase):
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

    def _client(self):
        return TestClient(self.app, headers=BROWSER)

    def _register(self, username):
        body = self._client().post("/api/auth/register", json={"username": username}).json()
        return body["account_id"], body["login_id"]

    def _login(self, username, login_id, client=None):
        return (client or self._client()).post(
            LOGIN, json={"username": username, "login_id": login_id}
        )

    # --- signing in ---

    def test_a_new_account_gets_a_word_code_and_signs_in_with_its_username(self):
        _, login_id = self._register("word_player")
        self.assertRegex(login_id, WORD_CODE)
        res = self._login("word_player", login_id)
        self.assertEqual(res.status_code, 200, res.text)
        self.assertEqual(res.json()["username"], "word_player")

    def test_username_case_and_code_case_do_not_matter(self):
        _, login_id = self._register("Case_Player")
        typed = login_id.upper().replace("-", " ")
        self.assertEqual(self._login("case_player", typed).status_code, 200)

    def test_the_code_alone_no_longer_signs_in(self):
        _, login_id = self._register("code_alone")
        res = self._client().post(LOGIN, json={"login_id": login_id})
        self.assertEqual(res.status_code, 422)

    def test_a_code_from_before_signs_in_with_the_username(self):
        account_id, _ = self._register("old_code_player")
        old = "ABCD-EFGH-JKMN-PRST"
        migrate.execute(
            self.conn,
            "UPDATE login_credentials SET verifier = %s WHERE account_id = %s"
            " AND revoked_at IS NULL",
            (hash_login_id(old), account_id),
        )
        self.conn.commit()
        self.assertEqual(self._login("old_code_player", old).status_code, 200)
        self.assertEqual(self._login("old_code_player", "abcd efgh jkmn prst").status_code, 200)

    def test_two_accounts_may_share_a_code_and_each_opens_only_its_own(self):
        a_id, _ = self._register("share_a")
        b_id, _ = self._register("share_b")
        shared = "banana-48"
        for account_id in (a_id, b_id):
            migrate.execute(
                self.conn,
                "UPDATE login_credentials SET verifier = %s WHERE account_id = %s"
                " AND revoked_at IS NULL",
                (hash_login_id(shared), account_id),
            )
        self.conn.commit()
        self.assertEqual(self._login("share_a", shared).json()["account_id"], a_id)
        self.assertEqual(self._login("share_b", shared).json()["account_id"], b_id)

    def test_every_wrong_pair_gets_the_same_refusal(self):
        _, login_id = self._register("refusal_player")
        other_id, other_code = self._register("refusal_other")
        cases = [
            ("refusal_player", "wrong-00"),  # wrong code
            ("nobody_at_all", login_id),  # unknown username
            ("refusal_player", other_code),  # someone else's code
            ("refusal_player", "not a code!!"),  # malformed code
        ]
        bodies = set()
        for username, code in cases:
            res = self._login(username, code)
            self.assertEqual(res.status_code, 401, (username, code))
            bodies.add(res.text)
        self.assertEqual(len(bodies), 1)

    def test_no_lookup_value_is_derived_from_a_new_code(self):
        account_id, login_id = self._register("no_lookup")
        import hashlib

        normalized = login_id.replace("-", "")
        derived = hashlib.sha256(normalized.encode("ascii")).digest()[:16].hex()
        row = migrate.fetch_one(
            self.conn,
            "SELECT lookup_key FROM login_credentials WHERE account_id = %s",
            (account_id,),
        )
        self.assertNotEqual(row["lookup_key"], derived)

    def test_a_deleted_account_cannot_sign_in(self):
        account_id, login_id = self._register("gone_player")
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (account_id,)
        )
        self.conn.commit()
        self.assertEqual(self._login("gone_player", login_id).status_code, 401)

    # --- changing one's own code ---

    def _signed_in(self, username):
        account_id, login_id = self._register(username)
        client = self._client()
        self.assertEqual(self._login(username, login_id, client).status_code, 200)
        return client, account_id, login_id

    def _reauth(self, client, login_id):
        res = client.post("/api/auth/reauthenticate", json={"login_id": login_id})
        self.assertEqual(res.status_code, 204, res.text)

    def test_changing_needs_the_current_code_re_entered(self):
        client, _, _ = self._signed_in("change_gate")
        self.assertEqual(client.post(CHANGE).status_code, 428)

    def test_changing_needs_a_session(self):
        self.assertEqual(self._client().post(CHANGE).status_code, 401)

    def test_after_a_change_the_new_code_works_and_the_old_one_does_not(self):
        client, _, old = self._signed_in("change_player")
        self._reauth(client, old)
        res = client.post(CHANGE)
        self.assertEqual(res.status_code, 200, res.text)
        new = res.json()["login_id"]
        self.assertRegex(new, WORD_CODE)
        self.assertEqual(self._login("change_player", new).status_code, 200)
        self.assertEqual(self._login("change_player", old).status_code, 401)

    def test_this_device_stays_signed_in_and_the_others_end(self):
        client, account_id, old = self._signed_in("change_devices")
        other = self._client()
        self.assertEqual(self._login("change_devices", old, other).status_code, 200)
        self._reauth(client, old)
        self.assertEqual(client.post(CHANGE).status_code, 200)
        self.assertEqual(client.get("/api/auth/me").status_code, 200)
        self.assertEqual(other.get("/api/auth/me").status_code, 401)
        live = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM sessions WHERE account_id = %s AND revoked_at IS NULL",
            (account_id,),
        )["n"]
        self.assertEqual(live, 1)

    def test_the_new_code_is_never_stored(self):
        client, account_id, old = self._signed_in("change_secret")
        self._reauth(client, old)
        new = client.post(CHANGE).json()["login_id"]
        rows = migrate.fetch_all(
            self.conn,
            "SELECT lookup_key, verifier FROM login_credentials WHERE account_id = %s",
            (account_id,),
        )
        for row in rows:
            self.assertNotIn(new, row["lookup_key"] + row["verifier"])
            self.assertNotIn(new.replace("-", ""), row["lookup_key"] + row["verifier"])


if __name__ == "__main__":
    unittest.main()
