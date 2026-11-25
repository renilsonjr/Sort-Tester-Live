import zlib
"""Quiz Code checks are bounded: how many run at once, how many one address
may fail in a window, and how much the limiters remember."""
import os
import threading
import time
import unittest
from contextlib import contextmanager
from unittest import mock

from fastapi.testclient import TestClient

from backend.auth import credentials, verification_gate
from backend.auth.rate_limit import AddressAttemptLimiter, LoginRateLimiter
from backend.auth.verification_gate import VerificationBusy, VerificationGate
from backend.db import migrate, settings
from backend.main import create_app
from backend.routers import auth as auth_router
from backend.tests.browser import BROWSER


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class ConcurrencyProbe:
    """Stands in for the expensive step and records how many overlap."""

    def __init__(self, seconds=0.05):
        self.seconds = seconds
        self.running = 0
        self.most = 0
        self.calls = 0
        self._lock = threading.Lock()

    def __call__(self, *args, **kwargs):
        with self._lock:
            self.running += 1
            self.calls += 1
            self.most = max(self.most, self.running)
        time.sleep(self.seconds)
        with self._lock:
            self.running -= 1
        return True


def run_together(count, work):
    results = [None] * count
    start = threading.Barrier(count)

    def one(index):
        start.wait()
        try:
            results[index] = work(index)
        except Exception as exc:  # the outcome under test, kept for asserts
            results[index] = exc

    threads = [threading.Thread(target=one, args=(i,)) for i in range(count)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)
    return results


class VerificationGateTests(unittest.TestCase):
    def test_no_more_than_the_allowed_number_run_at_once(self):
        gate = VerificationGate(running=2, waiting=8, wait_seconds=10)
        probe = ConcurrencyProbe()

        def work(_):
            with gate.turn():
                return probe()

        results = run_together(8, work)
        self.assertEqual(results, [True] * 8)
        self.assertEqual(probe.most, 2)

    def test_a_full_line_is_told_busy_at_once(self):
        gate = VerificationGate(running=1, waiting=1, wait_seconds=10)
        probe = ConcurrencyProbe(seconds=0.3)

        def work(_):
            with gate.turn():
                return probe()

        results = run_together(5, work)
        self.assertEqual(sum(1 for r in results if r is True), 2)
        self.assertEqual(
            sum(1 for r in results if isinstance(r, VerificationBusy)), 3
        )
        self.assertEqual(probe.most, 1)

    def test_waiting_ends_after_the_time_limit(self):
        gate = VerificationGate(running=1, waiting=4, wait_seconds=0.05)
        with gate.turn():
            began = time.monotonic()
            outcome = run_together(1, lambda _: gate.turn().__enter__())[0]
            waited = time.monotonic() - began
        self.assertIsInstance(outcome, VerificationBusy)
        self.assertLess(waited, 5)

    def test_a_turn_is_returned_when_the_work_raises(self):
        gate = VerificationGate(running=1, waiting=0, wait_seconds=0)
        with self.assertRaises(KeyError):
            with gate.turn():
                raise KeyError("boom")
        with gate.turn():
            pass

    def test_hashing_and_verifying_share_the_two_turns(self):
        probe = ConcurrencyProbe()
        hasher = mock.Mock()
        hasher.verify.side_effect = probe
        hasher.hash.side_effect = probe
        gate = VerificationGate(running=2, waiting=8, wait_seconds=10)

        def work(index):
            if index % 2:
                return credentials.verify_login_id("AAAA-AAAA-AAAA-AAAA", "x")
            return credentials.hash_login_id("AAAA-AAAA-AAAA-AAAA")

        with mock.patch.object(credentials, "_hasher", return_value=hasher), \
                mock.patch.object(credentials, "get_verification_gate", return_value=gate):
            results = run_together(8, work)
        self.assertEqual(results, [True] * 8)
        self.assertEqual(probe.most, 2)

    def test_the_shipped_gate_allows_two_and_a_line_shorter_than_the_pool(self):
        from backend.db import pool

        gate = verification_gate.get_verification_gate()
        self.assertEqual(gate.running, 2)
        self.assertLess(gate.running + gate.waiting, pool.MAX_SIZE)


