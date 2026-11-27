"""Support tickets over HTTP (issue #26): a player's own cases and the
owner's review queue.

Same /api/ranked prefix as ranked.py; the rules live in backend/support.
"""
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.routers import deps
from backend.routers.deps import current_account, get_db, utc
from backend.support import retention as support_retention
from backend.support import tickets as support_tickets
from backend.text_input import PlainText

router = APIRouter(prefix="/api/ranked", tags=["ranked"])


# --- Support tickets (issue #26) -------------------------------------------
#
# Support holds Tickets and nothing else, and only a player request creates
# one. Every player endpoint here reads and writes through the account in the
# session, so there is no form of these calls that reaches another player's
# case.


class CreateTicketRequest(BaseModel):
    attempt_id: str
    # unbounded free text is storage whose size someone else chooses
    description: PlainText | None = Field(default=None, max_length=2000)


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
        "opened_at": utc(ticket["opened_at"]),
        "closed_at": utc(ticket["closed_at"]) if ticket["closed_at"] else None,
        "outcome": ticket["closed_outcome"],
        "evidence_deleted_at": utc(due) if due else None,
        "evidence_held_by_open_case": ticket["closed_at"] is not None and due is None,
    }


@router.get("/support/tickets")
def list_tickets(account: dict = Depends(current_account), conn=Depends(get_db)):
    """This player's own tickets, newest first. Never anybody else's."""
    return [
        _ticket_json(conn, ticket)
        for ticket in support_tickets.tickets_for(conn, account["id"])
    ]


@router.post("/support/tickets", status_code=status.HTTP_201_CREATED)
def create_ticket(
    payload: CreateTicketRequest,
    account: dict = Depends(current_account),
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
    account: dict = Depends(current_account),
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
def review_queue(account: dict = Depends(current_account), conn=Depends(get_db)):
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
            "opened_at": utc(row["opened_at"]),
            "events": [
                {"kind": event["kind"], "occurred_at": utc(event["occurred_at"])}
                for event in row["events"]
            ],
        }
        for row in rows
    ]


@router.post("/support/review/{ticket_id}/close")
def close_ticket(
    ticket_id: str,
    payload: CloseTicketRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Close a reviewed ticket. Changes no points and no access."""
    try:
        UUID(ticket_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found") from None
    try:
        outcome = support_tickets.close_ticket(
            conn, account["id"], ticket_id, payload.outcome, clock=deps.CLOCK
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
    account: dict = Depends(current_account),
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
