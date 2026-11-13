"""Recording a confirmed server-wide outage (issue #25).

One entry point does the three things a confirmed outage requires: save it,
void and settle the attempts it interrupted (zero adjustment, no flag), and
remove any review flag the outage explains. A flag returns only if its attempt
still qualifies with the outage's events left out.

Deciding that an outage really happened needs trusted evidence (#13); this
module applies the consequences once it is confirmed. It lives apart from
:mod:`backend.ranked.flags` because it uses settlement, which uses flags.
"""
from backend.db import migrate
from backend.ranked import engine, flags, settlement


def record_outage(conn, *, starts_at, ends_at, clock) -> int:
    """Save a confirmed outage and apply its consequences.

    Returns how many flags were removed for good: flags whose run overlapped
    the outage and whose attempt no longer qualifies without it.
    """
    if ends_at < starts_at:
        raise ValueError("an outage cannot end before it starts")
    migrate.execute(
        conn,
        "INSERT INTO confirmed_outages (starts_at, ends_at, recorded_at)"
        " VALUES (%s, %s, %s)",
        (starts_at, ends_at, clock.now()),
    )
    conn.commit()

    engine.void_attempts_for_outage(conn, outage_start=starts_at, outage_end=ends_at)
    settlement.settle_pending(conn, clock=clock)

    overlapping = migrate.fetch_all(
        conn,
        "SELECT attempt_id, closed_at FROM connection_flags"
        " WHERE first_loss_at <= %s AND last_loss_at >= %s FOR UPDATE",
        (ends_at, starts_at),
    )
    removed = 0
    for row in overlapping:
        # re-check without the outage's events: a run it does not explain stays
        run = flags.qualifying_run_for(conn, row["attempt_id"])
        if run is None:
            migrate.execute(
                conn, "DELETE FROM connection_flags WHERE attempt_id = %s",
                (row["attempt_id"],),
            )
            removed += 1
        elif row["closed_at"] is None:
            # still unstable on its own: an open flag shows the run that remains
            migrate.execute(
                conn,
                "UPDATE connection_flags SET first_loss_at = %s, last_loss_at = %s"
                " WHERE attempt_id = %s",
                (run.first_loss_at, run.last_loss_at, row["attempt_id"]),
            )
        # a closed flag that still qualifies keeps its review unchanged
    conn.commit()
    return removed
