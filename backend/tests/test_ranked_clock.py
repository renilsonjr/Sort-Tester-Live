"""The ranked engine's time source (issue #8, slice 1)."""
from datetime import datetime, timedelta, timezone
import unittest

from backend.ranked.clock import Clock, SystemClock, system_clock


class FakeClock:
    """A controllable clock for tests: it reports a fixed time and advances
    only when told, so the engine's 10-second deadlines are deterministic.
    """

    def __init__(self, start: datetime):
        self._now = start

    def now(self) -> datetime:
        return self._now

    def advance(self, seconds: float) -> None:
        self._now += timedelta(seconds=seconds)


class SystemClockTests(unittest.TestCase):
    def test_now_is_timezone_aware_utc(self):
        moment = SystemClock().now()
        self.assertIsNotNone(moment.tzinfo)
        self.assertEqual(moment.utcoffset(), timedelta(0))

    def test_now_is_non_decreasing(self):
        clock = system_clock()
        first = clock.now()
        second = clock.now()
        self.assertGreaterEqual(second, first)


class FakeClockTests(unittest.TestCase):
    def test_reports_start_time_until_advanced(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = FakeClock(start)
        self.assertEqual(clock.now(), start)

    def test_advance_moves_time_forward(self):
        start = datetime(2026, 1, 1, tzinfo=timezone.utc)
        clock = FakeClock(start)
        clock.advance(10)
        self.assertEqual(clock.now(), start + timedelta(seconds=10))

    def test_satisfies_the_clock_protocol(self):
        clock: Clock = FakeClock(datetime(2026, 1, 1, tzinfo=timezone.utc))
        self.assertIsInstance(clock.now(), datetime)


if __name__ == "__main__":
    unittest.main()
