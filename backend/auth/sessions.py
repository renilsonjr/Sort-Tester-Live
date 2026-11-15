import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import UUID

from backend.db import migrate


def _hash_token(raw_token: str) -> bytes:
    return hashlib.sha256(raw_token.encode("ascii")).digest()


def create_session(
    conn,
    account_id: UUID,
    ttl_seconds: int,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, UUID]:
    """Create a new opaque server-side session and return (raw_token, session_id)."""
    raw_token = secrets.token_urlsafe(32)
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=ttl_seconds)
    row = migrate.fetch_one(
        conn,
        """
        INSERT INTO sessions (account_id, token_hash, expires_at, last_seen_at, ip_address, user_agent)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (account_id, token_hash, expires_at, now, ip_address, user_agent),
    )
    return raw_token, row["id"]


def authenticate_session(
    conn, raw_token: str, idle_seconds: int | None = None
) -> dict | None:
    """Return the active session row for a raw token, or None.

    ``idle_seconds`` ends a session that has been left alone that long, even
    though ``expires_at`` is still in the future: a phone put down on a sort
    floor should not keep an account open. Every request already refreshes
    ``last_seen_at`` below, so an account in use never trips it, and the
    check is here rather than in each router because this is the one gate
    every authenticated request passes through.

    The expiry is lazy: the row is revoked when the token is next presented.
    A session nobody comes back to simply stays unusable until
    ``expires_at`` removes it, which is the same outcome without a sweep.
    """
    if idle_seconds is None:
        from backend.auth.settings import get_auth_settings

        idle_seconds = get_auth_settings().session_idle_seconds
    token_hash = _hash_token(raw_token)
    now = datetime.now(timezone.utc)
    row = migrate.fetch_one(
        conn,
        """
        SELECT * FROM sessions
        WHERE token_hash = %s
          AND expires_at > %s
          AND revoked_at IS NULL
        """,
        (token_hash, now),
    )
    if row is None:
        return None
    if idle_seconds > 0 and row["last_seen_at"] <= now - timedelta(seconds=idle_seconds):
        revoke_session(conn, row["id"])
        return None
    migrate.execute(
        conn,
        "UPDATE sessions SET last_seen_at = %s WHERE id = %s",
        (now, row["id"]),
    )
    return row


def revoke_session(conn, session_id: UUID) -> None:
    """Revoke a single session by id."""
    now = datetime.now(timezone.utc)
    migrate.execute(
        conn,
        "UPDATE sessions SET revoked_at = %s WHERE id = %s AND revoked_at IS NULL",
        (now, session_id),
    )


def revoke_all_account_sessions(conn, account_id: UUID) -> None:
    """Revoke all active sessions for an account."""
    now = datetime.now(timezone.utc)
    migrate.execute(
        conn,
        """
        UPDATE sessions
        SET revoked_at = %s
        WHERE account_id = %s AND revoked_at IS NULL
        """,
        (now, account_id),
    )
