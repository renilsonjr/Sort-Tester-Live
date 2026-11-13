import os
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field


@dataclass
class _AttemptBucket:
    failures: int = 0
    first_failure_at: float = field(default_factory=time.monotonic)
    last_failure_at: float = field(default_factory=time.monotonic)


class LoginRateLimiter:
    """In-memory rate limiter for failed login attempts.

    Keys are typically a source identifier such as IP address or a
    combination of IP + target lookup key. After a threshold of failures
    within a window, further attempts are blocked until the window expires.

    This is suitable for a single-instance pilot. A distributed deployment
    would need a shared store such as Redis.
    """

    def __init__(
        self,
        max_failures: int = 10,
        window_seconds: float = 300.0,
        lockout_seconds: float = 300.0,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self._buckets: dict[str, _AttemptBucket] = defaultdict(_AttemptBucket)
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            # If no failures or window has passed, reset.
            if bucket.failures == 0 or now - bucket.first_failure_at > self.window_seconds:
                return True
            if bucket.failures >= self.max_failures:
                # Still within lockout window?
                if now - bucket.last_failure_at < self.lockout_seconds:
                    return False
                return True
            return True

    def record_failure(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            bucket = self._buckets[key]
            if bucket.failures == 0 or now - bucket.first_failure_at > self.window_seconds:
                bucket.failures = 1
                bucket.first_failure_at = now
            else:
                bucket.failures += 1
            bucket.last_failure_at = now

    def record_success(self, key: str) -> None:
        with self._lock:
            if key in self._buckets:
                del self._buckets[key]


# Singleton for the application process.
_default_limiter = LoginRateLimiter()


def get_login_rate_limiter() -> LoginRateLimiter:
    return _default_limiter


def _trusts_proxy() -> bool:
    return os.environ.get("SORT_TEST_TRUST_PROXY", "").strip() == "1"


def _client_key(request) -> str:
    """The network address a request comes from, for rate limiting.

    X-Forwarded-For is believed only when SORT_TEST_TRUST_PROXY=1, set where a
    trusted proxy (such as the hosting ingress) writes that header. Without
    it, anyone could send a made-up address per request and never be limited,
    so the connection's own address is used.
    """
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded and _trusts_proxy():
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


class RegistrationLimiter:
    """In-memory caps on successful sign-ups (issue #47).

    Owner decision: at most 30 sign-ups per hour from one network address,
    so a whole onboarding session on shared workplace Wi-Fi still works, and
    at most 200 per day in total. Both windows slide. Only successful sign-ups
    are recorded; refused ones (409, 422, 429) do not count.

    Like the login limiter this suits the single-instance pilot: counts reset
    when the process restarts and are not shared between processes.
    """

    def __init__(
        self,
        per_client: int = 30,
        per_client_window: float = 3600.0,
        total: int = 200,
        total_window: float = 86400.0,
        clock=time.monotonic,
    ):
        self.per_client = per_client
        self.per_client_window = per_client_window
        self.total = total
        self.total_window = total_window
        self._clock = clock
        self._by_client: dict[str, list[float]] = defaultdict(list)
        self._all: list[float] = []
        self._lock = threading.Lock()

    def is_allowed(self, key: str) -> bool:
        """Whether one more sign-up from ``key`` fits both caps. Counts nothing."""
        now = self._clock()
        with self._lock:
            self._forget_old(key, now)
            return (
                len(self._by_client[key]) < self.per_client
                and len(self._all) < self.total
            )

    def record(self, key: str) -> None:
        """Count one successful sign-up from ``key``."""
        now = self._clock()
        with self._lock:
            self._by_client[key].append(now)
            self._all.append(now)

    def _forget_old(self, key, now):
        self._by_client[key] = [
            t for t in self._by_client[key] if now - t < self.per_client_window
        ]
        self._all = [t for t in self._all if now - t < self.total_window]
