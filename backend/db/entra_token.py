"""An Entra access token used as the PostgreSQL connection password (#84).

Managed-identity mode replaces the database password with a short-lived
Entra token the app fetches at the hosting platform's local identity
endpoint. The azure-identity SDK would do this, but it pulls ``requests``
and a dozen transitive packages, which breaks the container's tested
dependency invariants (``test_runtime_requirements``), so this calls the
endpoint with the standard library and caches the token until it is near
expiry. The token value is never logged.

Two endpoints, picked at runtime:

* **Azure Container Apps / App Service** inject ``IDENTITY_ENDPOINT`` and
  ``IDENTITY_HEADER`` into the container. The token comes from that URL
  with the ``X-IDENTITY-HEADER`` header and api-version ``2019-08-01``.
  This is where the app actually runs, so it is tried first.
* **VMs / VMSS** expose the Instance Metadata Service at a fixed link-local
  address with a ``Metadata: true`` header. Used as the fallback when the
  platform injects no identity endpoint.

The earlier version only knew the IMDS address, which Container Apps does
not expose; the token fetch failed there with a ``URLError`` and the app
served a clean 503 instead of reaching the database.
"""
import json
import logging
import os
import time
import urllib.parse
import urllib.request
from datetime import datetime

from backend.db import settings

logger = logging.getLogger(__name__)

DB_TOKEN_RESOURCE = "https://ossrdbms-aad.database.windows.net"

# VM / VMSS Instance Metadata Service.
_IMDS_URL = "http://169.254.169.254/metadata/identity/oauth2/token"
_IMDS_API_VERSION = "2018-02-01"

# App Service / Container Apps managed-identity REST endpoint. The platform
# injects these two env vars; the api-version is the one that endpoint speaks.
IDENTITY_ENDPOINT_ENV_VAR = "IDENTITY_ENDPOINT"
IDENTITY_HEADER_ENV_VAR = "IDENTITY_HEADER"
_MSI_API_VERSION = "2019-08-01"

EXPIRY_SKEW_SECONDS = 300
_IMDS_TIMEOUT_SECONDS = 5

_fetcher = None  # None -> real endpoint call; tests inject a fake with set_token_fetcher
_cache = None  # (token, expires_at) or None


class TokenUnavailable(Exception):
    """Raised when no Entra token could be obtained."""


def set_token_fetcher(fetcher) -> None:
    """Inject a payload fetcher (tests) or reset to the real call with None."""
    global _fetcher
    _fetcher = fetcher


def reset_cache() -> None:
    """Forget any cached token. For tests and for a deliberate refresh."""
    global _cache
    _cache = None


def _token_request() -> urllib.request.Request:
    """Build the token request for whichever identity endpoint this host has.

    Container Apps / App Service inject ``IDENTITY_ENDPOINT`` and
    ``IDENTITY_HEADER``; prefer them, because that is where the app runs.
    Fall back to the VM IMDS address otherwise.
    """
    client_id = os.environ.get(settings.DB_IDENTITY_CLIENT_ID_ENV_VAR, "").strip()
    if not client_id:
        raise TokenUnavailable(
            f"{settings.DB_IDENTITY_CLIENT_ID_ENV_VAR} is not set; "
            "managed-identity mode needs the user-assigned identity's client id."
        )

    identity_endpoint = os.environ.get(IDENTITY_ENDPOINT_ENV_VAR, "").strip()
    identity_header = os.environ.get(IDENTITY_HEADER_ENV_VAR, "").strip()
    if identity_endpoint and identity_header:
        query = urllib.parse.urlencode(
            {
                "api-version": _MSI_API_VERSION,
                "resource": DB_TOKEN_RESOURCE,
                "client_id": client_id,
            }
        )
        return urllib.request.Request(
            f"{identity_endpoint}?{query}",
            headers={"X-IDENTITY-HEADER": identity_header},
        )

    query = urllib.parse.urlencode(
        {
            "api-version": _IMDS_API_VERSION,
            "resource": DB_TOKEN_RESOURCE,
            "client_id": client_id,
        }
    )
    return urllib.request.Request(f"{_IMDS_URL}?{query}", headers={"Metadata": "true"})


def _fetch_token() -> dict:
    request = _token_request()
    with urllib.request.urlopen(request, timeout=_IMDS_TIMEOUT_SECONDS) as response:
        return json.loads(response.read().decode("utf-8"))


def _parse_expires_on(value) -> float:
    """Return ``expires_on`` as epoch seconds.

    IMDS and the Container Apps endpoint return epoch seconds (as a string
    or a number); some App Service builds return a formatted datetime. Parse
    the epoch form first, then a couple of datetime shapes, so a changed
    representation does not silently become a token that never expires.
    """
    text = str(value).strip()
    try:
        return float(text)
    except ValueError:
        pass
    for fmt in ("%m/%d/%Y %I:%M:%S %p %z", "%Y-%m-%dT%H:%M:%S%z"):
        try:
            return datetime.strptime(text, fmt).timestamp()
        except ValueError:
            continue
    raise TokenUnavailable("the token response carried no readable expiry")


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
        payload = (_fetcher or _fetch_token)()
        token = payload["access_token"]
        expires_at = _parse_expires_on(payload["expires_on"])
    except TokenUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 - broad on purpose; no token in the message
        logger.warning("Entra token acquisition failed: %s", type(error).__name__)
        raise TokenUnavailable(
            "could not obtain an Entra token for the database"
        ) from error
    _cache = (token, expires_at)
    return token
