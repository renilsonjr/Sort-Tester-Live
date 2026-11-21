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
from backend.ranked import engine, flags, settlement, tiebreaks


class NotOwnerError(PermissionError):
    """Raised when an account that is not the owner tries to record one."""


def _require_owner(conn, acting_account_id) -> None:
    row = migrate.fetch_one(
        conn,
        "SELECT 1 AS ok FROM accounts"
        " WHERE id = %s AND is_owner = true AND deleted_at IS NULL",
        (acting_account_id,),
    )
    if row is None:
        raise NotOwnerError(acting_account_id)


def record_outage(conn, *, acting_account_id, starts_at, ends_at, clock) -> int:
    """Save a confirmed outage and apply its consequences.

    Returns how many flags were removed for good: flags whose run overlapped
    the outage and whose attempt no longer qualifies without it.

    The owner check lives **here**, not in whichever route eventually calls
    this (audit L5). This function voids attempts and rewrites flags for
    every account on the server; left as a bare primitive, it would be
    correct only for as long as every future caller remembered. There is no
    route today, which is exactly when the check is cheap to add.
    """
    _require_owner(conn, acting_account_id)
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
    # a prize tie-break round is restarted whole rather than voided attempt
    # by attempt (settled Decisions 9-10)
    tiebreaks.void_rounds_for_outage(
        conn, outage_start=starts_at, outage_end=ends_at, clock=clock
    )

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
