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


def _client_key(request) -> str:
    # Prefer X-Forwarded-For for deployments behind a trusted proxy; otherwise
    # fall back to the direct client host. In production this should be set by
    # the ingress/proxy, never by the client.
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
