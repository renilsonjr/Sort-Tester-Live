import ipaddress
import os
import threading
import time
from collections import OrderedDict, defaultdict
from dataclasses import dataclass


@dataclass
class _AttemptBucket:
    failures: int
    first_failure_at: float
    last_failure_at: float


# Far more keys than the pilot produces in a window, and small enough that
# the table stays a few megabytes however many distinct keys are offered.
MAX_TRACKED_KEYS = 10_000


class LoginRateLimiter:
    """In-memory rate limiter for failed login attempts.

    Keys are typically a source identifier such as IP address or a
    combination of IP + target lookup key. After a threshold of failures
    within a window, further attempts are blocked until the window expires.

    The table is bounded: a key whose window has passed is dropped, and at
    most ``max_keys`` are kept, the ones that failed longest ago going first.

    This is suitable for a single-instance pilot. A distributed deployment
    would need a shared store such as Redis.
    """

    def __init__(
        self,
        max_failures: int = 10,
        window_seconds: float = 300.0,
        lockout_seconds: float = 300.0,
        max_keys: int = MAX_TRACKED_KEYS,
        clock=time.monotonic,
    ):
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        self.max_keys = max_keys
        self._clock = clock
        # Ordered by last failure, oldest first, so both kinds of forgetting
        # only ever look at the front.
        self._buckets: OrderedDict[str, _AttemptBucket] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._buckets)

    def is_allowed(self, key: str) -> bool:
        now = self._clock()
        with self._lock:
            # Looking a key up never stores it: only a failure does.
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket.first_failure_at > self.window_seconds:
                return True
            if bucket.failures >= self.max_failures:
                # Still within lockout window?
                return now - bucket.last_failure_at >= self.lockout_seconds
            return True

    def record_failure(self, key: str) -> None:
        now = self._clock()
        with self._lock:
            bucket = self._buckets.get(key)
            if bucket is None or now - bucket.first_failure_at > self.window_seconds:
                self._buckets[key] = _AttemptBucket(1, now, now)
            else:
                bucket.failures += 1
                bucket.last_failure_at = now
            self._buckets.move_to_end(key)
            self._forget(now)

    def _forget(self, now: float) -> None:
        """Drop keys that can no longer block anything, then keep to the cap."""
        keep_for = max(self.window_seconds, self.lockout_seconds)
        while self._buckets:
            oldest = next(iter(self._buckets.values()))
            if now - oldest.last_failure_at <= keep_for:
                break
            self._buckets.popitem(last=False)
        while len(self._buckets) > self.max_keys:
            self._buckets.popitem(last=False)

    def record_success(self, key: str) -> None:
        """Clear the failures counted against one key.

        Only that key: with keys of client+credential (``_login_rate_key``)
        this forgives the owner their own mistyped attempts and reaches
        nothing else, so signing in to one account can no longer hand an
        attacker a fresh run of guesses at another (audit H-2).
        """
        with self._lock:
            self._buckets.pop(key, None)


