"""Migrate the APPLICATION database to the latest revision (issue #75).

Usage (from the repository root):

    SORT_TESTER_DATABASE_URL=postgresql://... \\
        python -m backend.db.upgrade_app --confirm <database>@<host>:<port>

Guards, all checked before any connection is made:
- the URL comes only from SORT_TESTER_DATABASE_URL (never the test URL);
- --confirm must repeat the target as `database@host:port`, because
  staging and production call their database the same thing;
- the unittest scratch database is refused (it has its own tooling).

Only upgrades are offered; there is no downgrade from this command.
The password is never printed.
"""
import argparse
import os
import re
import sys

import psycopg
from psycopg.conninfo import conninfo_to_dict

from backend.db import migrate, settings


class _Refused(Exception):
    """A guard failed; nothing was touched."""


def _target(url: str) -> dict:
    """Return host, port and database of *url*, or refuse."""
    if not url.startswith("postgresql://"):
        raise _Refused(f"{settings.APP_ENV_VAR} must be a postgresql:// URL.")
    try:
        parameters = conninfo_to_dict(url)
    except (psycopg.Error, ValueError):
        raise _Refused(f"{settings.APP_ENV_VAR} is not a valid PostgreSQL URL.") from None
    database = parameters.get("dbname") or ""
    if not database:
        raise _Refused(f"{settings.APP_ENV_VAR} must name a database.")
    if database == settings.SCRATCH_DB_NAME:
        raise _Refused(
            f"{database} is the unittest scratch database; it is migrated by the "
            "test tooling, not by this command."
        )
    if database == "postgres":
        # every server has one, and a DSN that lost its dbname falls back
        # to it silently; it is never ours to migrate (audit L7)
        raise _Refused(
            "postgres is the server's maintenance database, not an application "
            "database; check that the URL names the database you mean."
        )
    return {
        "database": database,
        "host": parameters.get("host") or "localhost",
        "port": parameters.get("port") or "5432",
    }


def _confirmation_for(target: dict) -> str:
    """What --confirm has to repeat back (audit L7).

    The database name alone was not proof of anything: staging and
    production call theirs the same thing, so typing it proved only that
    the operator knew what it was called, not where it pointed.
    """
    return f"{target['database']}@{target['host']}:{target['port']}"


_CREDENTIALS = re.compile(r"//[^/\s@]*:[^/\s@]*@")


def _safe(message: str, url: str) -> str:
    """Remove any credentials from an error message (audit L8).

    The exact-string replace this used to do only worked when the URL
    psycopg names in its error is character-for-character the one we hold.
    It usually is not: psycopg reorders parameters, appends `sslmode`, and
    a percent-encoded password comes back in a different form. The replace
    then quietly did nothing while looking like a redaction, and deploy
    logs are kept.

    So the password is removed by shape, wherever it appears. The rest of
    the message is left alone -- a redaction that eats the whole text
    helps nobody work out what failed.
    """
    message = message.replace(url, "<database url>")
    return _CREDENTIALS.sub("//<credentials>@", message)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.db.upgrade_app",
        description="Migrate the application database to the latest revision.",
    )
    parser.add_argument("--confirm", metavar="DATABASE@HOST:PORT",
                        help="repeat the full target to confirm")
    args = parser.parse_args(argv)

    url = os.environ.get(settings.APP_ENV_VAR, "").strip()
    try:
        if not url:
            raise _Refused(f"{settings.APP_ENV_VAR} is not set.")
        target = _target(url)
        expected = _confirmation_for(target)
        if args.confirm is None:
            raise _Refused(
                f"Target is {expected}. Re-run with --confirm {expected} to "
                "migrate it."
            )
        if args.confirm != expected:
            raise _Refused(
                f"--confirm {args.confirm!r} does not match the target "
                f"{expected!r}; nothing was changed."
            )
    except _Refused as refusal:
        print(f"Refused: {refusal}", file=sys.stderr)
        return 2

    print(f"Target: {target['database']} on {target['host']}:{target['port']}")
    try:
        before = migrate.current_revision(url)
        print(f"Revision before: {before or 'none (empty database)'}")
        migrate.upgrade_to_head(url)
        after = migrate.current_revision(url)
    except Exception as error:  # report any failure without leaking the URL
        print(f"Migration failed: {_safe(str(error), url)}", file=sys.stderr)
        return 1
    print(f"Revision after: {after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
