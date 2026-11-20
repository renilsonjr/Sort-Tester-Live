"""The deletion list: accepted deletions, noted outside the database (#13).

A point-in-time restore rewinds everything inside the database, so an
account a player deleted after the restore point comes back. The restore
runbook (``infra/azure/restore-runbook.md``, step 4) re-applies those
deletions, and for that it needs a record the restore cannot rewind.

This module keeps that record in Azure Blob Storage: one blob per accepted
deletion, **named by the account id, containing the deletion time and
nothing else**. A storage lifecycle rule removes each blob after the 7-day
backup window; this code never extends that. It is an approved, minimal
exception to Decision 14.

The app authenticates with its managed identity (no key, no SAS). Like
``entra_token``, it talks to the REST endpoint with the standard library so
the container's dependency set does not grow.

Off unless ``SORT_TESTER_DELETION_LIST_URL`` holds a container URL, so
development and tests need nothing. A managed-identity deployment must set
it, or say ``disabled`` on purpose; see :func:`check_policy`.
"""
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime
from urllib.parse import urlsplit
from uuid import UUID

from backend.db import entra_token, settings

logger = logging.getLogger(__name__)

ENV_VAR = "SORT_TESTER_DELETION_LIST_URL"
DISABLED = "disabled"

_BLOB_HOST_SUFFIX = ".blob.core.windows.net"
_API_VERSION = "2021-08-06"
_TIMEOUT_SECONDS = 5

_transport = None  # None -> real HTTP call; tests inject a fake with set_transport


class DeletionListConfigError(Exception):
    """The deletion-list setting is missing where required, or malformed."""


class DeletionListUnavailable(Exception):
    """The note could not be written; the deletion must not be accepted."""


def set_transport(transport) -> None:
    """Inject ``transport(method, url, headers, body) -> status`` (tests),
    or reset to the real HTTP call with None."""
    global _transport
    _transport = transport


def container_url() -> str | None:
    """The blob container URL, or None when the list is off.

    The value is never echoed in an error: a pasted SAS URL would be a secret.
    """
    raw = os.environ.get(ENV_VAR, "").strip()
    if not raw or raw == DISABLED:
        return None
    try:
        parts = urlsplit(raw)
        host = parts.hostname or ""
        segments = [segment for segment in parts.path.split("/") if segment]
        valid = (
            parts.scheme == "https"
            and host.endswith(_BLOB_HOST_SUFFIX)
            and len(host) > len(_BLOB_HOST_SUFFIX)
            and parts.username is None
            and parts.password is None
            and parts.port is None
            and not parts.query
            and not parts.fragment
            and len(segments) == 1
        )
    except ValueError:
        valid = False
    if not valid:
        raise DeletionListConfigError(
            f"{ENV_VAR} must be https://<account>{_BLOB_HOST_SUFFIX}/<container> "
            f"with no query string or credentials, or the word {DISABLED!r}."
        )
    return f"https://{host}/{segments[0]}"


def check_policy(*, db_auth_mode: str) -> None:
    """Refuse to start a managed-identity deployment that says nothing.

    Forgetting the setting would switch the list off in silence, and nobody
    would notice until a restore brought deleted accounts back. A hosted
    deployment therefore has to name a container or write ``disabled``.
    A malformed value stops startup in every mode.
    """
    container_url()
    raw = os.environ.get(ENV_VAR, "").strip()
    if db_auth_mode == settings.MANAGED_IDENTITY_MODE and not raw:
        raise DeletionListConfigError(
            f"{ENV_VAR} is not set. A managed-identity deployment must name the "
            f"deletion-list container, or set it to {DISABLED!r} on purpose."
        )


def _blob_url(container: str, account_id) -> str:
    # only a UUID may become a blob name: no path tricks, no other container
    return f"{container}/{UUID(str(account_id))}"


def _send(method: str, url: str, headers: dict, body: bytes | None) -> int:
    request = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code


def _call(method: str, url: str, body: bytes | None, extra_headers: dict) -> int:
    token = entra_token.access_token(entra_token.STORAGE_TOKEN_RESOURCE)
    headers = {
        "Authorization": f"Bearer {token}",
        "x-ms-version": _API_VERSION,
        **extra_headers,
    }
    return (_transport or _send)(method, url, headers, body)


def record(account_id, deleted_at: datetime) -> None:
    """Note one accepted deletion. Raises :class:`DeletionListUnavailable`
    unless the storage service confirmed the write; does nothing when off."""
    container = container_url()
    if container is None:
        return
    if deleted_at.tzinfo is None:
        raise ValueError("the deletion time must carry a timezone")
    url = _blob_url(container, account_id)
    body = deleted_at.isoformat().encode("ascii")
    try:
        status = _call(
            "PUT",
            url,
            body,
            {"x-ms-blob-type": "BlockBlob", "Content-Type": "text/plain"},
        )
    except Exception as error:  # noqa: BLE001 - broad on purpose; no token in the message
        logger.warning("deletion list write failed: %s", type(error).__name__)
        raise DeletionListUnavailable("the deletion list could not be written") from None
    if status != 201:
        logger.warning("deletion list write refused: HTTP %s", status)
        raise DeletionListUnavailable("the deletion list could not be written")


def forget(account_id) -> None:
    """Remove a note whose deletion did not happen. Best effort, never raises:
    it runs while another error is already being reported. A note left behind
    is logged, because a restore would otherwise delete a live account."""
    try:
        container = container_url()
        if container is None:
            return
        status = _call("DELETE", _blob_url(container, account_id), None, {})
    except Exception as error:  # noqa: BLE001 - see docstring
        status = type(error).__name__
    if status not in (202, 404):
        logger.error(
            "deletion list note for account %s could not be removed (%s); "
            "remove it by hand before any restore",
            account_id,
            status,
        )
