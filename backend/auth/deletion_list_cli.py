"""Read the deletion list during a database restore (issue #13).

    python -m backend.auth.deletion_list_cli --after 2026-11-19T21:50:00Z

Prints every accepted deletion at or after the restore point, oldest first,
one per line: ``<account id><TAB><deletion time>``. Those are the deletions
``infra/azure/restore-runbook.md`` step 4 must re-apply.

It is meant to be run inside the app's container (``az containerapp exec``),
which is inside the private network and already holds the identity that may
read the list. It only reads: it never changes a note, and it does not touch
the database, so it works while the database is being restored.

Exit codes: 0 the list was read in full; 1 it could not be read, and nothing
was printed; 2 bad arguments; 3 it was read but some notes are malformed --
the readable ones are printed, the others are named on stderr and must be
looked at by hand before the restore is trusted.
"""
import argparse
import sys
from datetime import datetime

from backend.auth import deletion_list


def _restore_point(text: str) -> datetime:
    try:
        moment = datetime.fromisoformat(text.strip().replace("Z", "+00:00"))
    except ValueError:
        raise argparse.ArgumentTypeError("not an ISO 8601 time") from None
    if moment.tzinfo is None:
        raise argparse.ArgumentTypeError("the restore point must carry a timezone, e.g. a trailing Z")
    return moment


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="deletion_list_cli", description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--after",
        required=True,
        type=_restore_point,
        metavar="RESTORE_POINT",
        help="the restore point, ISO 8601 with timezone (2026-11-19T21:50:00Z)",
    )
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return 2 if stop.code else 0

    try:
        notes, unreadable = deletion_list.notes()
    except deletion_list.DeletionListConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    except deletion_list.DeletionListUnavailable as error:
        print(f"error: {error}; nothing was printed, do not treat this as an empty list", file=sys.stderr)
        return 1

    # ">=": a deletion in the very instant of the restore point may or may not
    # be in the backup. Re-applying one twice is harmless; missing one is not.
    wanted = sorted(
        (note for note in notes if note.deleted_at >= args.after),
        key=lambda note: note.deleted_at,
    )
    for note in wanted:
        print(f"{note.account_id}\t{note.deleted_at.isoformat()}")
    print(
        f"{len(wanted)} of {len(notes)} readable notes are at or after {args.after.isoformat()}",
        file=sys.stderr,
    )
    if unreadable:
        print(
            f"WARNING: {len(unreadable)} malformed note(s), not included above; "
            "inspect before trusting the restore:",
            file=sys.stderr,
        )
        for name in unreadable:
            print(f"  {name}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
