import hashlib
import secrets

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.auth.settings import AuthSettings


def normalize_login_id(login_id: str) -> str:
    """Return the canonical form of a login ID.

    Removes dashes and whitespace, uppercases, and rejects characters
    outside the Crockford base32 alphabet (I, L, O, U are never accepted).
    """
    cleaned = login_id.replace("-", "").replace(" ", "").strip().upper()
    allowed = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
    for char in cleaned:
        if char not in allowed:
            raise ValueError(f"Invalid character in login ID: {char}")
    return cleaned


def generate_login_id(settings: AuthSettings) -> str:
    """Generate a new login ID as a grouped, easy-to-type secret."""
    raw = "".join(secrets.choice(settings.login_id_alphabet) for _ in range(settings.login_id_length))
    group_size = settings.login_id_group_size
    return "-".join(raw[i : i + group_size] for i in range(0, len(raw), group_size))


def derive_lookup_key(login_id: str) -> str:
    """Derive a non-secret lookup key from a login ID.

    The lookup key is used to find the candidate credential row during login.
    It is deterministic and collision-resistant but does not reveal the secret.
    """
    normalized = normalize_login_id(login_id)
    digest = hashlib.sha256(normalized.encode("ascii")).digest()
    return digest[:16].hex()


def _hasher(settings: AuthSettings) -> PasswordHasher:
    return PasswordHasher(
        time_cost=settings.argon2_time_cost,
        memory_cost=settings.argon2_memory_cost,
        parallelism=settings.argon2_parallelism,
        type=argon2.Type.ID,
    )


def hash_login_id(login_id: str, settings: AuthSettings | None = None) -> str:
    """Hash a login ID for storage. Uses Argon2id."""
    if settings is None:
        settings = AuthSettings()
    normalized = normalize_login_id(login_id)
    return _hasher(settings).hash(normalized)


def verify_login_id(login_id: str, encoded_hash: str, settings: AuthSettings | None = None) -> bool:
    """Verify a login ID against its stored Argon2id verifier."""
    if settings is None:
        settings = AuthSettings()
    try:
        normalized = normalize_login_id(login_id)
    except ValueError:
        return False
    try:
        _hasher(settings).verify(encoded_hash, normalized)
        return True
    except VerifyMismatchError:
        return False