class LoginRateLimiterMemoryTests(unittest.TestCase):
    def test_asking_about_a_key_does_not_store_it(self):
        limiter = LoginRateLimiter()
        for n in range(100):
            self.assertTrue(limiter.is_allowed(f"key-{n}"))
        self.assertEqual(len(limiter), 0)

    def test_the_number_of_keys_never_passes_the_cap(self):
        limiter = LoginRateLimiter(max_keys=50)
        for n in range(500):
            limiter.record_failure(f"key-{n}")
            self.assertLessEqual(len(limiter), 50)
        self.assertEqual(len(limiter), 50)

    def test_keys_whose_window_has_passed_are_dropped(self):
        clock = FakeClock()
        limiter = LoginRateLimiter(window_seconds=300, lockout_seconds=300, clock=clock)
        for n in range(30):
            limiter.record_failure(f"key-{n}")
        clock.advance(301)
        limiter.record_failure("fresh")
        self.assertEqual(len(limiter), 1)

    def test_a_blocked_key_stays_blocked_while_other_keys_come_and_go(self):
        clock = FakeClock()
        limiter = LoginRateLimiter(max_failures=10, max_keys=50, clock=clock)
        for _ in range(10):
            limiter.record_failure("blocked")
        for n in range(40):
            clock.advance(5)
            limiter.record_failure(f"other-{n}")
        self.assertFalse(limiter.is_allowed("blocked"))
        clock.advance(120)  # 320s after its last failure
        self.assertTrue(limiter.is_allowed("blocked"))

    def test_a_success_forgets_only_that_key(self):
        limiter = LoginRateLimiter()
        limiter.record_failure("a")
        limiter.record_failure("b")
        limiter.record_success("a")
        self.assertEqual(len(limiter), 1)


class AddressAttemptLimiterTests(unittest.TestCase):
    def test_the_twenty_first_in_five_minutes_is_refused(self):
        limiter = AddressAttemptLimiter(clock=FakeClock())
        self.assertEqual([limiter.reserve("a") for _ in range(21)], [True] * 20 + [False])

    def test_one_address_at_its_cap_leaves_another_alone(self):
        limiter = AddressAttemptLimiter(clock=FakeClock())
        for _ in range(20):
            limiter.reserve("a")
        self.assertFalse(limiter.reserve("a"))
        self.assertTrue(limiter.reserve("b"))

    def test_a_released_check_does_not_count(self):
        limiter = AddressAttemptLimiter(clock=FakeClock())
        for _ in range(100):
            self.assertTrue(limiter.reserve("a"))
            limiter.release("a")
        self.assertEqual(len(limiter), 0)

    def test_the_window_slides(self):
        clock = FakeClock()
        limiter = AddressAttemptLimiter(clock=clock)
        for _ in range(20):
            limiter.reserve("a")
        clock.advance(299)
        self.assertFalse(limiter.reserve("a"))
        clock.advance(2)
        self.assertTrue(limiter.reserve("a"))

    def test_the_number_of_addresses_never_passes_the_cap(self):
        limiter = AddressAttemptLimiter(max_keys=50, clock=FakeClock())
        for n in range(500):
            limiter.reserve(f"address-{n}")
            self.assertLessEqual(len(limiter), 50)

    def test_old_addresses_are_dropped(self):
        clock = FakeClock()
        limiter = AddressAttemptLimiter(clock=clock)
        for n in range(30):
            limiter.reserve(f"address-{n}")
        clock.advance(301)
        limiter.reserve("fresh")
        self.assertEqual(len(limiter), 1)


