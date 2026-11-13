"""The season clock (issue #23).

A season has a scheduled end and a status derived from the clock. There is no
background timer: like the attempt engine's deadlines, everything here is
worked out from the stored times and the ``now`` the caller passes.

Rules are the owner's (decision record, Decisions 11 and 13): Pre-Season runs
until a manual launch and has no scheduled end; an official season stops
admitting new Ranked attempts at its end, and attempts already started get a
five-minute finishing window.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.db import migrate

FINISHING_WINDOW_SECONDS = 300


@dataclass(frozen=True)
class SeasonStatus:
    season_id: str
    phase: str               # 'pre_season' or 'official'
    label: str
    closes_at: datetime | None
    status: str              # 'open', 'finishing', 'closed' or 'frozen'


def ensure_pre_season(conn, label: str = "Pre-Season"):
    """Create the Pre-Season if there is no season yet; return the newest
    season's id. Creates nothing when any season already exists."""
    row = _newest(conn)
    if row is None:
        row = migrate.fetch_one(
            conn,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', %s) RETURNING id",
            (label,),
        )
    conn.commit()
    return row["id"]


def admitting_season(conn, now: datetime):
    """Return the id of the season admitting new Ranked attempts at ``now``.

    ``None`` when no season admits. A season admits while it is neither closed
    nor frozen and its scheduled end, if it has one, is still in the future;
    at exactly the scheduled end admission has stopped.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM seasons WHERE closed_at IS NULL AND frozen_at IS NULL"
        " AND (closes_at IS NULL OR closes_at > %s)"
        " ORDER BY opened_at DESC LIMIT 1",
        (now,),
    )
    return None if row is None else row["id"]


def season_status(conn, season_id, now: datetime) -> SeasonStatus:
    """Report the season's details and where it is in its life at ``now``."""
    row = migrate.fetch_one(
        conn,
        "SELECT phase, label, closes_at, closed_at, frozen_at FROM seasons"
        " WHERE id = %s",
        (season_id,),
    )
    if row is None:
        raise ValueError("unknown season")
    return SeasonStatus(
        season_id=season_id,
        phase=row["phase"],
        label=row["label"],
        closes_at=row["closes_at"],
        status=_status(row, now),
    )


def _status(row, now) -> str:
    if row["frozen_at"] is not None:
        return "frozen"
    ended_at = _ended_at(row, now)
    if ended_at is None:
        return "open"
    window = timedelta(seconds=FINISHING_WINDOW_SECONDS)
    return "finishing" if now < ended_at + window else "closed"


def _ended_at(row, now):
    """When the season stopped admitting: a manual close, or the scheduled end
    once it has passed. ``None`` while it still admits."""
    ends = [
        moment for moment in (row["closed_at"], row["closes_at"])
        if moment is not None and moment <= now
    ]
    return min(ends) if ends else None


def _newest(conn):
    return migrate.fetch_one(
        conn, "SELECT id FROM seasons ORDER BY opened_at DESC LIMIT 1"
    )
