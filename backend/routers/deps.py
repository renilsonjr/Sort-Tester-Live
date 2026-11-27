"""What every router needs before it can do its own work.

One place for the three things each route file used to define for itself:
a pooled connection, the signed-in account behind the session cookie, and
the pinned question bank. A router imports these names; it does not reach
into another router for them.

Nothing here knows about a season, a duel or a ticket. The per-request
game clock (closing a season, a tie-break round) stays with the ranked
router, which is the only one that owns it.
"""
from contextlib import contextmanager

from fastapi import HTTPException, Request, status

from backend.auth.service import get_account_by_session
from backend.db import pool, settings
from backend.ranked_bank.catalog import load_reviewed_bank

_bank = None


def reviewed_bank():
    # the pinned bank is immutable; load it once and reuse
    global _bank
    if _bank is None:
        _bank = load_reviewed_bank()
    return _bank


@contextmanager
def db_connection():
    """One pooled connection for this request (audit M-5).

    Opening a connection per request cost a connect to Postgres each time
    and had no ceiling; the pool reuses a capped set and makes a burst
    wait. Commits are still the caller's own: see backend/db/pool.py for
    why that was kept rather than folded into the checkout.
    """
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
    with pool.checkout() as conn:
        yield conn


def get_plain_db():
    """A connection and nothing else: no sweep, no game clock.

    For a route that must not drive the locks a season close and a
    tie-break round need. In front of a session that matters most: an
    anonymous request that ran the sweep chain could stall the ranked
    path for people who are playing (audit M-1).
    """
    with db_connection() as conn:
        yield conn


def current_account(request: Request):
    raw_token = request.cookies.get("sort_tester_session")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    with db_connection() as conn:
        account = get_account_by_session(conn, raw_token)
        # the idle refresh and the idle revocation are writes: without this
        # the close rolls both back, so last_seen_at never leaves the login
        # time and every session dies one idle window later (audit H-1)
        conn.commit()
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return account
