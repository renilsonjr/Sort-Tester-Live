"""The one-time "you're approved for the hat" notice (issue #517).

The owner's approval is a row in ``participant_links``
(``backend.auth.eligibility``). The notice is pending while that row's
``notice_seen_at`` is empty, and the player closing it fills it in. Only
the player's own account is ever read or written here.
"""
from uuid import UUID

from backend.db import migrate


def pending(conn, account_id: UUID) -> bool:
    """True when this account is approved and has not closed the notice."""
    row = migrate.fetch_one(
        conn,
        "SELECT 1 AS pending FROM participant_links"
        " WHERE account_id = %s AND notice_seen_at IS NULL",
        (account_id,),
    )
    return row is not None


def mark_seen(conn, account_id: UUID) -> None:
    """Close it for good. Harmless when there is nothing to close."""
    migrate.execute(
        conn,
        "UPDATE participant_links SET notice_seen_at = now()"
        " WHERE account_id = %s AND notice_seen_at IS NULL",
        (account_id,),
    )
