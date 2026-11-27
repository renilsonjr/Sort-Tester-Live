"""Playing Ranked over HTTP: the entry screen, an attempt, a tie-break attempt.

Adapts HTTP requests to `backend.ranked.engine`. It enforces that an attempt
belongs to the signed-in account and translates engine errors to status
codes. It holds no game logic of its own.

The season and its leaderboard are in ranked_season.py, the owner's screens
in ranked_owner.py, support tickets in ranked_support.py. All four share
the /api/ranked prefix.
"""
from contextlib import contextmanager
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel

from backend.db import migrate
from backend.routers import deps
from backend.routers.deps import current_account, get_db, get_plain_db, reviewed_bank, utc
from backend.ranked import capability, engine, settlement
from backend.ranked import tiebreaks as ranked_tiebreaks
from backend.ranked import profile_stats as ranked_profile_stats

router = APIRouter(prefix="/api/ranked", tags=["ranked"])

CAPABILITY_HEADER = "X-Attempt-Capability"


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

    A tie-break is never settled -- it changes no seasonal points -- and
    reveals nothing about its score until its round closes (settled Q4).
    Every path that ends an attempt comes through here, Quit and a found-
    ended attempt included, so this is the one place that guarantees it.
    """
    if engine.is_tiebreak_attempt(conn, attempt_id):
        row = migrate.fetch_one(
            conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
        )
        conn.commit()
        return {"final_outcome": row["final_outcome"], "hidden_until_round_closes": True}
    result = settlement.settle_attempt(conn, attempt_id, clock=deps.CLOCK)
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
    # None is "the clock ran out and nothing was sent" (#428). It is not a
    # way to skip a question: submit_answer refuses it while the deadline
    # still stands, so a page whose clock is fast gets a refusal rather than
    # a wrong answer recorded against a player who never chose.
    choice: str | None = None


class StartRequest(BaseModel):
    # the kind of attempt the player explicitly chose; never inferred here
    mode: Literal["normal", "promotion"] = "normal"


@router.get("/entry")
def entry(account: dict = Depends(current_account), conn=Depends(get_db)):
    """Which kind of attempt the account may start now. Read-only: opening
    this information starts no attempt and no timer."""
    entry_status = engine.entry_status(conn, account["id"])
    return {
        "points": entry_status.points,
        "badge": entry_status.badge,
        "mode": entry_status.mode,
    }


@router.get("/profile/stats")
def profile_stats(account: dict = Depends(current_account), conn=Depends(get_plain_db)):
    """The signed-in account's Profile stats: best Ranked correct-count and
    current leaderboard place. Read-only and private to the account; opening
    it starts no attempt and reveals nothing about anyone else."""
    correct = ranked_profile_stats.best_ranked_correct(conn, account["id"])
    place = ranked_profile_stats.leaderboard_place(conn, account["id"])
    return {
        "best_ranked": None if correct is None
        else {"correct": correct, "total": ranked_profile_stats.RANKED_QUIZ_LENGTH},
        "place": place,
    }


@router.post("/attempts", status_code=status.HTTP_201_CREATED)
def start(
    payload: StartRequest | None = None,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    mode = payload.mode if payload is not None else "normal"
    # issued once, here; the page holds it in memory and the server keeps
    # only its hash
    token = capability.new_token()
    # score at once: an attempt this account walked away from is closed and
    # settled first, so it does not block the new one
    engine.expire_stale_attempts(conn, clock=deps.CLOCK, account_id=account["id"])
    settlement.settle_pending(conn, clock=deps.CLOCK, account_id=account["id"])
    try:
        attempt_id = engine.start_attempt(
            conn, account["id"], clock=deps.CLOCK, bank=reviewed_bank(),
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


@router.get("/tiebreak/mine")
def my_tiebreak(account: dict = Depends(current_account), conn=Depends(get_db)):
    """This player's own tie-break state, or ``{"tie": null}``. Their own
    round, whether they played it, and once a round has closed their own
    score and standing -- never anybody else's."""
    mine = ranked_tiebreaks.my_tiebreak(conn, account["id"])
    if mine is None:
        return {"tie": None}
    round_ = mine["round"]
    if round_ is not None:
        round_ = {
            **round_,
            "id": str(round_["id"]),
            "deadline_at": utc(round_["deadline_at"]),
            "attempt_id": None if round_["attempt_id"] is None else str(round_["attempt_id"]),
        }
    return {"tie": {**mine, "round": round_}}


