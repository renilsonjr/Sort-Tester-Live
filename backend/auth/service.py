import secrets
import string
from uuid import UUID

from backend.auth.credentials import (
    derive_lookup_key,
    generate_login_id,
    hash_login_id,
    normalize_login_id,
    verify_login_id,
)
from backend.auth.sessions import (
    authenticate_session,
    create_session,
    revoke_all_account_sessions,
)
from backend.db import migrate


def _generate_unique_tag(conn) -> str:
    alphabet = string.ascii_uppercase + string.digits
    while True:
        tag = "".join(secrets.choice(alphabet) for _ in range(6))
        existing = migrate.fetch_one(
            conn,
            "SELECT 1 FROM accounts WHERE tag = %s",
            (tag,),
        )
        if existing is None:
            return tag


def register_account(conn, username: str) -> tuple[UUID, str]:
    """Create a new account with a generated login ID.

    Returns (account_id, login_id). The login ID is shown only once.
    """
    username_lower = username.lower()
    tag = _generate_unique_tag(conn)
    row = migrate.fetch_one(
        conn,
        """
        INSERT INTO accounts (username, username_lower, tag)
        VALUES (%s, %s, %s)
        RETURNING id
        """,
        (username, username_lower, tag),
    )
    account_id = row["id"]

    from backend.auth.settings import AuthSettings

    settings = AuthSettings()
    login_id = generate_login_id(settings)
    lookup_key = derive_lookup_key(login_id)
    verifier = hash_login_id(login_id, settings)
    migrate.execute(
        conn,
        """
        INSERT INTO login_credentials (account_id, lookup_key, verifier)
        VALUES (%s, %s, %s)
        """,
        (account_id, lookup_key, verifier),
    )
    return account_id, login_id


def login_with_id(
    conn,
    login_id: str,
    ttl_seconds: int,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, UUID] | None:
    """Authenticate with a login ID and create a session."""
    try:
        normalized = normalize_login_id(login_id)
    except ValueError:
        return None
    lookup_key = derive_lookup_key(normalized)
    candidates = migrate.fetch_all(
        conn,
        """
        SELECT lc.account_id, lc.verifier
        FROM login_credentials lc
        WHERE lc.lookup_key = %s AND lc.revoked_at IS NULL
        """,
        (lookup_key,),
    )
    if not candidates:
        return None
    for candidate in candidates:
        if verify_login_id(normalized, candidate["verifier"]):
            return create_session(
                conn, candidate["account_id"], ttl_seconds, ip_address, user_agent
            )
    return None


def get_account_by_session(conn, raw_token: str) -> dict | None:
    """Return the account row for an active session token."""
    session = authenticate_session(conn, raw_token)
    if session is None:
        return None
    return migrate.fetch_one(
        conn,
        "SELECT id, username, tag, is_owner, created_at FROM accounts WHERE id = %s",
        (session["account_id"],),
    )


def admin_regenerate_login_id(
    conn, admin_account_id: UUID, target_account_id: UUID
) -> str | None:
    """Admin-only: revoke the target's credential and sessions, issue a new login ID."""
    admin = migrate.fetch_one(
        conn,
        "SELECT is_owner FROM accounts WHERE id = %s AND is_owner = true",
        (admin_account_id,),
    )
    if admin is None:
        return None

    target = migrate.fetch_one(
        conn,
        "SELECT id FROM accounts WHERE id = %s",
        (target_account_id,),
    )
    if target is None:
        return None

    # revoke existing credential
    migrate.execute(
        conn,
        "UPDATE login_credentials SET revoked_at = now() WHERE account_id = %s AND revoked_at IS NULL",
        (target_account_id,),
    )
    # revoke all active sessions
    revoke_all_account_sessions(conn, target_account_id)

    from backend.auth.settings import AuthSettings

    settings = AuthSettings()
    new_login_id = generate_login_id(settings)
    lookup_key = derive_lookup_key(new_login_id)
    verifier = hash_login_id(new_login_id, settings)
    migrate.execute(
        conn,
        """
        INSERT INTO login_credentials (account_id, lookup_key, verifier)
        VALUES (%s, %s, %s)
        """,
        (target_account_id, lookup_key, verifier),
    )
    return new_login_id
