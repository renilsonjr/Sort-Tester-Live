"""One-time local owner bootstrap (issue #47).

The owner role is sole and is designated by a command run on the server
machine, never by a public request (security/operations design). There is
deliberately no HTTP route for this.

    python -m backend.auth.owner designate --tag A1B2C3
    python -m backend.auth.owner show

``show`` answers "which account is the owner here?", which is a fair
question on a server you set up weeks ago, and it is also how you check
that a fresh deployment has no owner yet. It reads; it changes nothing.
"""
import argparse
import sys

from backend.db import migrate, settings


class OwnerError(Exception):
    """The owner could not be designated; nothing was changed."""


class OwnerExistsError(OwnerError):
    """An owner account already exists."""


class AccountNotFoundError(OwnerError):
    """No active account has that tag."""


def is_active_owner(conn, account_id) -> bool:
    """Whether this account is the owner right now.

    The one place this question is put to the database. An owner action
    asks it again inside its own transaction instead of trusting what a
    session said earlier. Deletion is a timestamp, not a DELETE, so the
    row of a deleted owner still says is_owner = true: it must not count. Each
    caller raises its own error; this only answers.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT 1 AS ok FROM accounts"
        " WHERE id = %s AND is_owner = true AND deleted_at IS NULL",
        (account_id,),
    )
    return row is not None


def designate_owner(conn, tag: str) -> dict:
    """Make the active account with ``tag`` the owner; return its id,
    username and tag. Refuses, changing nothing, when an owner exists or no
    active account has the tag."""
    existing = migrate.fetch_one(
        conn, "SELECT tag FROM accounts WHERE is_owner FOR UPDATE"
    )
    if existing is not None:
        conn.rollback()
        raise OwnerExistsError(f"an owner already exists (tag {existing['tag']})")
    account = migrate.fetch_one(
        conn,
        "SELECT id, username, tag FROM accounts"
        " WHERE upper(tag) = upper(%s) AND deleted_at IS NULL FOR UPDATE",
        (tag.strip(),),
    )
    if account is None:
        conn.rollback()
        raise AccountNotFoundError(f"no active account has tag {tag.strip()}")
    try:
        migrate.execute(
            conn, "UPDATE accounts SET is_owner = true WHERE id = %s", (account["id"],)
        )
    except migrate.IntegrityError:
        # another designation won the race; the database allows one owner
        conn.rollback()
        raise OwnerExistsError("an owner already exists") from None
    conn.commit()
    return {"account_id": account["id"], "username": account["username"], "tag": account["tag"]}


def current_owner(conn) -> dict | None:
    """The owner account, or ``None`` when none has been designated.

    Carries the username and tag only: this answers who holds the role,
    not anything about how they have played.
    """
    return migrate.fetch_one(
        conn,
        "SELECT id, username, tag FROM accounts"
        " WHERE is_owner AND deleted_at IS NULL",
    )


def reissue_owner_login_id(conn) -> dict:
    """Issue the owner a new login ID, revoking the old credential and
    every session. Returns the new login ID; it is shown once.

    The owner cannot use the in-app recovery, because that needs an owner
    session and the locked-out owner has none. Without this, an owner who
    lost their login ID could only be rescued by editing the database by
    hand. It asks for no secret because it cannot: the one it would check
    is the one that was lost. What stands in its place is the same thing
    that guards ``designate`` -- being on the server machine.

    It restores access to the same account and nothing else: no points
    change, no history is opened, and the old login ID is never disclosed,
    because only its hash was ever stored.
    """
    from backend.auth.service import issue_new_login_id

    owner = migrate.fetch_one(
        conn,
        "SELECT id, username, tag FROM accounts"
        " WHERE is_owner AND deleted_at IS NULL FOR UPDATE",
    )
    if owner is None:
        conn.rollback()
        raise AccountNotFoundError("no owner has been designated")
    login_id = issue_new_login_id(conn, owner["id"])
    conn.commit()
    return {
        "username": owner["username"],
        "tag": owner["tag"],
        "login_id": login_id,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.auth.owner",
        description="Owner account commands (run on the server machine).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    designate = commands.add_parser("designate", help="make an account the owner")
    designate.add_argument("--tag", required=True, help="the account's tag, e.g. A1B2C3")
    commands.add_parser("show", help="say which account is the owner")
    commands.add_parser(
        "reissue-login-id",
        help="issue the owner a new login ID, for an owner who lost theirs",
    )
    args = parser.parse_args(argv)

    conn = migrate.connect(settings.app_database_url())
    try:
        if args.command == "show":
            owner = current_owner(conn)
            if owner is None:
                print("No owner has been designated.")
                return 0
            print(f"Owner is {owner['username']} (tag {owner['tag']}).")
            return 0
        if args.command == "reissue-login-id":
            result = reissue_owner_login_id(conn)
            print(
                f"New Quiz Code for {result['username']} (tag {result['tag']}):"
                f"\n\n    {result['login_id']}\n\n"
                "It is shown once and cannot be recovered. Every session of"
                " that account has been signed out."
            )
            return 0
        result = designate_owner(conn, args.tag)
    except OwnerError as exc:
        print(f"Refused: {exc}. Nothing was changed.", file=sys.stderr)
        return 1
    finally:
        conn.close()
    print(f"Owner is now {result['username']} (tag {result['tag']}).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
