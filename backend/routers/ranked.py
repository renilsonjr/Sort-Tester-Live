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

from backend.auth import eligibility, reauth, recovery
from backend.auth.deletion import purge_deleted_accounts
from backend.auth.service import get_account_by_session
from backend.db import migrate, settings
from backend.ranked import capability, engine, launch, season_close, seasons, settlement
from backend.ranked import standings as ranked_standings
from backend.ranked import tiebreaks as ranked_tiebreaks
from backend.ranked import history as ranked_history
from backend.ranked import flags as ranked_flags
from backend.support import retention as support_retention
from backend.support import tickets as support_tickets
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
        # and a tie-break round closes at its own deadline the same way:
        # score it, place its players, open the next round if one is due
        ranked_tiebreaks.close_due_rounds(conn, clock=_CLOCK, bank=_reviewed_bank())
        # same idea for retention: a closed ticket's description goes fifteen
        # days after its own closure, and an attempt's shared connection log
        # goes fifteen days after the last case on it closes (#26)
        support_retention.purge_due_cases(conn, clock=_CLOCK)
        # and for accepted account deletions (#47)
        purge_deleted_accounts(conn)
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


@router.post("/tiebreak/rounds/{round_id}/attempts", status_code=status.HTTP_201_CREATED)
def start_tiebreak(
    round_id: str,
    account: dict = Depends(_current_account),
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
            conn, account["id"], round_id, clock=_CLOCK, page_capability=token
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
    if result.finished and not engine.is_tiebreak_attempt(conn, attempt_id):
        # the final answer ended the attempt: apply and report its points now.
        # A tie-break has no points to apply and reveals nothing until its
        # round closes (settled Q4), so it gets the bare acknowledgement.
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


@router.get("/leaderboard")
def leaderboard(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """The official standings. Login is required to see them (settled Q5).

    Read-only, and it carries only what the approved screen shows: place,
    username, tag, points and badge. ``your_place`` is null for a player
    the competition does not include, which is the "no position" state the
    mockup draws; their own points and badge are unaffected and stay on
    their profile.

    During Pre-Season there is no official season to rank, so the board is
    empty rather than invented. ``points_final`` repeats what /season says:
    once the season is frozen the points no longer move, while prize
    places stay provisional until the tie-breaks in #24 resolve them.
    """
    launch_fact = seasons.official_launch(conn)
    if launch_fact is None:
        return {
            "season_label": None,
            "points_final": False,
            "rows": [],
            "your_place": None,
            "eligible": False,
        }
    rows = ranked_standings.standings(conn, launch_fact.season_id)
    current = seasons.current_season_status(conn, _CLOCK.now())
    place = ranked_standings.place_of(rows, account["id"])
    return {
        "season_label": launch_fact.label,
        "points_final": current is not None and current.status == "frozen",
        "rows": [
            {
                "place": row.place,
                "username": row.username,
                "tag": row.tag,
                "points": row.points,
                "badge": row.badge,
                "tied": row.tied,
                "you": row.account_id == account["id"],
            }
            for row in rows
        ],
        "your_place": place,
        "eligible": place is not None,
    }


# Recent login-ID reauthentication (#11 box 5). The owner's eligibility
# and recovery actions need the login ID re-entered on this session within
# five minutes. 428 rather than 401 or 403 on purpose: the session is
# valid and the owner is allowed, a precondition is simply missing, and the
# page answers 428 by asking for the login ID instead of signing out.
REAUTH_DETAIL = (
    "Re-enter your login ID to continue. It stays confirmed on this device"
    " for five minutes."
)


def _require_recent_reauth(request: Request, conn) -> None:
    raw_token = request.cookies.get("sort_tester_session") or ""
    try:
        reauth.require_recent(conn, raw_token, clock=_CLOCK)
    except reauth.ReauthRequired:
        raise HTTPException(
            status_code=status.HTTP_428_PRECONDITION_REQUIRED, detail=REAUTH_DETAIL
        ) from None


# Prize eligibility, the owner's own screen (#11). The rule lives in
# backend/auth/eligibility.py; these three only carry it over HTTP. There
# is no player list, no points endpoint and no history here, because the
# owner was never granted those: what is missing is missing on purpose.
class ApproveRequest(BaseModel):
    tag: str
    roster_reference: str


def _approval_json(approval) -> dict:
    return {
        "account_id": str(approval.account_id),
        "username": approval.username,
        "tag": approval.tag,
        "roster_reference": approval.roster_reference,
        "established_at": _utc(approval.established_at),
    }


@router.get("/owner/approvals")
def list_approvals(account: dict = Depends(_current_account), conn=Depends(get_db)):
    try:
        approvals = eligibility.approvals(conn, account["id"])
    except eligibility.EligibilityError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=error.reason
        ) from None
    return {
        "approvals_open": seasons.approvals_open(conn, _CLOCK.now()),
        "approvals": [_approval_json(approval) for approval in approvals],
    }


@router.post("/owner/approvals", status_code=status.HTTP_201_CREATED)
def approve_sorter(
    request: Request,
    payload: ApproveRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owner(account)
    _require_recent_reauth(request, conn)
    try:
        target_id = eligibility.account_id_for_tag(conn, payload.tag)
        approval = eligibility.approve(
            conn,
            account["id"],
            target_id,
            payload.roster_reference,
            clock=_CLOCK,
        )
    except eligibility.EligibilityError as error:
        # 403 only when the caller is not the owner; everything else is a
        # refusal of this particular approval, not of the person asking.
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return _approval_json(approval)


@router.delete("/owner/approvals/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_approval(
    request: Request,
    account_id: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owner(account)
    _require_recent_reauth(request, conn)
    try:
        eligibility.withdraw(conn, account["id"], UUID(account_id))
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None
    except eligibility.EligibilityError as error:
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_404_NOT_FOUND
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return None


# Access recovery (#11, box 2). The rule lives in backend/auth/recovery.py:
# these only carry it over HTTP. Opening a recovery grants nothing, and
# handing one over is refused unless a roster link older than the request
# exists, so the two steps are separate calls rather than one.
class RecoveryOpenRequest(BaseModel):
    tag: str


@router.get("/owner/recoveries")
def list_recoveries(account: dict = Depends(_current_account), conn=Depends(get_db)):
    try:
        rows = recovery.recent_requests(conn, account["id"])
    except recovery.RecoveryError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=error.reason
        ) from None
    return {
        "recoveries": [
            {
                "id": str(row["id"]),
                "username": row["username"],
                "tag": row["tag"],
                "opened_at": _utc(row["opened_at"]),
                "completed_at": None if row["completed_at"] is None
                else _utc(row["completed_at"]),
            }
            for row in rows
        ]
    }


@router.post("/owner/recoveries", status_code=status.HTTP_201_CREATED)
def open_recovery(
    payload: RecoveryOpenRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    try:
        request = recovery.open_request(conn, account["id"], payload.tag, clock=_CLOCK)
    except recovery.RecoveryError as error:
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return {
        "id": str(request.id),
        "username": request.username,
        "tag": request.tag,
        "opened_at": _utc(request.opened_at),
    }


@router.post("/owner/recoveries/{request_id}/handover")
def hand_over_recovery(
    request: Request,
    request_id: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Issue the new login ID. The response carries it once; the server
    keeps only its hash, so nothing can read it back afterwards."""
    _require_owner(account)
    _require_recent_reauth(request, conn)
    try:
        handover = recovery.hand_over(
            conn, account["id"], UUID(request_id), clock=_CLOCK
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None
    except recovery.RecoveryError as error:
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_ENTITY
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return {
        "login_id": handover.login_id,
        "username": handover.username,
        "tag": handover.tag,
    }


# Prize selection (#24, slice 6). Where every "wait for the owner" lands.
# Recording a choice is a prize action, so it needs the login ID
# re-entered on this device within five minutes, like approvals.
class SelectionRequest(BaseModel):
    account_ids: list[str]


@router.get("/owner/selections")
def list_selections(account: dict = Depends(_current_account), conn=Depends(get_db)):
    try:
        cases = ranked_tiebreaks.selection_cases(conn, account["id"])
    except ranked_tiebreaks.SelectionError as error:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=error.reason) from None
    return {
        "cases": [
            {
                "group_id": str(case["group_id"]),
                "tied_points": case["tied_points"],
                "hats": case["hats"],
                "players": [
                    {
                        "account_id": str(p["id"]),
                        "username": p["username"],
                        "tag": p["tag"],
                        "history": [
                            {"round": h["round_number"], "outcome": h["outcome"], "score": h["score"]}
                            for h in p["history"]
                        ],
                    }
                    for p in case["players"]
                ],
            }
            for case in cases
        ]
    }


@router.post("/owner/selections/{group_id}")
def record_selection(
    request: Request,
    group_id: str,
    payload: SelectionRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owner(account)
    _require_recent_reauth(request, conn)
    try:
        chosen = [UUID(a) for a in payload.account_ids]
        UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        ranked_tiebreaks.record_selection(conn, account["id"], group_id, chosen, clock=_CLOCK)
    except ranked_tiebreaks.SelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.reason
        ) from None
    return {"group_id": group_id, "recorded": True}


class CloseFlagRequest(BaseModel):
    outcome: Literal["network_instability", "insufficient_evidence"]


def _require_owner(account: dict) -> None:
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


def _utc(moment) -> str:
    return moment.astimezone(timezone.utc).isoformat()


@router.get("/season/notice")
def season_notice(conn=Depends(get_db)):
    """The season-start notice, for anyone — signed in or not.

    The approved home page shows a small callout once the official season
    has started, carrying its start date, and **guests see it too**
    (Decision 15, placement settled 2026-11-15). The authenticated
    ``/season`` endpoint cannot serve that, so this one exists.

    It carries nothing about any player and nothing that is not already
    public once the season opens: whether it has started, its label, and
    when it started and ends. Before the official launch it answers
    ``started: false`` and no dates, because inventing one is forbidden.
    """
    fact = seasons.official_launch(conn)
    if fact is None:
        return {"started": False, "label": None, "started_at": None, "closes_at": None}
    current = seasons.current_season_status(conn, _CLOCK.now())
    closes_at = current.closes_at if current else None
    return {
        "started": True,
        "label": fact.label,
        "started_at": _utc(fact.launched_at),
        "closes_at": None if closes_at is None else _utc(closes_at),
    }


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


# --- Support tickets (issue #26) -------------------------------------------
#
# Support holds Tickets and nothing else, and only a player request creates
# one. Every player endpoint here reads and writes through the account in the
# session, so there is no form of these calls that reaches another player's
# case.


class CreateTicketRequest(BaseModel):
    attempt_id: str
    description: str | None = None


class CloseTicketRequest(BaseModel):
    outcome: Literal["network_instability", "insufficient_evidence"]


def _ticket_json(conn, ticket: dict) -> dict:
    """One ticket as the Support screens need it.

    A closed ticket carries either the date its description and the shared
    connection log are deleted, or the fact that an open linked case is
    holding that evidence. Those are the two states the approved screens
    show, and the second one never says which case or whose.
    """
    due = support_retention.shared_log_deletion_date(conn, ticket["attempt_id"])
    return {
        "id": str(ticket["id"]),
        "attempt_id": str(ticket["attempt_id"]),
        "description": ticket["description"],
        "opened_at": _utc(ticket["opened_at"]),
        "closed_at": _utc(ticket["closed_at"]) if ticket["closed_at"] else None,
        "outcome": ticket["closed_outcome"],
        "evidence_deleted_at": _utc(due) if due else None,
        "evidence_held_by_open_case": ticket["closed_at"] is not None and due is None,
    }


@router.get("/support/tickets")
def list_tickets(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """This player's own tickets, newest first. Never anybody else's."""
    return [
        _ticket_json(conn, ticket)
        for ticket in support_tickets.tickets_for(conn, account["id"])
    ]


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: CreateTicketRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Open a ticket about one of this player's own attempts.

    A description is optional. An attempt that is not this player's and an
    attempt that does not exist are refused identically: whether an attempt
    exists is not something one player learns about another.
    """
    try:
        UUID(payload.attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        ticket_id = support_tickets.open_ticket(
            conn, account["id"], payload.attempt_id, description=payload.description
        )
    except support_tickets.AttemptNotYoursError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except support_tickets.TicketAlreadyOpenError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A ticket about this attempt is already open",
        ) from None
    conn.commit()
    ticket = support_tickets.ticket_for(conn, account["id"], ticket_id)
    return _ticket_json(conn, ticket)


@router.get("/support/tickets/{ticket_id}")
def read_ticket(
    ticket_id: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """One of this player's own tickets.

    Somebody else's ticket is Not found, the same answer as a ticket that
    does not exist.
    """
    try:
        UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    ticket = support_tickets.ticket_for(conn, account["id"], ticket_id)
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return _ticket_json(conn, ticket)


@router.get("/support/review")
def review_queue(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Open tickets for an authorized reviewer.

    Returns the player's display identity, the attempt, what they wrote and
    that attempt's connection events. Nothing else about them.
    """
    try:
        rows = support_tickets.open_tickets_for_review(conn, account["id"])
    except support_tickets.NotAuthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
    return [
        {
            "id": str(row["id"]),
            "attempt_id": str(row["attempt_id"]),
            "username": row["username"],
            "tag": row["tag"],
            "description": row["description"],
            "opened_at": _utc(row["opened_at"]),
            "events": [
                {"kind": event["kind"], "occurred_at": _utc(event["occurred_at"])}
                for event in row["events"]
            ],
        }
        for row in rows
    ]


@router.post("/support/review/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    payload: CloseTicketRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Close a reviewed ticket. Changes no points and no access."""
    try:
        UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        outcome = support_tickets.close_ticket(
            conn, account["id"], ticket_id, payload.outcome, clock=_CLOCK
        )
    except support_tickets.NotAuthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
    except support_tickets.TicketNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    conn.commit()
    return {"id": ticket_id, "outcome": outcome}


@router.post("/support/review/{ticket_id}/reopen")
def reopen_ticket(
    ticket_id: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Reopen a closed ticket for follow-up, which also stops its retention
    clock: evidence an open case needs must not be deleted underneath it."""
    try:
        UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        support_tickets.reopen_ticket(conn, account["id"], ticket_id)
    except support_tickets.NotAuthorizedError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
    except support_tickets.TicketNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    conn.commit()
    return {"id": ticket_id, "reopened": True}
