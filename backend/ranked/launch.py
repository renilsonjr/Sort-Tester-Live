"""Official season launch, exactly once (issue #23).

The owner's manual launch (decision record, Decision 12): every unfinished
Pre-Season attempt is voided without applying its result, Pre-Season records
are kept, every balance is reset to 0 and the official season opens.

The official season's existence is the launch marker. Everything before the
final transaction is idempotent, and the reset happens only in the transaction
that inserts the official season, so an interrupted launch is completed by
running it again and there is never a reset without an official season.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

from backend.db import migrate
from backend.ranked import engine, settlement

# Owner decision: the first official season ends December 31, 2026 at
# 11:59 p.m. Eastern, stored as 23:59:00.
DEFAULT_OFFICIAL_END = datetime(
    2026, 12, 31, 23, 59, 0, tzinfo=ZoneInfo("America/New_York")
)


class LaunchError(Exception):
    """Base class for launch errors."""


class InvalidLaunchError(LaunchError):
    """The launch request itself is not acceptable (label or end time)."""


class AlreadyLaunchedError(LaunchError):
    """An official season already exists: launch happens once."""


class NoPreSeasonError(LaunchError):
    """There is no Pre-Season to launch from."""


def launch_official_season(conn, *, label, clock, closes_at=DEFAULT_OFFICIAL_END):
    """Launch the official season; return its id. See the module docstring."""
    now = clock.now()
    label = (label or "").strip()
    if not label:
        raise InvalidLaunchError("the official season needs a name")
    if closes_at <= now:
        raise InvalidLaunchError("the official season must end in the future")

    # Locking the season rows serialises launches and waits for any attempt
    # start in progress, which holds a share lock on its season.
    pre_season_id = _lock_and_pick_pre_season(conn)
    migrate.execute(
        conn,
        "UPDATE seasons SET closed_at = COALESCE(closed_at, %s) WHERE id = %s",
        (now, pre_season_id),
    )
    conn.commit()  # from here no Pre-Season attempt can start

    engine.void_attempts_for_launch(conn, pre_season_id)
    settlement.settle_pending(conn, clock=clock)

    _lock_and_pick_pre_season(conn)  # re-check under lock: still not launched
    unsettled = migrate.fetch_one(
        conn,
        "SELECT COUNT(*) AS n FROM attempts WHERE season_id = %s"
        " AND state <> 'finalized'",
        (pre_season_id,),
    )["n"]
    if unsettled:
        conn.rollback()
        raise LaunchError("Pre-Season attempts are still unsettled; run launch again")
    migrate.execute(
        conn, "UPDATE balances SET current_points = 0, updated_at = %s", (now,)
    )
    migrate.execute(
        conn, "UPDATE seasons SET frozen_at = %s WHERE id = %s", (now, pre_season_id)
    )
    try:
        official = migrate.fetch_one(
            conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', %s, %s, %s) RETURNING id",
            (label, now, closes_at),
        )
    except migrate.IntegrityError:
        conn.rollback()
        raise InvalidLaunchError("that season name is already used") from None
    conn.commit()
    return official["id"]


def _lock_and_pick_pre_season(conn):
    """Lock every season row and return the Pre-Season to launch from."""
    rows = migrate.fetch_all(
        conn,
        "SELECT id, phase, frozen_at FROM seasons ORDER BY opened_at FOR UPDATE",
    )
    if any(row["phase"] == "official" for row in rows):
        conn.rollback()
        raise AlreadyLaunchedError("the official season has already been launched")
    candidates = [
        row for row in rows if row["phase"] == "pre_season" and row["frozen_at"] is None
    ]
    if not candidates:
        conn.rollback()
        raise NoPreSeasonError("there is no Pre-Season to launch from")
    return candidates[-1]["id"]
