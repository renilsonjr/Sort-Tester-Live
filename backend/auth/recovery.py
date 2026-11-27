"""Owner-approved access recovery (issue #11, slice 3).

Somebody loses their login ID. There is no self-service route back and
there is deliberately no email to send one to, so the only way is the
owner, in person, at work. This module is the rule for that.

The owner's settled policy, and what each part means here:

* **In person, against a trusted prior link.** The link is the owner's
  own roster approval (``participant_links``), and it has to have existed
  **before** the request. A link recorded in the same breath as the
  recovery proves nothing: it would just be the owner saying twice that
  this is the right person. So the request is written down first, and the
  link must be older than it.
* **No trusted prior link means no recovery by this route.** Not a
  warning, a refusal.
* **A public username or tag is not proof**, and neither is holding the
  owner role: both are required, neither is sufficient, and this module
  never asks for a tag alone.
* **One-use handoff.** The new login ID is shown once, to be handed over
  in person. The record of the recovery keeps no copy of it, so nobody,
  the owner included, can read it afterwards.
* **Same account.** Recovery restores access to the account that was
  lost. It issues no substitute account, moves no points, creates no
  prize eligibility, opens no history and restores nothing that was
  deleted.

The one thing this module cannot check is the part that matters most:
that the person in front of the owner is who they say they are. That is
the owner's job, done in person, and the screen says so.
"""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from backend.auth.owner import is_active_owner
from backend.auth.service import issue_new_login_id
from backend.db import migrate


class RecoveryError(Exception):
    """A refusal with a reason the owner may be shown."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class RecoveryRequest:
    id: UUID
    account_id: UUID
    username: str
    tag: str
    opened_at: datetime


@dataclass(frozen=True)
class Handover:
    """What the owner reads out once and then cannot read again."""

    login_id: str
    username: str
    tag: str


def _require_owner(conn, owner_account_id: UUID) -> None:
    if not is_active_owner(conn, owner_account_id):
        raise RecoveryError("Only the owner may approve a recovery.")


def open_request(
    conn, owner_account_id: UUID, tag: str, *, clock
) -> RecoveryRequest:
    """Start a recovery for the account with this tag.

    Opening one asserts nothing and grants nothing: it records that the
    owner is standing in front of somebody claiming that account, at a
    moment the trusted link must already predate.
    """
    _require_owner(conn, owner_account_id)
    cleaned = (tag or "").strip().lstrip("#").strip().upper()
    if not cleaned:
        raise RecoveryError("A player tag is required.")
    account = migrate.fetch_one(
        conn,
        "SELECT id, username, tag FROM accounts"
        " WHERE tag = %s AND deleted_at IS NULL",
        (cleaned,),
    )
    if account is None:
        raise RecoveryError("No account with that tag.")
    if account["id"] == owner_account_id:
        raise RecoveryError(
            "Your own access is recovered on the server machine, not here."
        )
    row = migrate.fetch_one(
        conn,
        "INSERT INTO recovery_requests (account_id, opened_by, opened_at)"
        " VALUES (%s, %s, %s) RETURNING id, opened_at",
        (account["id"], owner_account_id, clock.now()),
    )
    return RecoveryRequest(
        id=row["id"],
        account_id=account["id"],
        username=account["username"],
        tag=account["tag"],
        opened_at=row["opened_at"],
    )


def hand_over(conn, owner_account_id: UUID, request_id: UUID, *, clock) -> Handover:
    """Complete a recovery: issue a new login ID, once.

    Everything the policy requires is checked here rather than at the
    screen, because a screen is not where a rule belongs.
    """
    _require_owner(conn, owner_account_id)
    request = migrate.fetch_one(
        conn,
        "SELECT r.id, r.account_id, r.opened_at, r.completed_at,"
        " a.username, a.tag, a.deleted_at"
        " FROM recovery_requests r JOIN accounts a ON a.id = r.account_id"
        " WHERE r.id = %s FOR UPDATE",
        (request_id,),
    )
    if request is None:
        raise RecoveryError("No such recovery.")
    if request["completed_at"] is not None:
        # One use. A second reading would be a second secret in the world.
        raise RecoveryError(
            "That recovery is already done. Its Quiz Code was shown once and"
            " cannot be shown again; open a new recovery if it was lost."
        )
    if request["deleted_at"] is not None:
        raise RecoveryError("That account has been deleted. There is nothing to restore.")
    link = migrate.fetch_one(
        conn,
        "SELECT established_at FROM participant_links"
        " WHERE account_id = %s AND established_at < %s",
        (request["account_id"], request["opened_at"]),
    )
    if link is None:
        raise RecoveryError(
            "This account has no roster link recorded before the request, so"
            " access cannot be restored this way."
        )
    login_id = issue_new_login_id(conn, request["account_id"])
    migrate.execute(
        conn,
        "UPDATE recovery_requests SET completed_at = %s, completed_by = %s"
        " WHERE id = %s",
        (clock.now(), owner_account_id, request_id),
    )
    return Handover(
        login_id=login_id,
        username=request["username"],
        tag=request["tag"],
    )


def recent_requests(conn, owner_account_id: UUID, limit: int = 20) -> list[dict]:
    """The owner's own record of recoveries, newest first.

    Deliberately thin: who, when, and whether it completed. No login ID is
    kept, so none can be shown; nothing about how the player has played
    appears here either.
    """
    _require_owner(conn, owner_account_id)
    rows = migrate.fetch_all(
        conn,
        "SELECT r.id, a.username, a.tag, r.opened_at, r.completed_at"
        " FROM recovery_requests r JOIN accounts a ON a.id = r.account_id"
        " ORDER BY r.opened_at DESC LIMIT %s",
        (limit,),
    )
    return [dict(row) for row in rows]
