"""What every router needs before it can do its own work.

One place for what each route file used to define for itself: a pooled
connection, the signed-in account behind the session cookie, the pinned
question bank, the game's clock, and the few small checks and answers
several routers give in the same words. A router imports these names; it
does not reach into another router for them.

No rule lives here. What the game does when a deadline passes is in
backend/ranked/due_work.py and what the server deletes with age is in
backend/retention.py; this module only decides that a request behind an
account runs them first.
"""
from contextlib import contextmanager
from datetime import timezone

from fastapi import HTTPException, Request, status

from backend import retention
from backend.auth import reauth
from backend.auth.service import get_account_by_session
from backend.db import pool, settings
from backend.ranked import due_work
from backend.ranked.clock import system_clock
from backend.ranked_bank.catalog import load_reviewed_bank

# The one clock the Ranked routes read. A test that needs to move time
# replaces this name.
CLOCK = system_clock()

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


def get_db(request: Request):
    """A connection for a route behind an account, with the game up to date.

    Before the route runs, whatever has come due by the clock is done
    (backend/ranked/due_work.py), on every request. Retention deletes what
    is days old, so it takes its turn at most once a minute for the whole
    process (backend/sweep_interval.py).
    """
    with db_connection() as conn:
        due_work.run(conn, clock=CLOCK, bank=reviewed_bank())
        if request.app.state.retention_interval.due():
            retention.sweep(conn, clock=CLOCK)
        yield conn


def require_owner(account: dict) -> None:
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


# Recent login-ID reauthentication (#11 box 5). The owner's eligibility
# and recovery actions need the login ID re-entered on this session within
# five minutes. 428 rather than 401 or 403 on purpose: the session is
# valid and the owner is allowed, a precondition is simply missing, and the
# page answers 428 by asking for the login ID instead of signing out.
REAUTH_DETAIL = (
    "Re-enter your Quiz Code to continue. It stays confirmed on this device"
    " for five minutes."
)


def require_recent_reauth(request: Request, conn) -> None:
    raw_token = request.cookies.get("sort_tester_session") or ""
    try:
        reauth.require_recent(conn, raw_token, clock=CLOCK)
    except reauth.ReauthRequired:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=REAUTH_DETAIL
        ) from None


def unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=detail)


def utc(moment) -> str:
    return moment.astimezone(timezone.utc).isoformat()
