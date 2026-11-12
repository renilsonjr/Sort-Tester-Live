"""Thin HTTP layer over the ranked attempt engine.

Adapts HTTP requests to `backend.ranked.engine`. It resolves the current
account from the session cookie, enforces that an attempt belongs to that
account, and translates engine errors to status codes. It holds no game logic
of its own. Not wired into the published static site; the backend is unhosted.
"""
from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.auth.service import get_account_by_session
from backend.db import migrate, settings
from backend.ranked import engine
from backend.ranked.clock import system_clock
from backend.ranked_bank.catalog import load_reviewed_bank

router = APIRouter(prefix="/api/ranked", tags=["ranked"])

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


def _require_owned_attempt(conn, attempt_id: str, account_id) -> None:
    try:
        UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    row = migrate.fetch_one(
        conn, "SELECT account_id FROM attempts WHERE id = %s", (attempt_id,)
    )
    if row is None or row["account_id"] != account_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")


@contextmanager
def _gone_when_ended():
    # an attempt that has ended (completed or disconnected) answers 410 Gone
    try:
        yield
    except engine.AttemptEndedError:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail="Attempt ended") from None


class AnswerRequest(BaseModel):
    seq: int
    choice: str


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
def start(account: dict = Depends(_current_account), conn=Depends(get_db)):
    try:
        attempt_id = engine.start_attempt(
            conn, account["id"], clock=_CLOCK, bank=_reviewed_bank()
        )
    except engine.NoOpenSeasonError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="No open season") from None
    except engine.ActiveAttemptExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Active attempt exists"
        ) from None
    return {"attempt_id": str(attempt_id)}


@router.get("/attempts/{attempt_id}/current")
def current(attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"])
    with _gone_when_ended():
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
    attempt_id: str,
    payload: AnswerRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owned_attempt(conn, attempt_id, account["id"])
    try:
        with _gone_when_ended():
            result = engine.submit_answer(
                conn, attempt_id, payload.seq, payload.choice,
                clock=_CLOCK, bank=_reviewed_bank(),
            )
    except engine.AnswerRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return {"seq": result.seq, "correct": result.correct, "outcome": result.outcome}


@router.post("/attempts/{attempt_id}/advance")
def advance(attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"])
    try:
        with _gone_when_ended():
            result = engine.advance(conn, attempt_id, clock=_CLOCK)
    except engine.NotAnsweredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return {"finished": result.finished, "next_seq": result.next_seq}


@router.post("/attempts/{attempt_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(attempt_id: str, account: dict = Depends(_current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"])
    with _gone_when_ended():
        engine.heartbeat(conn, attempt_id, clock=_CLOCK)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
