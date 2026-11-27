"""Messages a locked-out player leaves for the owner (issue #251).

Somebody who lost their login ID cannot sign in, and there is no email.
From the sign-in screen they may leave one free-text message. This module
is the whole rule for that message:

* **It is a note, not a recovery.** Leaving one looks up no account, opens
  no recovery request and issues nothing. Access is restored only by the
  owner, in person, through ``backend/auth/recovery.py``.
* **It proves nothing.** Anybody can type anything, including somebody
  else's name. The owner reads it as a reason to go and find a person.
* **It is bounded.** At most ``MAX_LENGTH`` characters, and at most
  ``MAX_UNRESOLVED`` unread at once, so the table cannot be filled from
  outside however many addresses the messages come from.
* **Only the owner reads it.**
* **It is not kept for good.** A message is free text and may name a
  person. Once the owner has marked it resolved it has done its job, and
  it is deleted ``RESOLVED_RETENTION_DAYS`` days later. One still waiting
  for the owner is never deleted by age.
"""
from datetime import timedelta
from uuid import UUID

from backend.auth.owner import is_active_owner
from backend.db import migrate

MAX_LENGTH = 500
MAX_UNRESOLVED = 100
# Owner decision, 2026-11-23.
RESOLVED_RETENTION_DAYS = 30


class MessageRefused(Exception):
    """The text itself is not acceptable. ``reason`` may be shown."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class InboxFull(Exception):
    """Too many unresolved messages are already waiting."""


class NotOwner(Exception):
    """Somebody other than the owner asked to read or resolve."""


def _require_owner(conn, owner_account_id: UUID) -> None:
    if not is_active_owner(conn, owner_account_id):
        raise NotOwner()


def leave_message(conn, body: str, *, clock) -> None:
    """Store one message. Returns nothing: there is nothing to tell the sender."""
    cleaned = (body or "").strip()
    if not cleaned:
        raise MessageRefused("Write a message first.")
    if len(cleaned) > MAX_LENGTH:
        raise MessageRefused(f"A message can be at most {MAX_LENGTH} characters.")
    # The ceiling and the insert are one statement, so a full inbox stores
    # nothing rather than being checked and then overrun.
    row = migrate.fetch_one(
        conn,
        "INSERT INTO recovery_messages (body, created_at)"
        " SELECT %s, %s"
        " WHERE (SELECT count(*) FROM recovery_messages WHERE resolved_at IS NULL) < %s"
        " RETURNING id",
        (cleaned, clock.now(), MAX_UNRESOLVED),
    )
    if row is None:
        raise InboxFull()


def list_messages(conn, owner_account_id: UUID, limit: int = 50) -> list[dict]:
    """The owner's inbox: unresolved first, then newest first."""
    _require_owner(conn, owner_account_id)
    rows = migrate.fetch_all(
        conn,
        "SELECT id, body, created_at, resolved_at FROM recovery_messages"
        " ORDER BY (resolved_at IS NOT NULL), created_at DESC LIMIT %s",
        (limit,),
    )
    return [dict(row) for row in rows]


def resolve(conn, owner_account_id: UUID, message_id: UUID, *, clock) -> bool:
    """Mark one message resolved. False when there is no such message.

    Resolving twice keeps the first date: the second press changes nothing.
    """
    _require_owner(conn, owner_account_id)
    migrate.execute(
        conn,
        "UPDATE recovery_messages SET resolved_at = %s, resolved_by = %s"
        " WHERE id = %s AND resolved_at IS NULL",
        (clock.now(), owner_account_id, message_id),
    )
    return migrate.fetch_one(
        conn, "SELECT id FROM recovery_messages WHERE id = %s", (message_id,)
    ) is not None


def purge_resolved(conn, *, clock) -> int:
    """Delete messages resolved more than the retention period ago.

    Returns how many were deleted. Committing is the caller's. On a server
    with nothing due this is one DELETE that matches nothing.
    """
    result = migrate.execute(
        conn,
        "DELETE FROM recovery_messages"
        " WHERE resolved_at IS NOT NULL AND resolved_at < %s",
        (clock.now() - timedelta(days=RESOLVED_RETENTION_DAYS),),
    )
    return getattr(result, "rowcount", 0)
