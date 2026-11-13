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


def evaluate_attempt(conn, attempt_id, *, clock) -> bool:
    """Flag the ended attempt if it qualifies; return whether it is flagged.

    Does not commit: settlement calls it inside its own transaction, so a
    scored attempt and its flag are saved together. Safe to repeat.
    """
    row = migrate.fetch_one(
        conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
    )
    if row is None or row["final_outcome"] in _VOID_OUTCOMES:
        return False
    run = instability.qualifying_run(_counted_events(conn, attempt_id))
    if run is None:
        return False
    migrate.execute(
        conn,
        "INSERT INTO connection_flags (attempt_id, first_loss_at, last_loss_at, flagged_at)"
        " VALUES (%s, %s, %s, %s) ON CONFLICT (attempt_id) DO NOTHING",
        (attempt_id, run.first_loss_at, run.last_loss_at, clock.now()),
    )
    return True


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
