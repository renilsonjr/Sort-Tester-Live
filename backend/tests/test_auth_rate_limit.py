import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

from backend.db import migrate, settings
from backend.main import create_app


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AuthRateLimitTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        app = create_app()
        self.client = TestClient(app, headers=BROWSER)

    def test_login_rate_limit_blocks_after_threshold(self):
        # The test client has one connection address shared by every test, so
        # this test acts as if a trusted proxy reported a distinct address;
        # its failures then cannot block other tests' logins.
        self._trust_one_proxy()
        for i in range(12):
            status_code = self._login("rl_threshold", "wrong-00", "192.168.1.50")
            if i < 10:
                self.assertEqual(status_code, 401)
            else:
                self.assertEqual(status_code, 429)

    def test_a_forged_first_entry_cannot_evade_the_limit(self):
        # issue #78: the client invents a new first entry on every request; the
        # ingress appends the same real address each time.
        self._trust_one_proxy()
        codes = [
            self._login("rl_forged", "wrong-00", f"10.99.0.{n}, 192.168.7.7")
            for n in range(12)
        ]
        self.assertEqual(codes, [401] * 10 + [429] * 2)

    def test_one_address_being_blocked_does_not_block_another(self):
        self._trust_one_proxy()
        for _ in range(11):
            self._login("rl_two_addresses", "wrong-00", "192.168.8.8")
        self.assertEqual(self._login("rl_two_addresses", "wrong-00", "192.168.8.8"), 429)
        self.assertEqual(self._login("rl_two_addresses", "wrong-00", "192.168.9.9"), 401)

    def _login(self, username, login_id, forwarded):
        return self.client.post(
            "/api/auth/login",
            json={"username": username, "login_id": login_id},
            headers={"X-Forwarded-For": forwarded},
        ).status_code

    def _trust_one_proxy(self):
        trusted = mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"})
        trusted.start()
        self.addCleanup(trusted.stop)

    def _register(self, username):
        return self.client.post(
            "/api/auth/register", json={"username": username}
        ).json()["login_id"]

    def test_guessing_one_account_does_not_lock_out_another(self):
        # audit H-2: keyed by address alone, ten guesses at one account
        # locked every other account reachable from that address -- behind
        # one ingress, that is everybody.
        self._trust_one_proxy()
        victim = self._register("h2_victim")
        for _ in range(11):
            self._login("h2_target", "wrong-00", "192.168.20.20")

        self.assertEqual(self._login("h2_target", "wrong-00", "192.168.20.20"), 429)
        self.assertEqual(self._login("h2_victim", victim, "192.168.20.20"), 200)

    def test_a_different_code_each_guess_is_still_limited(self):
        # word codes (2026-11-25): the limit is per account, so trying a new
        # code every time does not earn a fresh allowance.
        self._trust_one_proxy()
        self._register("h2_many_codes")
        codes = [
            self._login("h2_many_codes", f"guess-{n:02d}", "192.168.24.24")
            for n in range(12)
        ]
        self.assertEqual(codes, [401] * 10 + [429] * 2)

    def test_a_success_elsewhere_does_not_clear_the_guessing_counter(self):
        # the attacker signs in to their own account between guesses; that
        # must not hand them a fresh ten tries at somebody else's account.
        self._trust_one_proxy()
        attacker = self._register("h2_attacker")
        for _ in range(10):
            self._login("h2_someone", "wrong-00", "192.168.21.21")
            self.assertEqual(self._login("h2_attacker", attacker, "192.168.21.21"), 200)

        self.assertEqual(self._login("h2_someone", "wrong-00", "192.168.21.21"), 429)

    def test_the_owner_of_an_account_is_not_locked_out_by_their_own_success(self):
        # the other side of the same rule: once they get in, the failed
        # tries they made on the way stop counting against them.
        self._trust_one_proxy()
        login_id = self._register("h2_owner")
        for _ in range(9):
            self._login("h2_owner", "wrong-00", "192.168.22.22")
        self.assertEqual(self._login("h2_owner", login_id, "192.168.22.22"), 200)

        for _ in range(9):
            self.assertEqual(self._login("h2_owner", login_id, "192.168.22.22"), 200)

    def test_a_malformed_login_id_is_refused_without_a_server_error(self):
        # the same refusal as any other wrong code, never a 500
        self._trust_one_proxy()
        self.assertEqual(self._login("rl_malformed", "not a login id!!", "192.168.23.23"), 401)
        self.assertEqual(self._login("rl_malformed", "WRNG-WRNG-WRNG-WRN!", "192.168.23.23"), 401)
        self.assertEqual(self._login("bad name!", "banana-48", "192.168.23.23"), 401)

    def test_thirty_failures_from_anywhere_pause_the_account(self):
        # owner decision 2026-11-25: 30 failed checks against one account in a
        # day, whatever the address, pause that account for an hour.
        self._trust_one_proxy()
        login_id = self._register("h2_spread")
        codes = [
            self._login("h2_spread", "wrong-00", f"192.168.{30 + n // 5}.{n % 5 + 1}")
            for n in range(30)
        ]
        self.assertEqual(codes, [401] * 30)
        # a fresh address, and even the right code, waits out the pause
        self.assertEqual(self._login("h2_spread", login_id, "192.168.99.99"), 429)
        # other accounts are not affected
        other = self._register("h2_spread_other")
        self.assertEqual(self._login("h2_spread_other", other, "192.168.99.99"), 200)


if __name__ == "__main__":
    unittest.main()
