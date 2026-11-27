"""The owner's Ranked screens over HTTP: prize approvals, accounts, Quiz Code
recoveries, recovery messages, tie-break selections and flags.

Same /api/ranked prefix as ranked.py. Every route here checks the owner
itself, and the rule it carries re-checks inside its own transaction.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.auth import eligibility, recovery, recovery_messages
from backend.auth import deletion as account_deletion
from backend.auth.deletion_list import DeletionListUnavailable
from backend.routers import deps
from backend.routers.deps import current_account, get_db, require_owner, require_recent_reauth, unprocessable, utc
from backend.ranked import seasons
from backend.ranked import tiebreaks as ranked_tiebreaks
from backend.ranked import flags as ranked_flags
from backend.text_input import PlainText

router = APIRouter(prefix="/api/ranked", tags=["ranked"])


# Prize eligibility, the owner's own screen (#11). The rule lives in
# backend/auth/eligibility.py; these three only carry it over HTTP. There
# is no player list, no points endpoint and no history here, because the
# owner was never granted those: what is missing is missing on purpose.
class ApproveRequest(BaseModel):
    tag: str
    roster_reference: PlainText


def _approval_json(approval) -> dict:
    return {
        "account_id": str(approval.account_id),
        "username": approval.username,
        "tag": approval.tag,
        "roster_reference": approval.roster_reference,
        "established_at": utc(approval.established_at),
    }


@router.get("/owner/approvals")
def list_approvals(account: dict = Depends(current_account), conn=Depends(get_db)):
    try:
        approvals = eligibility.approvals(conn, account["id"])
    except eligibility.EligibilityError as error:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=error.reason
        ) from None
    return {
        "approvals_open": seasons.approvals_open(conn, deps.CLOCK.now()),
        "approvals": [_approval_json(approval) for approval in approvals],
    }


@router.post("/owner/approvals", status_code=status.HTTP_201_CREATED)
def approve_sorter(
    request: Request,
    payload: ApproveRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    require_owner(account)
    require_recent_reauth(request, conn)
    try:
        target_id = eligibility.account_id_for_tag(conn, payload.tag)
        approval = eligibility.approve(
            conn,
            account["id"],
            target_id,
            payload.roster_reference,
            clock=deps.CLOCK,
        )
    except eligibility.EligibilityError as error:
        # 403 only when the caller is not the owner; everything else is a
        # refusal of this particular approval, not of the person asking.
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return _approval_json(approval)


@router.delete("/owner/approvals/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def withdraw_approval(
    request: Request,
    account_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    require_owner(account)
    require_recent_reauth(request, conn)
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


# Deleting an account that should not exist (#271): tests, duplicates,
# people who left. The rule lives in backend/auth/deletion.py. The list is
# the one place the owner sees accounts at all, and it carries nothing of a
# player's record.
class OwnerDeleteRequest(BaseModel):
    confirm_tag: str = ""


@router.get("/owner/accounts")
def list_accounts(account: dict = Depends(current_account), conn=Depends(get_db)):
    try:
        rows = account_deletion.accounts_for_owner(conn, account["id"])
    except account_deletion.NotOwnerError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
    return {
        "accounts": [
            {
                "account_id": str(row["account_id"]),
                "username": row["username"],
                "tag": row["tag"],
                "created_at": utc(row["created_at"]),
                "is_owner": row["is_owner"],
                "approved": row["approved"],
                "has_played": row["has_played"],
            }
            for row in rows
        ]
    }


@router.post("/owner/accounts/{account_id}/delete", status_code=status.HTTP_202_ACCEPTED)
def delete_account_as_owner(
    request: Request,
    account_id: str,
    payload: OwnerDeleteRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Delete another account. Irreversible, so: owner only, the login ID
    entered again recently, and that account's tag typed to confirm."""
    require_owner(account)
    require_recent_reauth(request, conn)
    try:
        target = UUID(account_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        deleted = account_deletion.delete_by_owner(
            conn, account["id"], target, payload.confirm_tag, clock=deps.CLOCK
        )
    except account_deletion.NotOwnerError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
    except account_deletion.NoSuchAccountError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    except account_deletion.OwnerAccountError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The owner account cannot be deleted",
        ) from None
    except account_deletion.WrongTagError:
        raise unprocessable("That tag does not match this account. Nothing was changed.") from None
    except DeletionListUnavailable:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deletion is temporarily unavailable. Nothing was changed; try again shortly.",
        ) from None
    return {"status": "accepted", "username": deleted["username"], "tag": deleted["tag"]}


# Access recovery (#11, box 2). The rule lives in backend/auth/recovery.py:
# these only carry it over HTTP. Opening a recovery grants nothing, and
# handing one over is refused unless a roster link older than the request
# exists, so the two steps are separate calls rather than one.
class RecoveryOpenRequest(BaseModel):
    tag: str


