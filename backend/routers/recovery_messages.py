"""The one thing a locked-out player can do: leave the owner a message (#251).

Kept off ``auth.router`` on purpose. That router sweeps pending deletions
before every handler, which is database work; this route is anonymous, so
its limiter is checked before the database is touched at all.
"""
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.auth import recovery_messages
from backend.auth.rate_limit import _client_key
from backend.db import pool, settings
from backend.ranked.clock import system_clock

router = APIRouter(prefix="/api/auth", tags=["auth"])

_CLOCK = system_clock()

TOO_MANY = "Too many messages; find the owner in person."


class RecoveryMessageRequest(BaseModel):
    # A ceiling on what is parsed at all. The real rule (500 after
    # trimming) lives in backend/auth/recovery_messages.py.
    message: str = Field(max_length=4000)


@router.post("/recovery-messages", status_code=status.HTTP_201_CREATED)
def leave_recovery_message(request: Request, payload: RecoveryMessageRequest):
    limiter = request.app.state.recovery_message_limiter
    client = _client_key(request)
    if not limiter.is_allowed(client):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY)
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
    with pool.checkout() as conn:
        try:
            recovery_messages.leave_message(conn, payload.message, clock=_CLOCK)
        except recovery_messages.MessageRefused as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.reason
            ) from None
        except recovery_messages.InboxFull:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY
            ) from None
        conn.commit()
    # Only a stored message counts, as with sign-ups.
    limiter.record(client)
    # Nothing in the body: no id, no echo, the same bytes for every message.
    return Response(status_code=status.HTTP_201_CREATED)
