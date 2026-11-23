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
from backend.auth.settings import AuthSettings
from backend.auth.sessions import (
    authenticate_session,
    create_session,
    revoke_all_account_sessions,
)
from backend.db import migrate


_settings = AuthSettings()
_dummy_verifier_cache = None


def _get_dummy_verifier() -> str:
    global _dummy_verifier_cache
    if _dummy_verifier_cache is None:
        _dummy_verifier_cache = hash_login_id("DAAA-AAAA-AAAA-AAAA", _settings)
    return _dummy_verifier_cache


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

    login_id = generate_login_id(_settings)
    lookup_key = derive_lookup_key(login_id)
    verifier = hash_login_id(login_id, _settings)
    migrate.execute(
        conn,
        """
        INSERT INTO login_credentials (account_id, lookup_key, verifier)
        VALUES (%s, %s, %s)
        """,
        (account_id, lookup_key, verifier),
    )
    return account_id, login_id


def find_login_candidates(conn, login_id: str) -> tuple[str | None, list[dict]]:
    """Read the credentials a login ID could match. Checks nothing.

    Returns (normalized login ID, candidate rows); the normalized form is
    None when the ID is too malformed to name a credential at all.
    """
    try:
        normalized = normalize_login_id(login_id)
    except ValueError:
        return None, []
    candidates = migrate.fetch_all(
        conn,
        """
        SELECT lc.id, lc.account_id, lc.verifier
        FROM login_credentials lc
        WHERE lc.lookup_key = %s AND lc.revoked_at IS NULL
        """,
        (derive_lookup_key(normalized),),
    )
    return normalized, candidates


def check_login_candidates(normalized: str | None, candidates: list[dict]) -> dict | None:
    """Return the candidate the login ID verifies against, or None.

    Needs no database connection, so a caller can give its connection back
    before the expensive part and take one again afterwards.

    Every path performs one Argon2 verification, a dummy one when there is
    nothing real to check, so that timing does not reveal whether a lookup
    key exists in the database.
    """
    if normalized is None:
        verify_login_id("DAAA-AAAA-AAAA-AAAA", _get_dummy_verifier(), _settings)
        return None
    if not candidates:
        verify_login_id(normalized, _get_dummy_verifier(), _settings)
        return None
    for candidate in candidates:
        if verify_login_id(normalized, candidate["verifier"], _settings):
            return candidate
    return None


def open_login_session(
    conn,
    candidate: dict,
    ttl_seconds: int,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, UUID] | None:
    """Create the session for a verified candidate.

    The credential is read again first: it was verified without a
    connection held, and one revoked in that moment must not sign anyone in.
    """
    still_valid = migrate.fetch_one(
        conn,
        "SELECT 1 FROM login_credentials WHERE id = %s AND revoked_at IS NULL",
        (candidate["id"],),
    )
    if still_valid is None:
        return None
    return create_session(
        conn, candidate["account_id"], ttl_seconds, ip_address, user_agent
    )


def login_with_id(
    conn,
    login_id: str,
    ttl_seconds: int,
    ip_address: str | None,
    user_agent: str | None,
) -> tuple[str, UUID] | None:
    """Authenticate with a login ID and create a session, on one connection.

    The sign-in route runs the same three steps itself so that it holds no
    connection during the verification; this is the single-connection form
    for callers that are already inside a transaction.
    """
    normalized, candidates = find_login_candidates(conn, login_id)
    candidate = check_login_candidates(normalized, candidates)
    if candidate is None:
        return None
    return open_login_session(conn, candidate, ttl_seconds, ip_address, user_agent)


def get_account_by_session(conn, raw_token: str) -> dict | None:
    """Return the account row for an active session token."""
    session = authenticate_session(conn, raw_token)
    if session is None:
        return None
    return migrate.fetch_one(
        conn,
        "SELECT id, username, tag, is_owner, avatar, created_at FROM accounts"
        " WHERE id = %s AND deleted_at IS NULL",
        (session["account_id"],),
    )


def admin_regenerate_login_id(
    conn, admin_account_id: UUID, target_account_id: UUID
) -> str | None:
    """Deprecated: regenerating on the owner's say-so alone.

    The settled recovery policy requires in-person verification against a
    trusted participant link **established before the request**, and says
    that no trusted prior link means no reset by this route. This function
    checked only that the caller is the owner, which is the authority to
    act and not evidence about who is asking.

    ``backend.auth.recovery`` is that route now: it records the request,
    refuses without an older link, and hands the login ID over once. This
    is kept only so that an old caller fails loudly rather than quietly
    doing the wrong thing.
    """
    raise NotImplementedError(
        "Use backend.auth.recovery.open_request and hand_over: recovery needs"
        " a trusted roster link established before the request (settled"
        " recovery policy), which this function never checked."
    )


def issue_new_login_id(conn, account_id: UUID) -> str:
    """Give this account a new login ID and invalidate what came before.

    The old credential is revoked and every session is ended, so a login
    ID that may have been seen by somebody else stops working at the same
    moment the new one starts. The old one is never disclosed, because
    only its hash was ever stored. Returned once: the caller shows it to
    the person it belongs to and keeps no copy.

    Restoring access is all this does. It moves no points, opens no
    history and creates no prize eligibility.
    """
    migrate.execute(
        conn,
        "UPDATE login_credentials SET revoked_at = now()"
        " WHERE account_id = %s AND revoked_at IS NULL",
        (account_id,),
    )
    revoke_all_account_sessions(conn, account_id)

    new_login_id = generate_login_id(_settings)
    lookup_key = derive_lookup_key(new_login_id)
    verifier = hash_login_id(new_login_id, _settings)
    migrate.execute(
        conn,
        """
        INSERT INTO login_credentials (account_id, lookup_key, verifier)
        VALUES (%s, %s, %s)
        """,
        (account_id, lookup_key, verifier),
    )
    return new_login_id
