"""A pool of connections for the request path (audit M-5).

Every request used to open its own connection and close it again.
Connecting to Postgres is not free, and nothing capped how many a burst
could ask for: the server's own `max_connections` was the only brake, and
hitting it refuses connections to everyone, not only to whoever caused it.

This hands out a fixed set instead and makes the rest wait. Two decisions
in here are easy to get wrong in opposite directions, so both are written
down rather than left to the reader.

**Transactions stay explicit.** `psycopg_pool`'s own `pool.connection()`
helper commits when its block exits cleanly. That would have been a quiet
change of meaning for every route: today a request that writes and does
not commit discards the write, and the H-1 fix depends on a commit being
something a route *does*. Owner decision, 2026-11-17: keep writes
explicit, which is why this module borrows and returns connections by
hand instead of using that helper, and rolls back whatever is open before
giving a connection back.

**The statement timeout is part of the DSN**, not a statement run after
checkout. Set per connection it would be one more thing to forget, and a
connection that skipped it would look identical to one that did not.

Migrations and tests do not come through here: they call
`migrate.connect` directly, because a migration legitimately runs longer
than any request may and must not be cut off at five seconds.
"""
from contextlib import contextmanager

import psycopg
from psycopg.conninfo import make_conninfo
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from backend.db import entra_token
from backend.db import settings as db_settings

# Eight is a request-path number, not a tuning result: the app is a quiz
# whose queries are short, and the point of the cap is that a burst waits
# instead of exhausting the server. Raising it without watching
# pg_stat_activity moves the problem rather than solving it.
MAX_SIZE = 8

# Five seconds is far longer than any request here should take, so a query
# that reaches it is stuck rather than slow. Without it a stuck query
# holds a pooled connection for as long as it lives, and eight of those
# are the whole pool.
STATEMENT_TIMEOUT_MS = 5000

_pool: ConnectionPool | None = None


def _conninfo_with_timeout(conninfo: str) -> str:
    return make_conninfo(conninfo, options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}")


def init_pool(
    conninfo: str,
    *,
    auth_mode: str = db_settings.PASSWORD_MODE,
    token_provider=entra_token.db_access_token,
) -> None:
    """Build the pool if there is not one already.

    Idempotent on purpose: it is called at startup and defensively from
    `checkout`, and a second pool would be eight more connections that
    nothing tracks or closes.

    In managed-identity mode the connection password is a fresh Entra token
    resolved per physical connection via a callable `kwargs` (audit #84);
    the conninfo carries no password. `psycopg_pool` 3.3.3 resolves a
    callable `kwargs` on every connection attempt, so a replaced connection
    fetches a current token. Password mode is unchanged.
    """
    global _pool
    if _pool is not None:
        return
    if auth_mode == db_settings.MANAGED_IDENTITY_MODE:
        def _kwargs():
            return {"row_factory": dict_row, "password": token_provider()}
        pool_kwargs = _kwargs
    else:
        pool_kwargs = {"row_factory": dict_row}
    _pool = ConnectionPool(
        conninfo=_conninfo_with_timeout(conninfo),
        min_size=1,
        max_size=MAX_SIZE,
        kwargs=pool_kwargs,
        # A pooled connection outlives the thing at the other end of it: a
        # restarted database, a dropped idle connection, a network blip
        # between the app and a private endpoint. Without this check the
        # first request to borrow a dead connection is the one that fails,
        # for no reason it could have known. It costs a round trip per
        # checkout and buys a failure that lands on the pool instead of on
        # a player.
        check=ConnectionPool.check_connection,
        open=True,
    )


def current_pool() -> ConnectionPool:
    if _pool is None:
        raise RuntimeError("the connection pool has not been opened")
    return _pool


def close_pool() -> None:
    """Close the pool and forget it. For shutdown and for tests."""
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


@contextmanager
def checkout():
    """Borrow a connection, and return it with nothing left open.

    Commits are the caller's: this never commits for you. On the way back
    the connection is rolled back whichever way the block ended, so the
    next borrower starts outside a transaction. Without that a connection
    could go back still inside an aborted transaction, and the next
    request would fail on a statement with nothing wrong with it.
    """
    conn = current_pool().getconn()
    try:
        yield conn
    finally:
        try:
            conn.rollback()
        except psycopg.Error:
            # a connection too broken to roll back is too broken to reuse;
            # putconn with the error lets the pool discard and replace it
            current_pool().putconn(conn)
            raise
        current_pool().putconn(conn)
