"""A ceiling on how many Quiz Code checks run at the same moment.

Hashing or verifying a Quiz Code is Argon2id, and is expensive on purpose:
by default each one holds 64 MiB and a processor for as long as it runs.
That cost is the protection for a stolen database, but nothing bounded how
many could run together, so the memory and processor in use depended on how
many requests happened to arrive at once.

This lets a fixed number run and makes the rest wait their turn, for a
limited time and in a limited line. A request that finds the line full, or
waits out its time, is told the server is busy (503) and can simply be sent
again; nothing about it was checked and nothing changed.

The line is deliberately shorter than the connection pool
(``backend.db.pool.MAX_SIZE``): some routes wait here while holding a
connection, and running plus waiting must never add up to every connection
there is.
"""
import threading
from contextlib import contextmanager

MAX_RUNNING = 2
MAX_WAITING = 4
MAX_WAIT_SECONDS = 10.0


class VerificationBusy(RuntimeError):
    """No turn became free in time. Nothing was checked."""


class VerificationGate:
    def __init__(
        self,
        running: int = MAX_RUNNING,
        waiting: int = MAX_WAITING,
        wait_seconds: float = MAX_WAIT_SECONDS,
    ):
        self.running = running
        self.waiting = waiting
        self.wait_seconds = wait_seconds
        self._turns = threading.BoundedSemaphore(running)
        self._lock = threading.Lock()
        self._in_line = 0

    @contextmanager
    def turn(self):
        """Hold one of the turns for the length of the block."""
        if not self._turns.acquire(blocking=False):
            with self._lock:
                if self._in_line >= self.waiting:
                    raise VerificationBusy()
                self._in_line += 1
            try:
                got_turn = self._turns.acquire(timeout=self.wait_seconds)
            finally:
                with self._lock:
                    self._in_line -= 1
            if not got_turn:
                raise VerificationBusy()
        try:
            yield
        finally:
            self._turns.release()


# One gate for the application process: every route shares the same turns.
_default_gate = VerificationGate()


def get_verification_gate() -> VerificationGate:
    return _default_gate
