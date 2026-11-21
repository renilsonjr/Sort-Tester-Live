"""Server-owned time source for the ranked engine.

The engine never reads the wall clock directly; it asks a ``Clock``. Production
uses :class:`SystemClock` (real UTC time). Tests inject a controllable clock so
the ten-second question deadlines are deterministic without any real waiting.
"""
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable


@runtime_checkable
class Clock(Protocol):
    """Anything that can report the current time as an aware UTC datetime."""

    def now(self) -> datetime:
        ...


class SystemClock:
    """Real wall-clock time, always timezone-aware UTC."""

    def now(self) -> datetime:
        return datetime.now(timezone.utc)


def system_clock() -> SystemClock:
    """Return the production clock."""
    return SystemClock()
