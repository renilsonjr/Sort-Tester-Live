"""Run a piece of housekeeping at most once per interval.

The Ranked request path does two kinds of work before every request. The
game's own clock (a season closing, a tie-break round ending, prizes
becoming final) has to be checked each time, because nothing may be
played past it. Retention is different: it deletes what is days old, so
checking it on every request of every player buys nothing and costs each
of them the round trips.

``due()`` answers True at most once per interval, and on its first call,
so a process that has just started does its housekeeping straight away.
One per application instance, like the limiters: with a single process
that is one sweep a minute however many requests arrive.
"""
import threading
import time

RETENTION_INTERVAL_SECONDS = 60.0


class SweepInterval:
    def __init__(self, seconds: float = RETENTION_INTERVAL_SECONDS, clock=time.monotonic):
        self.seconds = seconds
        self._clock = clock
        self._last: float | None = None
        self._lock = threading.Lock()

    def due(self) -> bool:
        """True if the interval has passed since the last True. Claims it."""
        now = self._clock()
        with self._lock:
            if self._last is not None and now - self._last < self.seconds:
                return False
            self._last = now
            return True

    def reset(self) -> None:
        """Make the next call due again."""
        with self._lock:
            self._last = None
