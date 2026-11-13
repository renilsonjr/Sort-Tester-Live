"""Thin HTTP layer over the ranked attempt engine.

Adapts HTTP requests to `backend.ranked.engine`. It resolves the current
account from the session cookie, enforces that an attempt belongs to that
account, and translates engine errors to status codes. It holds no game logic
of its own. Not wired into the published static site; the backend is unhosted.
"""
from contextlib import contextmanager
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.auth.service import get_account_by_session
from backend.db import migrate, settings
from backend.ranked import capability, engine, settlement
from backend.ranked.clock import system_clock
from backend.ranked_bank.catalog import load_reviewed_bank

router = APIRouter(prefix="/api/ranked", tags=["ranked"])

CAPABILITY_HEADER = "X-Attempt-Capability"

_CLOCK = system_clock()
_bank = None


def _reviewed_bank():
    # the pinned bank is immutable; load it once and reuse
    global _bank
    if _bank is None:
        _bank = load_reviewed_bank()
    return _bank


@contextmanager
def _db_connection():
    conn = migrate.connect(settings.app_database_url())
    try:
        yield conn
    finally:
        conn.close()


def get_db():
    with _db_connection() as conn:
        yield conn


def _current_account(request: Request):
    raw_token = request.cookies.get("sort_tester_session")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    with _db_connection() as conn:
        account = get_account_by_session(conn, raw_token)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return account


def _require_own_attempt(conn, attempt_id: str, account_id) -> None:
    """Admit only the account that owns the attempt (404 otherwise)."""
    try:
        UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    row = migrate.fetch_one(
        conn, "SELECT account_id FROM attempts WHERE id = %s", (attempt_id,)
    )
    if row is None or row["account_id"] != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


def _require_owned_attempt(conn, attempt_id: str, account_id, request: Request) -> None:
    """Admit only the account that owns the attempt, from the page that
    started it. Refusal happens before any engine call, so a refused request
    never counts as a heartbeat or a return within grace."""
    _require_own_attempt(conn, attempt_id, account_id)
    # the capability travels only in this header: never a cookie, URL or body
    token = request.headers.get(CAPABILITY_HEADER)
    if not capability.matches(conn, attempt_id, token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not the original page"
        )


@contextmanager
def _gone_when_ended(conn, attempt_id):
    # an attempt that has ended (completed or disconnected) answers 410 Gone
    try:
        yield
    except engine.AttemptEndedError:
        # score at once: an attempt found ended is settled before we answer
        _settle(conn, attempt_id)
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Attempt ended") from None


def _settle(conn, attempt_id) -> dict:
    """Apply the ended attempt's points (idempotent) and describe the result.

    The engine ends an attempt; settlement, a separate transaction, applies
    it. If the process stops between the two, the next call here, the next
    start by the account or the sweep settles it: never lost, never twice.
    """
    result = settlement.settle_attempt(conn, attempt_id, clock=_CLOCK)
    row = migrate.fetch_one(
        conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
    )
    return {
        "final_outcome": row["final_outcome"],
        "raw_score": result.raw_score,
        "adjustment": result.adjustment,
        "points_before": result.points_before,
        "points_after": result.points_after,
        "badge_before": result.badge_before,
        "badge_after": result.badge_after,
    }


class AnswerRequest(BaseModel):
    seq: int
    choice: str


class StartRequest(BaseModel):
    # the kind of attempt the player explicitly chose; never inferred here
    mode: Literal["normal", "promotion"] = "normal"


@router.get("/entry")
def entry(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Which kind of attempt the account may start now. Read-only: opening
    this information starts no attempt and no timer."""
    entry_status = engine.entry_status(conn, account["id"])
    return {
        "points": entry_status.points,
        "badge": entry_status.badge,
        "mode": entry_status.mode,
    }


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
def start(
    payload: StartRequest | None = None,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    mode = payload.mode if payload is not None else "normal"
    # issued once, here; the page holds it in memory and the server keeps
    # only its hash
    token = capability.new_token()
    # score at once: an attempt this account walked away from is closed and
    # settled first, so it does not block the new one
    engine.expire_stale_attempts(conn, clock=_CLOCK, account_id=account["id"])
    settlement.settle_pending(conn, clock=_CLOCK, account_id=account["id"])
    try:
        attempt_id = engine.start_attempt(
            conn, account["id"], clock=_CLOCK, bank=_reviewed_bank(),
            page_capability=token, mode=mode,
        )
    except engine.PromotionRequiredError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Promotion required"
        ) from None
    except engine.PromotionNotAvailableError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Promotion not available"
        ) from None
    except engine.NoOpenSeasonError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No open season") from None
    except engine.ActiveAttemptExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Active attempt exists"
        ) from None
    return {"attempt_id": str(attempt_id), "capability": token, "mode": mode}


@router.get("/attempts/{attempt_id}/current")
def current(request: Request, attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    with _gone_when_ended(conn, attempt_id):
        view = engine.current_question(
            conn, attempt_id, clock=_CLOCK, bank=_reviewed_bank()
        )
    if view is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return {
        "seq": view.seq,
        "deadline_at": view.deadline_at.isoformat(),
        "prompt_en": view.prompt_en,
        "prompt_es": view.prompt_es,
    }


@router.post("/attempts/{attempt_id}/answer")
def answer(
    request: Request,
    attempt_id: str,
    payload: AnswerRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    try:
        with _gone_when_ended(conn, attempt_id):
            result = engine.submit_answer(
                conn, attempt_id, payload.seq, payload.choice,
                clock=_CLOCK, bank=_reviewed_bank(),
            )
    except engine.AnswerRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    body = {
        "seq": result.seq,
        "correct": result.correct,
        "outcome": result.outcome,
        "finished": result.finished,
    }
    if result.finished:
        # the final answer ended the attempt: apply and report its points now
        body["result"] = _settle(conn, attempt_id)
    return body


@router.post("/attempts/{attempt_id}/advance")
def advance(request: Request, attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    try:
        with _gone_when_ended(conn, attempt_id):
            result = engine.advance(conn, attempt_id, clock=_CLOCK)
    except engine.NotAnsweredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return {"next_seq": result.next_seq}


@router.post("/attempts/{attempt_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(request: Request, attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    with _gone_when_ended(conn, attempt_id):
        engine.heartbeat(conn, attempt_id, clock=_CLOCK)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/attempts/{attempt_id}/quit")
def quit_attempt(request: Request, attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    # never 410: a retried Quit must get the same answer as the first one
    outcome = engine.quit_attempt(conn, attempt_id, clock=_CLOCK)
    return {"final_outcome": outcome, "result": _settle(conn, attempt_id)}


@router.get("/attempts/{attempt_id}/result")
def result(attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    """The result of an ended attempt. History: it needs the session and
    ownership but not the page capability, and it changes nothing a later
    settlement would not."""
    _require_own_attempt(conn, attempt_id, account["id"])
    # an attempt nobody is calling may have ended by the clock already
    engine.expire_stale_attempts(conn, clock=_CLOCK, account_id=account["id"])
    try:
        return _settle(conn, attempt_id)
    except settlement.AttemptNotEndedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt still running"
        ) from None
