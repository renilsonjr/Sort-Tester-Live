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

from backend.auth import deletion_list
from backend.auth.credentials import normalize_login_id, verify_login_id
from backend.db import migrate


class DeletionError(Exception):
    """The deletion was refused; nothing was changed."""


class WrongLoginIdError(DeletionError):
    """The login ID does not belong to this account."""


class OwnerAccountError(DeletionError):
    """The sole owner account cannot be deleted."""


class NotOwnerError(DeletionError):
    """Only the owner may delete somebody else's account."""


class NoSuchAccountError(DeletionError):
    """There is no active account with that id."""


class _SystemClock:
    def now(self):
        return datetime.now(timezone.utc)


def request_deletion(conn, account_id, login_id: str, *, clock=None) -> None:
    """Accept the account's own deletion request, in one transaction.

    Refuses the owner and a wrong login ID, changing nothing. Otherwise marks
    the account pending purge, revokes its sessions and login credentials,
    removes its unfinished attempts without fabricating a score, and keeps a
    season marker if the account has a participant link.

    Before any of that, the deletion is noted outside the database
    (``deletion_list``), so a later restore can re-apply it. If the note
    cannot be written the deletion is refused with
    ``DeletionListUnavailable`` and nothing changes; if the database then
    fails, the note is removed again.
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

    _apply_deletion(conn, account_id, now)


def _apply_deletion(conn, account_id, now) -> None:
    """Mark the account deleted and close everything it can act with.

    The one place the deletion itself happens, whether the player asked
    (``request_deletion``) or the owner did (``owner_delete``, #271). The note
    outside the database comes first, so a restore re-applies the deletion; if
    the database then fails, the note is removed again.
    """
    try:
        deletion_list.record(account_id, now)
    except deletion_list.DeletionListUnavailable:
        conn.rollback()
        raise
    try:
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
    except BaseException:
        conn.rollback()
        deletion_list.forget(account_id)
        raise


def _require_owner(conn, owner_account_id) -> None:
    owner = migrate.fetch_one(
        conn,
        "SELECT is_owner FROM accounts WHERE id = %s AND deleted_at IS NULL",
        (owner_account_id,),
    )
    if owner is None or not owner["is_owner"]:
        conn.rollback()
        raise NotOwnerError("only the owner may do this")


def _active_account(conn, account_id, *, lock: bool):
    return migrate.fetch_one(
        conn,
        "SELECT username, tag, is_owner, deleted_at FROM accounts WHERE id = %s"
        + (" FOR UPDATE" if lock else ""),
        (account_id,),
    )


def describe_for_owner(conn, owner_account_id, account_id) -> dict:
    """What the owner is about to remove, for the confirmation screen (#271).

    Deliberately narrow: the name and tag the owner must check against the
    person in front of them, and two facts that say whether this deletion
    changes anything else -- how many finished Ranked attempts it takes off
    the leaderboard, and whether the account was approved for prizes. Not a
    player lookup: no points, no history, no answers, and the caller must
    already know the tag. Reading changes nothing.
    """
    _require_owner(conn, owner_account_id)
    account = _active_account(conn, account_id, lock=False)
    if account is None or account["deleted_at"] is not None:
        conn.rollback()
        raise NoSuchAccountError("no such active account")
    finished = migrate.fetch_one(
        conn,
        "SELECT COUNT(*) AS n FROM attempts"
        " WHERE account_id = %s AND state = 'finalized'",
        (account_id,),
    )["n"]
    approved = migrate.fetch_one(
        conn,
        "SELECT 1 AS yes FROM participant_links WHERE account_id = %s",
        (account_id,),
    )
    conn.commit()
    return {
        "username": account["username"],
        "tag": account["tag"],
        "is_owner": account["is_owner"],
        "finished_attempts": finished,
        "approved_for_prizes": approved is not None,
    }


def owner_delete(conn, owner_account_id, account_id, *, clock=None) -> None:
    """Delete somebody else's account, on the owner's say-so (#271).

    The same deletion the player can ask for, authorised differently: the
    owner does not have the player's Quiz Code, so the caller's own ownership
    is what is checked here. The HTTP layer additionally demands the owner's
    Quiz Code re-entered on this device, so a borrowed signed-in phone is not
    enough.

    Refuses a caller who is not the owner, the owner's own account, and an
    account that is already deleted -- changing nothing in each case.
    """
    now = (clock or _SystemClock()).now()
    _require_owner(conn, owner_account_id)
    account = _active_account(conn, account_id, lock=True)
    if account is None or account["deleted_at"] is not None:
        conn.rollback()
        raise NoSuchAccountError("no such active account")
    if account["is_owner"]:
        conn.rollback()
        raise OwnerAccountError("the sole owner account cannot be deleted")
    _apply_deletion(conn, account_id, now)


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


def purge_deleted_accounts(conn) -> int:
    """Delete every account pending deletion; return how many.

    The database cascades remove everything the account owns: credentials,
    sessions, participant link, balance, attempts and their answers,
    settlements, balance history, connection events and flags. Season markers
    have no account key and stay; shared question versions and other players'
    records are untouched. When nothing is pending this is a single statement.
    """
    rows = migrate.fetch_all(
        conn, "DELETE FROM accounts WHERE deleted_at IS NOT NULL RETURNING id"
    )
    conn.commit()
    return len(rows)
