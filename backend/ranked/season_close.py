"""Season close: finishing window, ending, settlement and freeze (issue #23).

The end of a season (decision record, Decision 13): admission stops at the
season's end (the season clock does that); attempts already started get a
five-minute finishing window; when it is over, unfinished attempts are ended
with their partial result and no Quit penalty, everything is settled, and the
season's points are frozen.

There is no background timer. Callers run :func:`finish_due_seasons` when a
request arrives; every time involved is stored, so the result does not depend
on when it runs.
"""
from datetime import timedelta

from backend.db import migrate
from backend.ranked import engine, seasons, settlement


class SeasonCloseError(Exception):
    """The season could not be frozen yet; running the finish again completes it."""


def finish_season(conn, season_id, *, clock) -> bool:
    """End, settle and freeze a season whose finishing window is over.

    Returns True when this call froze the season. Does nothing and returns
    False for a season that is already frozen, has not ended, or is still
    inside its finishing window. The steps before the freeze are idempotent
    and the freeze is written only once nothing of the season is unsettled,
    so an interrupted finish completes when run again.
    """
    now = clock.now()
    season = _lock(conn, season_id)
    ended_at = None if season["frozen_at"] is not None else seasons.ended_at_of(season, now)
    window = timedelta(seconds=seasons.FINISHING_WINDOW_SECONDS)
    if ended_at is None or now < ended_at + window:
        conn.commit()  # nothing to do: release the season lock
        return False
    migrate.execute(
        conn,
        "UPDATE seasons SET closed_at = COALESCE(closed_at, %s) WHERE id = %s",
        (ended_at, season_id),
    )
    conn.commit()

    # endings the clock had already decided are applied first; the rest end
    # as season_close with their partial result and no Quit penalty
    engine.end_attempts_for_season_close(conn, season_id, clock=clock)
    settlement.settle_pending(conn, clock=clock)

    season = _lock(conn, season_id)
    if season["frozen_at"] is not None:
        conn.commit()  # another caller froze it meanwhile
        return False
    unsettled = migrate.fetch_one(
        conn,
        "SELECT COUNT(*) AS n FROM attempts WHERE season_id = %s"
        " AND state <> 'finalized'",
        (season_id,),
    )["n"]
    if unsettled:
        conn.rollback()
        raise SeasonCloseError("attempts of the season are still unsettled")
    migrate.execute(
        conn, "UPDATE seasons SET frozen_at = %s WHERE id = %s", (now, season_id)
    )
    conn.commit()
    return True


def finish_due_seasons(conn, *, clock) -> int:
    """Finish every unfrozen season whose finishing window is over.

    Returns how many this call froze. When nothing is due it is one read.
    """
    now = clock.now()
    cutoff = now - timedelta(seconds=seasons.FINISHING_WINDOW_SECONDS)
    rows = migrate.fetch_all(
        conn,
        "SELECT id FROM seasons WHERE frozen_at IS NULL"
        " AND (closed_at <= %s OR closes_at <= %s) ORDER BY opened_at",
        (cutoff, cutoff),
    )
    conn.commit()
    return sum(1 for row in rows if finish_season(conn, row["id"], clock=clock))


def _lock(conn, season_id):
    row = migrate.fetch_one(
        conn,
        "SELECT closes_at, closed_at, frozen_at FROM seasons WHERE id = %s FOR UPDATE",
        (season_id,),
    )
    if row is None:
        raise ValueError("unknown season")
    return row
