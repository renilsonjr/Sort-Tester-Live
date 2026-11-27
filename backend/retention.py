"""Delete what has outlived its retention period.

One list of everything this server promises to forget, and when. Each
line belongs to a different part of the app, which is why the list lives
above all of them rather than inside one router.

How often this runs is not decided here: see backend/sweep_interval.py.
"""
from backend.auth import deletion, recovery_messages, sessions
from backend.support import retention as support_retention


def sweep(conn, *, clock) -> None:
    """Run every retention deletion, and keep the result.

    Committed here rather than left to the caller: most requests that
    carry this sweep only read and never commit, and a sweep that waits a
    minute for its next turn must not be rolled back by whichever request
    drew it. The caller hands over a connection with nothing else open on
    it, so this commits the sweep and only the sweep.
    """
    # a closed ticket's description goes fifteen days after its own closure,
    # and an attempt's shared connection log goes fifteen days after the last
    # case on it closes (#26)
    support_retention.purge_due_cases(conn, clock=clock)
    # accepted account deletions (#47)
    deletion.purge_deleted_accounts(conn)
    # expired session rows authenticate nobody but still point at an account,
    # so they go a day after they die
    sessions.purge_expired_sessions(conn)
    # a recovery message is free text and may name a person: it goes thirty
    # days after the owner marked it resolved
    recovery_messages.purge_resolved(conn, clock=clock)
    conn.commit()
