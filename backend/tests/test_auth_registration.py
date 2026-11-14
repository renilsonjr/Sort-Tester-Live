"""Registration hardening (issue #47, slice 2)."""
import os
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

from backend.auth.rate_limit import RegistrationLimiter, _client_key
from backend.db import migrate, settings
from backend.main import create_app


class _Request:
    """The two parts of a request that _client_key reads."""

    def __init__(self, host, forwarded=None):
        self.headers = {} if forwarded is None else {"x-forwarded-for": forwarded}
        self.client = type("Client", (), {"host": host})()


class ClientAddressTests(unittest.TestCase):
    """Which address a request is counted under (issue #78).

    Each proxy APPENDS the address it received the request from, so only the
    entries written by our own proxies, counted from the right, can be
    believed. Everything to their left is whatever the client chose to send.
    """

    def key(self, host, forwarded=None, trust=None):
        environment = {} if trust is None else {"SORT_TEST_TRUST_PROXY": trust}
        with mock.patch.dict(os.environ, environment, clear=True):
            return _client_key(_Request(host, forwarded=forwarded))

    def test_forwarded_header_is_ignored_without_a_trusted_proxy(self):
        self.assertEqual(self.key("10.0.0.5", "203.0.113.9"), "10.0.0.5")

    def test_one_trusted_proxy_uses_the_last_entry(self):
        self.assertEqual(self.key("10.0.0.5", "203.0.113.9", trust="1"), "203.0.113.9")

    def test_a_forged_entry_in_front_is_not_believed(self):
        # The client sent "1.2.3.4"; the ingress appended the real address.
        for forged in ("1.2.3.4", "1.2.3.4, 5.6.7.8", "evil, 1.2.3.4"):
            with self.subTest(forged=forged):
                self.assertEqual(
                    self.key("10.0.0.5", f"{forged}, 203.0.113.9", trust="1"), "203.0.113.9"
                )

    def test_changing_the_forged_part_never_changes_the_key(self):
        keys = {self.key("10.0.0.5", f"9.9.9.{n}, 203.0.113.9", trust="1") for n in range(20)}
        self.assertEqual(keys, {"203.0.113.9"})

    def test_two_trusted_proxies_use_the_second_entry_from_the_right(self):
        self.assertEqual(
            self.key("10.0.0.5", "1.2.3.4, 203.0.113.9, 10.9.9.9", trust="2"), "203.0.113.9"
        )

    def test_fewer_entries_than_trusted_proxies_falls_back_to_the_connection(self):
        self.assertEqual(self.key("10.0.0.5", "203.0.113.9", trust="2"), "10.0.0.5")

    def test_no_header_uses_the_connection_address(self):
        self.assertEqual(self.key("10.0.0.5", trust="1"), "10.0.0.5")

    def test_an_entry_that_is_not_an_address_falls_back_to_the_connection(self):
        for junk in ("unknown", "", "not-an-ip", "203.0.113.9 extra", "<script>"):
            with self.subTest(junk=junk):
                self.assertEqual(self.key("10.0.0.5", f"1.2.3.4, {junk}", trust="1"), "10.0.0.5")

    def test_a_port_on_the_entry_is_dropped(self):
        self.assertEqual(self.key("10.0.0.5", "203.0.113.9:51234", trust="1"), "203.0.113.9")
        self.assertEqual(self.key("10.0.0.5", "[2001:db8::1]:443", trust="1"), "2001:db8::1")

    def test_ipv6_addresses_are_normalised_to_one_spelling(self):
        self.assertEqual(
            self.key("10.0.0.5", "2001:0DB8:0000:0000:0000:0000:0000:0001", trust="1"),
            "2001:db8::1",
        )

    def test_a_setting_that_is_not_a_small_whole_number_trusts_nothing(self):
        for value in ("yes", "true", "-1", "0", "1.5", "99", ""):
            with self.subTest(value=value):
                self.assertEqual(self.key("10.0.0.5", "203.0.113.9", trust=value), "10.0.0.5")


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class UsernameAnswerTests(unittest.TestCase):
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
        self.client = TestClient(create_app(), headers=BROWSER)

    def _accounts(self):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, "SELECT COUNT(*) AS n FROM accounts")["n"]
        finally:
            conn.close()

    def _register(self, username):
        return self.client.post("/api/auth/register", json={"username": username})

    def test_a_taken_username_in_any_case_is_a_conflict(self):
        self.assertEqual(self._register("Sorter_One").status_code, 200)
        taken = self._register("sorter_one")
        self.assertEqual(taken.status_code, 409)
        self.assertEqual(taken.json()["detail"], "Username taken")
        self.assertEqual(self._accounts(), 1)

    def test_names_breaking_the_rule_are_refused(self):
        for bad in ("ab", "x" * 25, "has space", "josé", ""):
            with self.subTest(name=bad):
                self.assertEqual(self._register(bad).status_code, 422)
        self.assertEqual(self._accounts(), 0)

    def test_a_valid_name_still_registers(self):
        res = self._register("Night_Sorter_42")
        self.assertEqual(res.status_code, 200, res.text)
        self.assertIn("login_id", res.json())


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class RegistrationLimiterTests(unittest.TestCase):
    def setUp(self):
        self.clock = FakeClock()
        self.limiter = RegistrationLimiter(
            per_client=3, per_client_window=3600, total=5, total_window=86400,
            clock=self.clock,
        )

    def _sign_up(self, key):
        allowed = self.limiter.is_allowed(key)
        if allowed:
            self.limiter.record(key)
        return allowed

    def test_the_per_address_cap(self):
        self.assertEqual([self._sign_up("a") for _ in range(4)], [True, True, True, False])
        self.assertTrue(self._sign_up("b"))  # another address is unaffected

    def test_the_hour_slides(self):
        for _ in range(3):
            self._sign_up("a")
        self.clock.now = 3599
        self.assertFalse(self.limiter.is_allowed("a"))
        self.clock.now = 3600  # the first sign-up is now an hour old
        self.assertTrue(self.limiter.is_allowed("a"))

    def test_the_daily_total_across_addresses(self):
        for key in ("a", "b", "c", "d", "e"):
            self.assertTrue(self._sign_up(key))
        self.assertFalse(self.limiter.is_allowed("f"))

    def test_the_day_slides(self):
        for key in ("a", "b", "c", "d", "e"):
            self._sign_up(key)
        self.clock.now = 86400
        self.assertTrue(self.limiter.is_allowed("f"))

    def test_checking_alone_counts_nothing(self):
        for _ in range(10):
            self.assertTrue(self.limiter.is_allowed("a"))