@router.get("/owner/recoveries")
def list_recoveries(account: dict = Depends(current_account), conn=Depends(get_db)):
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
                "opened_at": utc(row["opened_at"]),
                "completed_at": None if row["completed_at"] is None
                else utc(row["completed_at"]),
            }
            for row in rows
        ]
    }


@router.post("/owner/recoveries", status_code=status.HTTP_201_CREATED)
def open_recovery(
    payload: RecoveryOpenRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    try:
        request = recovery.open_request(conn, account["id"], payload.tag, clock=deps.CLOCK)
    except recovery.RecoveryError as error:
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return {
        "id": str(request.id),
        "username": request.username,
        "tag": request.tag,
        "opened_at": utc(request.opened_at),
    }


@router.post("/owner/recoveries/{request_id}/handover")
def hand_over_recovery(
    request: Request,
    request_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Issue the new login ID. The response carries it once; the server
    keeps only its hash, so nothing can read it back afterwards."""
    require_owner(account)
    require_recent_reauth(request, conn)
    try:
        handover = recovery.hand_over(
            conn, account["id"], UUID(request_id), clock=deps.CLOCK
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Not found"
        ) from None
    except recovery.RecoveryError as error:
        code = (
            status.HTTP_403_FORBIDDEN
            if error.reason.startswith("Only the owner")
            else status.HTTP_422_UNPROCESSABLE_CONTENT
        )
        raise HTTPException(status_code=code, detail=error.reason) from None
    conn.commit()
    return {
        "login_id": handover.login_id,
        "username": handover.username,
        "tag": handover.tag,
    }


# Recovery messages (#251): what a locked-out player typed on the sign-in
# screen. The rule lives in backend/auth/recovery_messages.py. No recent
# reauthentication here, unlike the recovery itself: reading a message and
# marking it resolved reveal no secret and grant nobody access.
@router.get("/owner/recovery-messages")
def list_recovery_messages(
    account: dict = Depends(current_account), conn=Depends(get_db)
):
    require_owner(account)
    try:
        rows = recovery_messages.list_messages(conn, account["id"])
    except recovery_messages.NotOwner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        ) from None
    return {
        "open": sum(1 for row in rows if row["resolved_at"] is None),
        "messages": [
            {
                "id": str(row["id"]),
                "body": row["body"],
                "created_at": utc(row["created_at"]),
                "resolved_at": None if row["resolved_at"] is None
                else utc(row["resolved_at"]),
            }
            for row in rows
        ],
    }


@router.post(
    "/owner/recovery-messages/{message_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
)
def resolve_recovery_message(
    message_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    require_owner(account)
    try:
        found = recovery_messages.resolve(
            conn, account["id"], UUID(message_id), clock=deps.CLOCK
        )
    except ValueError:
        found = False
    except recovery_messages.NotOwner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        ) from None
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    conn.commit()
    return None


# Prize selection (#24, slice 6). Where every "wait for the owner" lands.
# Recording a choice is a prize action, so it needs the login ID
# re-entered on this device within five minutes, like approvals.
class SelectionRequest(BaseModel):
    account_ids: list[str]


@router.get("/owner/selections")
def list_selections(account: dict = Depends(current_account), conn=Depends(get_db)):
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
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    require_owner(account)
    require_recent_reauth(request, conn)
    try:
        chosen = [UUID(a) for a in payload.account_ids]
        UUID(group_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        ranked_tiebreaks.record_selection(conn, account["id"], group_id, chosen, clock=deps.CLOCK)
    except ranked_tiebreaks.SelectionError as error:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=error.reason
        ) from None
    return {"group_id": group_id, "recorded": True}


class CloseFlagRequest(BaseModel):
    outcome: Literal["network_instability", "insufficient_evidence"]


@router.get("/flags")
def list_flags(account: dict = Depends(current_account), conn=Depends(get_db)):
    """Open connection review flags, for the owner only. A flag is an
    instability signal, not proof of cheating; no player sees flags,
    including their own."""
    require_owner(account)
    return [
        {
            "attempt_id": str(flag["attempt_id"]),
            "username": flag["username"],
            "tag": flag["tag"],
            "first_loss_at": utc(flag["first_loss_at"]),
            "last_loss_at": utc(flag["last_loss_at"]),
            "flagged_at": utc(flag["flagged_at"]),
            "events": [
                {"kind": event["kind"], "occurred_at": utc(event["occurred_at"])}
                for event in flag["events"]
            ],
        }
        for flag in ranked_flags.open_flags(conn)
    ]


@router.post("/flags/{attempt_id}/close")
def close_flag(
    attempt_id: str,
    payload: CloseFlagRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Close a reviewed flag. Changes nothing about the player's points or
    access."""
    require_owner(account)
    try:
        UUID(attempt_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        outcome = ranked_flags.close_flag(conn, attempt_id, payload.outcome, clock=deps.CLOCK)
    except ranked_flags.FlagNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    return {"attempt_id": attempt_id, "outcome": outcome}
