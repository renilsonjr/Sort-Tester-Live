"""Self-service account deletion (issue #47).

Rules: the security/operations design (deletion, Q10) and the decision record
(Decision 14). The player re-enters their login ID and acknowledges that
deletion cannot be undone. Once accepted the account is inaccessible and
pending purge; the purge then removes everything the account owns. Only a
minimal season-ineligibility marker survives, so the same person cannot
delete and return for the same season's prizes.

Deletion is never reported as completed here: that needs verified erasure of
backups and outside providers, which do not exist yet (#13, #41).
"""
from datetime import datetime, timezone

from backend.auth.credentials import normalize_login_id, verify_login_id
from backend.db import migrate


class DeletionError(Exception):
    """The deletion was refused; nothing was changed."""


class WrongLoginIdError(DeletionError):
    """The login ID does not belong to this account."""


class OwnerAccountError(DeletionError):
    """The sole owner account cannot be deleted."""


class _SystemClock:
    def now(self):
        return datetime.now(timezone.utc)


def request_deletion(conn, account_id, login_id: str, *, clock=None) -> None:
    """Accept the account's own deletion request, in one transaction.

    Refuses the owner and a wrong login ID, changing nothing. Otherwise marks
    the account pending purge, revokes its sessions and login credentials,
    removes its unfinished attempts without fabricating a score, and keeps a
    season marker if the account has a participant link.
    """
    now = (clock or _SystemClock()).now()
    account = migrate.fetch_one(
        conn,
        "SELECT is_owner, deleted_at FROM accounts WHERE id = %s FOR UPDATE",
        (account_id,),
    )
    if account is None or account["deleted_at"] is not None:
        conn.rollback()
        raise WrongLoginIdError("no such active account")
    if account["is_owner"]:
        conn.rollback()
        raise OwnerAccountError("the sole owner account cannot be deleted")
    if not _login_id_matches(conn, account_id, login_id):
        conn.rollback()
        raise WrongLoginIdError("the login ID does not match this account")

    migrate.execute(
        conn, "UPDATE accounts SET deleted_at = %s WHERE id = %s", (now, account_id)
    )
    migrate.execute(
        conn,
        "UPDATE sessions SET revoked_at = %s WHERE account_id = %s AND revoked_at IS NULL",
        (now, account_id),
    )
    migrate.execute(
        conn,
        "UPDATE login_credentials SET revoked_at = %s"
        " WHERE account_id = %s AND revoked_at IS NULL",
        (now, account_id),
    )
    # the attempt in progress ends without a score: it is removed, not scored
    migrate.execute(
        conn,
        "DELETE FROM attempts WHERE account_id = %s AND state <> 'finalized'",
        (account_id,),
    )
    link = migrate.fetch_one(
        conn,
        "SELECT roster_reference FROM participant_links WHERE account_id = %s",
        (account_id,),
    )
    season = migrate.fetch_one(
        conn, "SELECT id FROM seasons ORDER BY opened_at DESC LIMIT 1"
    )
    if link is not None and season is not None:
        migrate.execute(
            conn,
            "INSERT INTO season_markers (roster_reference, season, ineligible)"
            " VALUES (%s, %s, true)"
            " ON CONFLICT (roster_reference, season) DO UPDATE SET ineligible = true",
            (link["roster_reference"], str(season["id"])),
        )
    conn.commit()


def _login_id_matches(conn, account_id, login_id) -> bool:
    try:
        normalized = normalize_login_id(login_id)
    except ValueError:
        return False
    credential = migrate.fetch_one(
        conn,
        "SELECT verifier FROM login_credentials"
        " WHERE account_id = %s AND revoked_at IS NULL",
        (account_id,),
    )
    if credential is None:
        return False
    return verify_login_id(normalized, credential["verifier"])
