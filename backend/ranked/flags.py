"""Private connection review flags (issue #25).

An attempt whose connection events contain a qualifying run of losses (see
:mod:`backend.ranked.instability`) gets one private review flag. Losses inside
a confirmed server outage never count, and a voided attempt is never flagged.

A flag is an instability signal for a human reviewer, not proof of cheating.
It never deducts points, suspends, restricts Ranked or creates a Support
ticket (decision record, Decision 7): nothing reads a flag to decide anything.
"""
from backend.db import migrate
from backend.ranked import instability

_VOID_OUTCOMES = ("outage_void", "launch_reset")
CLOSING_OUTCOMES = ("network_instability", "insufficient_evidence")


class FlagNotFoundError(Exception):
    """The attempt has no connection flag."""


def evaluate_attempt(conn, attempt_id, *, clock) -> bool:
    """Flag the ended attempt if it qualifies; return whether it is flagged.

    Does not commit: settlement calls it inside its own transaction, so a
    scored attempt and its flag are saved together. Safe to repeat.
    """
    run = qualifying_run_for(conn, attempt_id)
    if run is None:
        return False
    migrate.execute(
        conn,
        "INSERT INTO connection_flags (attempt_id, first_loss_at, last_loss_at, flagged_at)"
        " VALUES (%s, %s, %s, %s) ON CONFLICT (attempt_id) DO NOTHING",
        (attempt_id, run.first_loss_at, run.last_loss_at, clock.now()),
    )
    return True


def qualifying_run_for(conn, attempt_id):
    """The attempt's qualifying run with confirmed outages left out, or None.
    A voided attempt never qualifies."""
    row = migrate.fetch_one(
        conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
    )
    if row is None or row["final_outcome"] in _VOID_OUTCOMES:
        return None
    return instability.qualifying_run(_counted_events(conn, attempt_id))


def open_flags(conn) -> list[dict]:
    """Open flags, oldest first, with only the evidence a reviewer needs: the
    player's display name and tag, the run, and the attempt's connection
    events. Nothing else about the player is returned."""
    rows = migrate.fetch_all(
        conn,
        "SELECT f.attempt_id, ac.username, ac.tag, f.first_loss_at, f.last_loss_at,"
        " f.flagged_at FROM connection_flags f"
        " JOIN attempts a ON a.id = f.attempt_id"
        " JOIN accounts ac ON ac.id = a.account_id"
        " WHERE f.closed_at IS NULL ORDER BY f.flagged_at, f.attempt_id",
    )
    for row in rows:
        row["events"] = migrate.fetch_all(
            conn,
            "SELECT kind, occurred_at FROM attempt_connection_events"
            " WHERE attempt_id = %s ORDER BY occurred_at, kind",
            (row["attempt_id"],),
        )
    conn.commit()
    return rows


def close_flag(conn, attempt_id, outcome, *, clock) -> str:
    """Close an open flag with a review outcome; return the stored outcome.

    Closing a closed flag changes nothing. Closure never touches points or
    access.
    """
    if outcome not in CLOSING_OUTCOMES:
        raise ValueError(f"unknown review outcome: {outcome!r}")
    row = migrate.fetch_one(
        conn,
        "SELECT closed_outcome FROM connection_flags WHERE attempt_id = %s FOR UPDATE",
        (attempt_id,),
    )
    if row is None:
        conn.rollback()
        raise FlagNotFoundError("the attempt has no connection flag")
    if row["closed_outcome"] is not None:
        conn.commit()
        return row["closed_outcome"]
    migrate.execute(
        conn,
        "UPDATE connection_flags SET closed_at = %s, closed_outcome = %s"
        " WHERE attempt_id = %s",
        (clock.now(), outcome, attempt_id),
    )
    conn.commit()
    return outcome


def _counted_events(conn, attempt_id):
    """The attempt's connection events, minus any inside a confirmed outage."""
    rows = migrate.fetch_all(
        conn,
        "SELECT e.kind, e.occurred_at FROM attempt_connection_events e"
        " WHERE e.attempt_id = %s AND NOT EXISTS ("
        "   SELECT 1 FROM confirmed_outages o"
        "   WHERE e.occurred_at BETWEEN o.starts_at AND o.ends_at)",
        (attempt_id,),
    )
    return [(row["kind"], row["occurred_at"]) for row in rows]
