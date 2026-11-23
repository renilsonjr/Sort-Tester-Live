"""Account deletion: the player's own (issue #47) and the owner's (#271).

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


class WrongTagError(DeletionError):
    """The tag typed to confirm is not this account's tag."""


# the owner's list is capped like every other list the app serves
MAX_ROWS = 500


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

    _apply(conn, account_id, now)


def _apply(conn, account_id, now) -> None:
    """Do an accepted deletion. The one path for both who may ask for it:
    the account itself, or the owner (#271). The caller holds the row lock
    and has already refused whatever it must refuse."""
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


def _require_owner(conn, acting_account_id) -> None:
    row = migrate.fetch_one(
        conn,
        "SELECT 1 AS ok FROM accounts"
        " WHERE id = %s AND is_owner = true AND deleted_at IS NULL",
        (acting_account_id,),
    )
    if row is None:
        raise NotOwnerError("Only the owner may delete another account.")


def accounts_for_owner(conn, acting_account_id) -> list[dict]:
    """The accounts the owner may look through to find one to delete (#271).

    Deliberately thin: name, tag, when it was created, whether it is
    approved for prizes and whether it has finished a Ranked quiz. No
    points, no history and no last activity: the owner was never granted a
    player's record, and choosing an account to remove does not need one.
    """
    _require_owner(conn, acting_account_id)
    return migrate.fetch_all(
        conn,
        "SELECT a.id AS account_id, a.username, a.tag, a.created_at, a.is_owner,"
        " EXISTS (SELECT 1 FROM participant_links p WHERE p.account_id = a.id) AS approved,"
        " EXISTS (SELECT 1 FROM attempts t WHERE t.account_id = a.id"
        "         AND t.state = 'finalized') AS has_played"
        " FROM accounts a WHERE a.deleted_at IS NULL"
        f" ORDER BY a.created_at DESC, a.id LIMIT {MAX_ROWS}",
    )


def delete_by_owner(conn, acting_account_id, account_id, confirm_tag: str, *, clock=None) -> dict:
    """Delete somebody else's account on the owner's word (#271).

    The same deletion as the player's own, with one difference: what
    stands in for the player's login ID is the owner typing that account's
    tag, so a slip of the finger on a list cannot remove the wrong person.
    The owner check lives here and not only in the route, as it does for
    recording an outage: this removes an account for good.

    Returns the username and tag that were deleted, for the confirmation.
    """
    _require_owner(conn, acting_account_id)
    now = (clock or _SystemClock()).now()
    account = migrate.fetch_one(
        conn,
        "SELECT username, tag, is_owner, deleted_at FROM accounts WHERE id = %s FOR UPDATE",
        (account_id,),
    )
    if account is None or account["deleted_at"] is not None:
        conn.rollback()
        raise NoSuchAccountError("No such account.")
    if account["is_owner"]:
        conn.rollback()
        raise OwnerAccountError("the sole owner account cannot be deleted")
    typed = (confirm_tag or "").strip().lstrip("#").strip().upper()
    if typed != account["tag"]:
        conn.rollback()
        raise WrongTagError("The tag does not match this account.")
    _apply(conn, account_id, now)
    return {"username": account["username"], "tag": account["tag"]}


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
