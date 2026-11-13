"""Migrate the APPLICATION database to the latest revision (issue #75).

Usage (from the repository root):

    SORT_TESTER_DATABASE_URL=postgresql://... \\
        python -m backend.db.upgrade_app --confirm <database name>

Guards, all checked before any connection is made:
- the URL comes only from SORT_TESTER_DATABASE_URL (never the test URL);
- --confirm must repeat the target database name exactly;
- the unittest scratch database is refused (it has its own tooling).

Only upgrades are offered; there is no downgrade from this command.
The password is never printed.
"""
import argparse
import os
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
    return {
        "database": database,
        "host": parameters.get("host") or "localhost",
        "port": parameters.get("port") or "5432",
    }


def _safe(message: str, url: str) -> str:
    """Remove the URL (and so its password) from an error message."""
    return message.replace(url, "<database url>")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m backend.db.upgrade_app",
        description="Migrate the application database to the latest revision.",
    )
    parser.add_argument("--confirm", metavar="DATABASE",
                        help="repeat the target database name to confirm")
    args = parser.parse_args(argv)

    url = os.environ.get(settings.APP_ENV_VAR, "").strip()
    try:
        if not url:
            raise _Refused(f"{settings.APP_ENV_VAR} is not set.")
        target = _target(url)
        if args.confirm is None:
            raise _Refused(
                f"Target is {target['database']} on {target['host']}:{target['port']}. "
                f"Re-run with --confirm {target['database']} to migrate it."
            )
        if args.confirm != target["database"]:
            raise _Refused(
                f"--confirm {args.confirm!r} does not match the target database "
                f"{target['database']!r}; nothing was changed."
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
