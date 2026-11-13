"""One-time local owner bootstrap (issue #47).

The owner role is sole and is designated by a command run on the server
machine, never by a public request (security/operations design). There is
deliberately no HTTP route for this.

    python -m backend.auth.owner designate --tag A1B2C3
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.auth.owner",
        description="Designate the sole owner account (run on the server machine).",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    designate = commands.add_parser("designate", help="make an account the owner")
    designate.add_argument("--tag", required=True, help="the account's tag, e.g. A1B2C3")
    args = parser.parse_args(argv)

    conn = migrate.connect(settings.app_database_url())
    try:
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
