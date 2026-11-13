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

    @property
    def approvals_open(self) -> bool:
        """Whether a new prize-eligibility approval may still be recorded.

        Only while the season is open: from its end onward, including the
        finishing window, no new approval is admitted (#23). A quiz already
        approved and validly completed inside the window still counts, since
        an attempt keeps the season it started in.
        """
        return self.status == "open"


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


def admitting_season(conn, now: datetime, *, lock: bool = False):
    """Return the id of the season admitting new Ranked attempts at ``now``.

    ``None`` when no season admits. A season admits while it is neither closed
    nor frozen and its scheduled end, if it has one, is still in the future;
    at exactly the scheduled end admission has stopped.

    With ``lock`` the season row is share-locked until the caller's
    transaction ends. An attempt start uses this so a launch, which locks the
    season rows exclusively, waits for it and then sees its attempt.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM seasons WHERE closed_at IS NULL AND frozen_at IS NULL"
        " AND (closes_at IS NULL OR closes_at > %s)"
        " ORDER BY opened_at DESC LIMIT 1" + (" FOR SHARE" if lock else ""),
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


def current_season_status(conn, now: datetime) -> SeasonStatus | None:
    """Status of the newest season, or ``None`` when there is no season yet.

    The lifecycle contract for standings and tie-breaks: a season's points
    are final exactly when its status is ``frozen``.
    """
    row = _newest(conn)
    return None if row is None else season_status(conn, row["id"], now)


def approvals_open(conn, now: datetime) -> bool:
    """Whether the current season still admits new prize-eligibility
    approvals at ``now``. False when there is no season. The one place the
    approval feature (#11) asks before recording an approval."""
    current = current_season_status(conn, now)
    return current is not None and current.approvals_open


@dataclass(frozen=True)
class LaunchFact:
    season_id: str
    label: str
    launched_at: datetime


def official_launch(conn) -> LaunchFact | None:
    """The durable, exactly-once fact that the official season was launched.

    ``None`` before launch. Launch reminders (#27) read this to create their
    own per-recipient messages; launch itself writes no outbox row, because
    those rows need the verified email and consent that #27 owns.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT id, label, opened_at FROM seasons WHERE phase = 'official'"
        " ORDER BY opened_at LIMIT 1",
    )
    if row is None:
        return None
    return LaunchFact(season_id=row["id"], label=row["label"], launched_at=row["opened_at"])


def _status(row, now) -> str:
    if row["frozen_at"] is not None:
        return "frozen"
    ended_at = ended_at_of(row, now)
    if ended_at is None:
        return "open"
    window = timedelta(seconds=FINISHING_WINDOW_SECONDS)
    return "finishing" if now < ended_at + window else "closed"


def ended_at_of(row, now):
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