@router.post("/tiebreak/rounds/{round_id}/attempts", status_code=status.HTTP_201_CREATED)
def start_tiebreak(
    round_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Start this player's one attempt in a prize tie-break round.

    Plays through the same attempt endpoints as any quiz, with the page
    capability issued here. A refusal says why in words; a player who is not
    in the round is told only that there is no such round."""
    try:
        UUID(round_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    token = capability.new_token()
    try:
        attempt_id = engine.start_tiebreak_attempt(
            conn, account["id"], round_id, clock=deps.CLOCK, page_capability=token
        )
    except engine.TiebreakEntryError as error:
        code = (
            status.HTTP_404_NOT_FOUND
            if str(error) == "There is no such tie-break round."
            else status.HTTP_409_CONFLICT
        )
        raise HTTPException(status_code=code, detail=str(error)) from None
    except engine.ActiveAttemptExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Active attempt exists"
        ) from None
    return {"attempt_id": str(attempt_id), "capability": token, "mode": "tiebreak"}


@router.get("/attempts/{attempt_id}/current")
def current(request: Request, attempt_id: str, account: dict = Depends(current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    with _gone_when_ended(conn, attempt_id):
        view = engine.current_question(
            conn, attempt_id, clock=deps.CLOCK, bank=reviewed_bank()
        )
    if view is None:
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    return {
        "seq": view.seq,
        "deadline_at": view.deadline_at.isoformat(),
        "prompt_en": view.prompt_en,
        "prompt_es": view.prompt_es,
        "service": view.service,
        "mode": view.mode,
        "routing_code": view.routing_code,
        "region_label": view.region_label,
        "named_destination": view.named_destination,
        "options": view.options,
    }


@router.post("/attempts/{attempt_id}/answer")
def answer(
    request: Request,
    attempt_id: str,
    payload: AnswerRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    try:
        with _gone_when_ended(conn, attempt_id):
            result = engine.submit_answer(
                conn, attempt_id, payload.seq, payload.choice,
                clock=deps.CLOCK, bank=reviewed_bank(),
            )
    except engine.AnswerRejectedError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    body = {
        "seq": result.seq,
        "correct": result.correct,
        "outcome": result.outcome,
        "finished": result.finished,
    }
    if result.correct_belt is not None:
        # feedback for an ordinary or promotion screen; None (and absent
        # here) for a tie-break, which reveals nothing until its round closes
        body["correct_belt"] = result.correct_belt
        body["difficulty"] = result.difficulty
        body["worth"] = result.worth
        body["explanation_en"] = result.explanation_en
        body["explanation_es"] = result.explanation_es
    if result.finished and not engine.is_tiebreak_attempt(conn, attempt_id):
        # the final answer ended the attempt: apply and report its points now.
        # A tie-break has no points to apply and reveals nothing until its
        # round closes (settled Q4), so it gets the bare acknowledgement.
        body["result"] = _settle(conn, attempt_id)
    return body


@router.post("/attempts/{attempt_id}/advance")
def advance(request: Request, attempt_id: str, account: dict = Depends(current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    try:
        with _gone_when_ended(conn, attempt_id):
            result = engine.advance(conn, attempt_id, clock=deps.CLOCK)
    except engine.NotAnsweredError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from None
    return {"next_seq": result.next_seq}


@router.post("/attempts/{attempt_id}/heartbeat", status_code=status.HTTP_204_NO_CONTENT)
def heartbeat(request: Request, attempt_id: str, account: dict = Depends(current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    with _gone_when_ended(conn, attempt_id):
        engine.heartbeat(conn, attempt_id, clock=deps.CLOCK)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/attempts/{attempt_id}/quit")
def quit_attempt(request: Request, attempt_id: str, account: dict = Depends(current_account), conn=Depends(get_db)):
    _require_owned_attempt(conn, attempt_id, account["id"], request)
    # never 410: a retried Quit must get the same answer as the first one
    outcome = engine.quit_attempt(conn, attempt_id, clock=deps.CLOCK)
    return {"final_outcome": outcome, "result": _settle(conn, attempt_id)}


@router.get("/attempts/{attempt_id}/result")
def result(attempt_id: str, account: dict = Depends(current_account), conn=Depends(get_db)):
    """The result of an ended attempt. History: it needs the session and
    ownership but not the page capability, and it changes nothing a later
    settlement would not."""
    _require_own_attempt(conn, attempt_id, account["id"])
    if engine.is_tiebreak_attempt(conn, attempt_id):
        # scores stay hidden for everyone until the round closes (settled
        # Q4); once it has, the player sees their own score and standing
        revealed = ranked_tiebreaks.revealed_result(conn, attempt_id)
        if revealed is None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tie-break results are shown when the round closes.",
            )
        return revealed
    # an attempt nobody is calling may have ended by the clock already
    engine.expire_stale_attempts(conn, clock=deps.CLOCK, account_id=account["id"])
    try:
        return _settle(conn, attempt_id)
    except settlement.AttemptNotEndedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Attempt still running"
        ) from None