def wrong_code(n):
    return f"WRNG-WRNG-WRNG-{n:04d}"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SignInLimitsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.client = TestClient(create_app(), headers=BROWSER)
        trusted = mock.patch.dict(os.environ, {"SORT_TEST_TRUST_PROXY": "1"})
        trusted.start()
        self.addCleanup(trusted.stop)

    def _login(self, login_id, address, client=None, username=None):
        # A registered code signs in with its own username. A wrong code is
        # tried against an account of its own (one name per code), so these
        # tests reach the per-address cap and not the per-account one.
        if username is None:
            username = getattr(self, "_names", {}).get(
                login_id, f"nobody_{zlib.crc32(login_id.encode())}"
            )
        return (client or self.client).post(
            "/api/auth/login",
            json={"username": username, "login_id": login_id},
            headers={"X-Forwarded-For": address},
        )

    def _register(self, username):
        login_id = self.client.post(
            "/api/auth/register", json={"username": username}
        ).json()["login_id"]
        if not hasattr(self, "_names"):
            self._names = {}
        self._names[login_id] = username
        return login_id

    def _count_checks(self):
        real = auth_router.check_login_candidates
        spy = mock.Mock(side_effect=real)
        patcher = mock.patch.object(auth_router, "check_login_candidates", spy)
        patcher.start()
        self.addCleanup(patcher.stop)
        return spy

    def test_the_twenty_first_failed_sign_in_from_an_address_is_not_checked(self):
        checks = self._count_checks()
        codes = [
            self._login(wrong_code(n), "192.168.40.1").status_code for n in range(22)
        ]
        self.assertEqual(codes, [401] * 20 + [429] * 2)
        self.assertEqual(checks.call_count, 20)

    def test_an_address_at_its_cap_does_not_hold_back_another(self):
        for n in range(21):
            self._login(wrong_code(n), "192.168.40.2")
        self.assertEqual(self._login(wrong_code(99), "192.168.40.2").status_code, 429)
        self.assertEqual(self._login(wrong_code(99), "192.168.40.3").status_code, 401)

    def test_sign_ins_that_succeed_do_not_use_the_allowance(self):
        login_id = self._register("limits_many")
        codes = [self._login(login_id, "192.168.40.4").status_code for _ in range(25)]
        self.assertEqual(codes, [200] * 25)

    def test_the_right_code_still_works_after_nineteen_wrong_ones(self):
        login_id = self._register("limits_late")
        for n in range(19):
            self._login(wrong_code(n), "192.168.40.5")
        self.assertEqual(self._login(login_id, "192.168.40.5").status_code, 200)

    def test_a_malformed_code_counts_like_any_other_wrong_one(self):
        codes = [
            self._login("not a code!!", "192.168.40.6").status_code for _ in range(21)
        ]
        # the per-account limit (10) is reached first; either way none is a 500
        # and nothing past the address cap is checked
        self.assertEqual(codes[:10], [401] * 10)
        self.assertEqual(set(codes[10:]), {429})

    def test_eight_sign_ins_together_never_check_more_than_two_at_once(self):
        probe = ConcurrencyProbe(seconds=0.1)
        hasher = mock.Mock()
        hasher.verify.side_effect = probe
        # the dummy verifier is made on first use; make it before patching
        self._login(wrong_code(0), "192.168.40.7")
        with mock.patch.object(credentials, "_hasher", return_value=hasher):
            results = run_together(
                8, lambda n: self._login(wrong_code(n), f"192.168.41.{n}").status_code
            )
        self.assertEqual(probe.most, 2)
        # two ran, four waited their turn, two found the line full
        self.assertEqual(sorted(results), [401] * 6 + [503] * 2)

    def test_busy_is_a_503_that_says_when_to_retry_and_uses_no_allowance(self):
        with mock.patch.object(
            auth_router, "check_login_candidates", side_effect=VerificationBusy()
        ):
            responses = [self._login(wrong_code(n), "192.168.40.8") for n in range(25)]
        self.assertEqual({r.status_code for r in responses}, {503})
        self.assertEqual(responses[0].headers["retry-after"], "5")
        self.assertEqual(self._login(wrong_code(0), "192.168.40.8").status_code, 401)

    def test_no_connection_is_held_while_the_code_is_checked(self):
        held = {"now": 0, "during_check": None}
        real_connection = auth_router._db_connection
        real_check = auth_router.check_login_candidates

        @contextmanager
        def counting_connection():
            with real_connection() as conn:
                held["now"] += 1
                try:
                    yield conn
                finally:
                    held["now"] -= 1

        def check(normalized, candidates):
            held["during_check"] = held["now"]
            return real_check(normalized, candidates)

        login_id = self._register("limits_conn")
        with mock.patch.object(auth_router, "_db_connection", counting_connection), \
                mock.patch.object(auth_router, "check_login_candidates", check):
            self.assertEqual(self._login(login_id, "192.168.40.9").status_code, 200)
        self.assertEqual(held["during_check"], 0)

    def test_a_code_revoked_while_it_was_being_checked_signs_nobody_in(self):
        login_id = self._register("limits_revoked")
        real_check = auth_router.check_login_candidates

        def check_then_revoke(normalized, candidates):
            candidate = real_check(normalized, candidates)
            conn = migrate.connect(self.conninfo)
            try:
                migrate.execute(
                    conn,
                    "UPDATE login_credentials SET revoked_at = now() WHERE id = %s",
                    (candidate["id"],),
                )
                conn.commit()
            finally:
                conn.close()
            return candidate

        with mock.patch.object(auth_router, "check_login_candidates", check_then_revoke):
            response = self._login(login_id, "192.168.40.10")
        self.assertEqual(response.status_code, 401)
        self.assertNotIn("sort_tester_session", response.cookies)

    def test_wrong_codes_on_reentry_count_against_the_address_too(self):
        login_id = self._register("limits_reauth")
        self.assertEqual(self._login(login_id, "192.168.40.11").status_code, 200)
        codes = [
            self.client.post(
                "/api/auth/reauthenticate",
                json={"login_id": wrong_code(n)},
                headers={"X-Forwarded-For": "192.168.40.11"},
            ).status_code
            for n in range(11)
        ]
        # the per-account limit (10) stops re-entry first ...
        self.assertEqual(codes, [403] * 10 + [429])
        # ... and those ten counted against the address too: ten more
        # failures from it, on other accounts, reach its cap of twenty
        others = [self._login(wrong_code(n), "192.168.40.11").status_code for n in range(11)]
        self.assertEqual(others, [401] * 10 + [429])


if __name__ == "__main__":
    unittest.main()
