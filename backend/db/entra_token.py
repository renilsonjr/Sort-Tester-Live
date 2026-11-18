"""An Entra access token used as the PostgreSQL connection password (#84).

Managed-identity mode replaces the database password with a short-lived
Entra token fetched from the Azure Instance Metadata Service (IMDS). The
azure-identity SDK would do this, but it pulls ``requests`` and a dozen
transitive packages, which breaks the container's tested dependency
invariants (``test_runtime_requirements``). IMDS is one documented
endpoint, so this calls it with the standard library and caches the token
until it is near expiry. The token value is never logged.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request

from backend.db import settings

logger = logging.getLogger(__name__)

DB_TOKEN_RESOURCE = "https://ossrdbms-aad.database.windows.net"
_IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"
_IMDS_API_VERSION = "2018-02-01"
EXPIRY_SKEW_SECONDS = 300
_IMDS_TIMEOUT_SECONDS = 5

_fetcher = None  # None -> real IMDS call; tests inject a fake with set_token_fetcher
_cache = None  # (token, expires_at) or None


class TokenUnavailable(Exception):
    """Raised when no Entra token could be obtained."""


def set_token_fetcher(fetcher) -> None:
    """Inject a payload fetcher (tests) or reset to the real IMDS call with None."""
    global _fetcher
    _fetcher = fetcher


def reset_cache() -> None:
    """Forget any cached token. For tests and for a deliberate refresh."""
    global _cache
    _cache = None


def _imds_fetch() -> dict:
    client_id = os.environ.get(settings.DB_IDENTITY_CLIENT_ID_ENV_VAR, "").strip()
    if not client_id:
        raise TokenUnavailable(
            f"{settings.DB_IDENTITY_CLIENT_ID_ENV_VAR} is not set; "
            "managed-identity mode needs the user-assigned identity's client id."
        )
    query = urllib.parse.urlencode(
        {
            "api-version": _IMDS_API_VERSION,
            "resource": DB_TOKEN_RESOURCE,
            "client_id": client_id,
        }
    )
    request = urllib.request.Request(
        f"{_IMDS_URL}?{query}", headers={"Metadata": "true"}
    )
    with urllib.request.urlopen(request, timeout=_IMDS_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def db_access_token() -> str:
    """Return a valid Entra token for the PostgreSQL resource.

    Reuses a cached token until it is within ``EXPIRY_SKEW_SECONDS`` of
    expiry, then refetches. Never logs the token. On any failure raises
    :class:`TokenUnavailable` with no token material in the message.
    """
    global _cache
    now = time.time()
    if _cache is not None and now < _cache[1] - EXPIRY_SKEW_SECONDS:
        return _cache[0]
    try:
        payload = (_fetcher or _imds_fetch)()
        token = payload["access_token"]
        expires_at = float(payload["expires_on"])
    except TokenUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 - broad on purpose; no token in the message
        logger.warning("Entra token acquisition failed: %s", type(error).__name__)
        raise TokenUnavailable(
            "could not obtain an Entra token for the database"
        ) from error
    _cache = (token, expires_at)
    return token
