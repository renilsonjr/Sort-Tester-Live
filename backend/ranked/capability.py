"""Page-instance capability for ranked attempts (issue #8).

An attempt may only be continued by the page that started it. At start the
server issues a random token; the page keeps it in memory and presents it on
every later request. Only the token's SHA-256 is stored, so the database never
holds a usable capability. This proves possession of a page-memory secret, not
a device or a human.
"""
import hashlib
import hmac
import secrets

from backend.db import migrate


def new_token() -> str:
    """Return a fresh random capability token (URL-safe text, 256 bits)."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> bytes:
    """Return the SHA-256 digest stored in place of the token."""
    return hashlib.sha256(token.encode("ascii")).digest()


def matches(conn, attempt_id, token) -> bool:
    """Whether ``token`` is the capability the attempt was started with.

    False for a missing, empty or malformed token and for an attempt that has
    no stored capability. The comparison is constant-time.
    """
    if not token:
        return False
    try:
        presented = hash_token(token)
    except UnicodeEncodeError:
        return False
    row = migrate.fetch_one(
        conn,
        "SELECT page_capability_sha256 AS stored FROM attempts WHERE id = %s",
        (attempt_id,),
    )
    if row is None or row["stored"] is None:
        return False
    return hmac.compare_digest(bytes(row["stored"]), presented)