class DefaultLimitTests(unittest.TestCase):
    def test_the_owners_limits(self):
        limiter = create_app().state.registration_limiter
        self.assertEqual(
            (limiter.per_client, limiter.per_client_window, limiter.total, limiter.total_window),
            (30, 3600, 200, 86400),
        )


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RegistrationLimitHttpTests(unittest.TestCase):
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
        app = create_app()
        # small caps keep the test quick; the owner's 30/200 are checked above
        app.state.registration_limiter = RegistrationLimiter(per_client=3, total=5)
        self.client = TestClient(app, headers=BROWSER)
        self._n = 0

    def _register(self, address=None, username=None):
        self._n += 1
        headers = {} if address is None else {"X-Forwarded-For": address}
        return self.client.post(
            "/api/auth/register",
            json={"username": username or f"limit_user_{self._n}"},
            headers=headers,
        )

    def _accounts(self):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, "SELECT COUNT(*) AS n FROM accounts")["n"]
        finally:
            conn.close()

    def test_sign_ups_past_the_cap_are_refused_with_nothing_created(self):
        codes = [self._register().status_code for _ in range(4)]
        self.assertEqual(codes, [200, 200, 200, 429])
        self.assertEqual(self._accounts(), 3)

    def test_refused_sign_ups_do_not_count(self):
        self.assertEqual(self._register(username="taken_name").status_code, 200)
        for _ in range(5):
            self.assertEqual(self._register(username="taken_name").status_code, 409)
            self.assertEqual(self._register(username="x").status_code, 422)
        self.assertEqual(self._register().status_code, 200)
        self.assertEqual(self._register().status_code, 200)
        self.assertEqual(self._register().status_code, 429)

    def test_a_made_up_address_cannot_dodge_the_cap(self):
        for n in range(3):
            self.assertEqual(self._register(address=f"198.51.100.{n}").status_code, 200)
        self.assertEqual(self._register(address="198.51.100.99").status_code, 429)

    def test_behind_a_trusted_proxy_each_address_has_its_own_cap(self):
        with mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"}):
            for _ in range(3):
                self.assertEqual(self._register(address="198.51.100.1").status_code, 200)
            self.assertEqual(self._register(address="198.51.100.1").status_code, 429)
            self.assertEqual(self._register(address="198.51.100.2").status_code, 200)


if __name__ == "__main__":
    unittest.main()
