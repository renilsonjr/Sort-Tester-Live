import re
import secrets

import argon2
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from backend.auth.settings import AuthSettings
from backend.auth.verification_gate import get_verification_gate
from backend.auth.wordlist import WORDS

# Quiz Codes issued before 2026-11-25: 16 Crockford base32 characters
# (I, L, O and U never appear), shown in groups of four.
_LEGACY_ALPHABET = set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")
_LEGACY_LENGTH = 16
# Quiz Codes from 2026-11-25: one English word and two digits.
_WORD_CODE = re.compile(r"[a-z]{3,8}[0-9]{2}")


def normalize_login_id(login_id: str) -> str:
    """Return the canonical form of a login ID, either format.

    Dashes, spaces and case do not matter, so ``Banana-48``, ``banana 48``
    and ``banana48`` are the same code. A 16-character code from before
    2026-11-25 keeps its old rules (uppercase Crockford base32). Anything
    that is neither shape raises ``ValueError``.
    """
    cleaned = login_id.replace("-", "").replace(" ", "").strip()
    upper = cleaned.upper()
    if len(upper) == _LEGACY_LENGTH and set(upper) <= _LEGACY_ALPHABET:
        return upper
    lower = cleaned.lower()
    if _WORD_CODE.fullmatch(lower):
        return lower
    raise ValueError("Not a Quiz Code")


def generate_login_id(settings: AuthSettings | None = None) -> str:
    """Generate a new Quiz Code: one English word and two digits.

    For example ``banana-48``. Both parts come from ``secrets``. Codes need
    not be unique: sign-in names the account by username first.
    """
    word = secrets.choice(WORDS)
    return f"{word}-{secrets.choice(CODE_ENDINGS)}"


# Two-digit endings a new Quiz Code may draw (#516): every one from 00 to 99
# except the hate-symbol numbers and the one juvenile one, so no code reads
# as either. Codes already issued keep whatever ending they have.
_EXCLUDED_ENDINGS = frozenset({"14", "88", "69"})
CODE_ENDINGS: tuple[str, ...] = tuple(
    f"{n:02d}" for n in range(100) if f"{n:02d}" not in _EXCLUDED_ENDINGS
)


def new_lookup_key() -> str:
    """A random value for ``login_credentials.lookup_key``.

    The column is ``NOT NULL UNIQUE`` from the code-only sign-in days, when
    it held a SHA-256 of the code. Sign-in now finds the credential by
    account, and a hash of a word code could be reversed by trying every
    code, so nothing derived from the code is stored any more.
    """
    return secrets.token_hex(16)


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
    with get_verification_gate().turn():
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
        with get_verification_gate().turn():
            _hasher(settings).verify(encoded_hash, normalized)
        return True
    except VerifyMismatchError:
        return False