class AddressAttemptLimiter:
    """In-memory cap on failed sign-in checks from one network address.

    Owner decision, 2026-11-23: at most 20 failed checks in 5 minutes from
    one address, whatever Quiz Codes were tried. A check that succeeds does
    not count, so a whole shift signing in over shared workplace Wi-Fi is
    never held back by it.

    A check is counted when it starts (``reserve``) and given back if it
    turns out not to be a failure (``release``). Counting first is what
    makes the cap hold for requests that arrive together: the twenty-first
    is refused before it costs anything, even while the first twenty are
    still being checked.

    Bounded like ``LoginRateLimiter``, and for the same single-instance
    pilot: counts reset when the process restarts.
    """

    def __init__(
        self,
        max_attempts: int = 20,
        window_seconds: float = 300.0,
        max_keys: int = MAX_TRACKED_KEYS,
        clock=time.monotonic,
    ):
        self.max_attempts = max_attempts
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self._clock = clock
        self._attempts: OrderedDict[str, list[float]] = OrderedDict()
        self._lock = threading.Lock()

    def __len__(self) -> int:
        with self._lock:
            return len(self._attempts)

    def reserve(self, key: str) -> bool:
        """Count one check for ``key`` if it fits; False means refuse it."""
        now = self._clock()
        with self._lock:
            self._forget(now)
            recent = [
                t for t in self._attempts.get(key, ()) if now - t < self.window_seconds
            ]
            if len(recent) >= self.max_attempts:
                self._attempts[key] = recent
                return False
            recent.append(now)
            self._attempts[key] = recent
            self._attempts.move_to_end(key)
            while len(self._attempts) > self.max_keys:
                self._attempts.popitem(last=False)
            return True

    def release(self, key: str) -> None:
        """Give back the most recent check counted for ``key``."""
        with self._lock:
            attempts = self._attempts.get(key)
            if attempts:
                attempts.pop()
                if not attempts:
                    del self._attempts[key]

    def _forget(self, now: float) -> None:
        # Ordered by latest check, oldest first: stop at the first live one.
        while self._attempts:
            key, attempts = next(iter(self._attempts.items()))
            if attempts and now - attempts[-1] < self.window_seconds:
                break
            del self._attempts[key]


# Singleton for the application process.
_default_limiter = LoginRateLimiter()


def get_login_rate_limiter() -> LoginRateLimiter:
    return _default_limiter


MAX_TRUSTED_PROXIES = 5


def _trusted_proxies() -> int:
    """How many proxies of our own sit in front of the app (0 = none).

    Set SORT_TEST_TRUST_PROXY to that count where the hosting ingress writes
    X-Forwarded-For; "1" for a single ingress. Anything that is not a small
    whole number trusts nothing.
    """
    raw = os.environ.get("SORT_TEST_TRUST_PROXY", "").strip()
    if not raw.isdigit():
        return 0
    count = int(raw)
    return count if 1 <= count <= MAX_TRUSTED_PROXIES else 0


def _address(entry: str) -> str | None:
    """Return *entry* as one canonical IP address, or None if it is not one."""
    entry = entry.strip()
    if entry.startswith("["):  # [v6]:port
        entry = entry[1:].partition("]")[0]
    elif entry.count(":") == 1:  # v4:port
        entry = entry.partition(":")[0]
    try:
        return str(ipaddress.ip_address(entry))
    except ValueError:
        return None


def _client_key(request) -> str:
    """The network address a request comes from, for rate limiting.

    Each proxy appends the address it received the request from to
    X-Forwarded-For, so the header reads `client-supplied..., real, proxy...`.
    Only the entries our own proxies wrote can be believed, and they are the
    last ones: with N trusted proxies the client's address is the Nth entry
    from the right. Everything further left is whatever the client chose to
    send, so reading the FIRST entry would let anyone pick a fresh address per
    request and never be limited.

    With no trusted proxy, or a header too short or malformed to hold that
    entry, the connection's own address is used.
    """
    connection = request.client.host if request.client else "unknown"
    proxies = _trusted_proxies()
    forwarded = request.headers.get("x-forwarded-for")
    if not proxies or not forwarded:
        return connection
    entries = forwarded.split(",")
    if len(entries) < proxies:
        return connection
    return _address(entries[-proxies]) or connection


def _login_rate_key(request, login_id: str) -> str:
    """The limiter key for an attempt on one credential (audit H-2).

    Keyed by the client *and* the credential it is trying. Keyed by the
    client alone, ten guesses at one login ID refused every other login ID
    from that address -- and behind a single ingress that address is
    everyone, so anyone could lock the whole app out of signing in.

    The target is the credential's lookup key, which is derived, not
    secret, and never leaves the process. An ID too malformed to derive
    one from shares a single bucket: it cannot name an account, so it
    cannot lock one out.
    """
    from backend.auth.credentials import derive_lookup_key

    try:
        target = derive_lookup_key(login_id)
    except ValueError:
        target = "invalid"
    return f"{_client_key(request)}|{target}"


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
