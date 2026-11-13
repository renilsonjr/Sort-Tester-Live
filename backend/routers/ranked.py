"""Thin HTTP layer over the ranked attempt engine.

Adapts HTTP requests to `backend.ranked.engine`. It resolves the current
account from the session cookie, enforces that an attempt belongs to that
account, and translates engine errors to status codes. It holds no game logic
of its own. Not wired into the published static site; the backend is unhosted.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.auth.service import get_account_by_session
from backend.db import migrate, settings
from backend.ranked import capability, engine, launch, season_close, seasons, settlement
from backend.ranked import history as ranked_history
from backend.ranked import flags as ranked_flags
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
        # The season closes by the clock, with no background timer: every
        # ranked request first finishes any season whose five-minute finishing
        # window is over (end unfinished attempts, settle, freeze). When
        # nothing is due this is a single read.
        season_close.finish_due_seasons(conn, clock=_CLOCK)
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


LAUNCH_CONFIRMATION = "LAUNCH"


class LaunchRequest(BaseModel):
    # every field is optional here so that the owner check runs before any
    # complaint about the body; the endpoint validates them itself
    label: str = ""
    confirm: str = ""
    closes_at: datetime | None = None


def _unprocessable(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=detail)


@router.post("/season/launch", status_code=status.HTTP_201_CREATED)
def launch_season(
    payload: LaunchRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Launch the official season. Irreversible: it voids unfinished
    Pre-Season attempts and resets every balance. Owner only, and only with
    the typed confirmation, so a stray or replayed request does nothing."""
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    if payload.confirm != LAUNCH_CONFIRMATION:
        raise _unprocessable("Type LAUNCH to confirm")
    if payload.closes_at is not None and payload.closes_at.tzinfo is None:
        raise _unprocessable("closes_at needs a time zone")
    options = {} if payload.closes_at is None else {"closes_at": payload.closes_at}
    try:
        season_id = launch.launch_official_season(
            conn, label=payload.label, clock=_CLOCK, **options
        )
    except launch.InvalidLaunchError as exc:
        raise _unprocessable(str(exc)) from None
    except launch.AlreadyLaunchedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already launched"
        ) from None
    except launch.NoPreSeasonError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No Pre-Season to launch from"
        ) from None
    row = migrate.fetch_one(
        conn, "SELECT label, closes_at FROM seasons WHERE id = %s", (season_id,)
    )
    return {
        "season_id": str(season_id),
        "label": row["label"],
        "closes_at": row["closes_at"].astimezone(timezone.utc).isoformat(),
    }


@router.get("/history")
def history(
    phase: Literal["pre_season", "official"] | None = None,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """The signed-in account's own scored attempts, newest first. Private to
    the account: the request cannot name another account, and the owner gets
    no exception."""
    entries = ranked_history.account_history(conn, account["id"], phase)
    return [
        {
            "attempt_id": str(entry["attempt_id"]),
            "phase": entry["phase"],
            "label": entry["label"],
            "mode": entry["mode"],
            "final_outcome": entry["final_outcome"],
            "raw_score": entry["raw_score"],
            "adjustment": entry["adjustment"],
            "points_before": entry["points_before"],
            "points_after": entry["points_after"],
            "badge_before": entry["badge_before"],
            "badge_after": entry["badge_after"],
            "settled_at": entry["settled_at"].astimezone(timezone.utc).isoformat(),
        }
        for entry in entries
    ]


@router.get("/season")
def season(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Where the current season is in its life. Read-only. ``points_final``
    is true once the season is frozen; prize standings stay provisional
    after that until they are finalized elsewhere."""
    current = seasons.current_season_status(conn, _CLOCK.now())
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No season")
    closes_at = current.closes_at
    return {
        "season_id": str(current.season_id),
        "phase": current.phase,
        "label": current.label,
        "status": current.status,
        "closes_at": None if closes_at is None
        else closes_at.astimezone(timezone.utc).isoformat(),
        "points_final": current.status == "frozen",
        "approvals_open": current.approvals_open,
    }


class CloseFlagRequest(BaseModel):
    outcome: Literal["network_instability", "insufficient_evidence"]


def _require_owner(account: dict) -> None:
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _utc(moment) -> str:
    return moment.astimezone(timezone.utc).isoformat()


@router.get("/flags")
def list_flags(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Open connection review flags, for the owner only. A flag is an
    instability signal, not proof of cheating; no player sees flags,
    including their own."""
    _require_owner(account)
    return [
        {
            "attempt_id": str(flag["attempt_id"]),
            "username": flag["username"],
            "tag": flag["tag"],
            "first_loss_at": _utc(flag["first_loss_at"]),
            "last_loss_at": _utc(flag["last_loss_at"]),
            "flagged_at": _utc(flag["flagged_at"]),
            "events": [
                {"kind": event["kind"], "occurred_at": _utc(event["occurred_at"])}
                for event in flag["events"]
            ],
        }
        for flag in ranked_flags.open_flags(conn)
    ]


@router.post("/flags/{attempt_id}/close")
def close_flag(
    attempt_id: str,
    payload: CloseFlagRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Close a reviewed flag. Changes nothing about the player's points or
    access."""
    _require_owner(account)
    try:
        UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        outcome = ranked_flags.close_flag(conn, attempt_id, payload.outcome, clock=_CLOCK)
    except ranked_flags.FlagNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    return {"attempt_id": attempt_id, "outcome": outcome}
