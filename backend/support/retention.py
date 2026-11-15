"""Retention for Support tickets and connection review flags (issue #26).

Decision 8, with Q9 settled. Two clocks run, and they are not the same:

* **A closed case's own detail** goes fifteen days after *that case's*
  closure. For a ticket that is the description the player wrote.
* **The shared connection log** — an attempt's detailed connection events —
  is kept while *any* linked case on that attempt is still open, and goes
  fifteen days after the **last** of them closed.

The link between a ticket and a flag is the attempt. A ticket names the
attempt it is about; a flag names the attempt it was raised on; the
connection events belong to the attempt. So two cases about the same attempt
share one log, with no linking table to keep in step.

That sharing is why this sweep replaced ``flags.purge_closed_flags``, which
deleted an attempt's events fifteen days after its flag closed and knew
nothing about tickets. Once tickets exist, it would delete the evidence an
open ticket still needs. The two cleanups cannot be independent, so there is
one sweep and the attempt is its unit.

Seasonal scores and quiz history — attempts, answers, settlements, balance
history — are never touched here.
"""
from datetime import timedelta

from backend.db import migrate

RETENTION_DAYS = 15


def purge_due_cases(conn, *, clock) -> dict:
    """Run both cleanups; return what was removed.

    ``{"descriptions": n, "logs": n}``: closed ticket descriptions cleared,
    and attempts whose shared connection log was deleted. Committing is the
    caller's, except that this runs as one statement batch per cleanup.

    When nothing is due this is two reads.
    """
    cutoff = clock.now() - timedelta(days=RETENTION_DAYS)

    # An attempt's shared log is due only when every case on it is closed and
    # the last closure is old enough. One open case of either kind holds the
    # whole log, which is the point: evidence an open case needs must not
    # disappear underneath it.
    due_logs = migrate.fetch_all(
        conn,
        """
        WITH cases AS (
            SELECT attempt_id, closed_at FROM support_tickets
            UNION ALL
            SELECT attempt_id, closed_at FROM connection_flags
        )
        SELECT attempt_id FROM cases
        GROUP BY attempt_id
        HAVING count(*) FILTER (WHERE closed_at IS NULL) = 0
           AND max(closed_at) <= %s
           -- Only attempts that still have something to delete. A closed
           -- ticket stays for the player to see for good, so without this
           -- its attempt would be "due" on every sweep for ever, and the
           -- sweep runs on every ranked request.
           AND (EXISTS (SELECT 1 FROM attempt_connection_events e
                        WHERE e.attempt_id = cases.attempt_id)
                OR EXISTS (SELECT 1 FROM connection_flags f
                           WHERE f.attempt_id = cases.attempt_id))
        """,
        (cutoff,),
    )
    for row in due_logs:
        migrate.execute(
            conn,
            "DELETE FROM attempt_connection_events WHERE attempt_id = %s",
            (row["attempt_id"],),
        )
        # The flag row is the reviewer's record of that log, so it goes with
        # it. The ticket row stays: the player keeps seeing that they asked,
        # and what the outcome was, with the description gone.
        migrate.execute(
            conn,
            "DELETE FROM connection_flags WHERE attempt_id = %s",
            (row["attempt_id"],),
        )

    # A ticket's own description runs on its own clock, whatever the shared
    # log is doing. Q9's exception extends to the shared evidence only.
    cleared = migrate.fetch_all(
        conn,
        "UPDATE support_tickets SET description = NULL"
        " WHERE closed_at <= %s AND description IS NOT NULL"
        " RETURNING id",
        (cutoff,),
    )
    return {"descriptions": len(cleared), "logs": len(due_logs)}


def shared_log_deletion_date(conn, attempt_id):
    """When this attempt's connection log is due to go, or None.

    ``None`` while any case on the attempt is open — there is no date to
    show, because the clock has not started. The Support screens show either
    this date or the fact that an open linked case is holding the evidence.
    """
    row = migrate.fetch_one(
        conn,
        """
        WITH cases AS (
            SELECT attempt_id, closed_at FROM support_tickets
            UNION ALL
            SELECT attempt_id, closed_at FROM connection_flags
        )
        SELECT max(closed_at) AS last_closed,
               count(*) FILTER (WHERE closed_at IS NULL) AS still_open
        FROM cases WHERE attempt_id = %s
        """,
        (attempt_id,),
    )
    if row is None or row["last_closed"] is None or row["still_open"]:
        return None
    return row["last_closed"] + timedelta(days=RETENTION_DAYS)
