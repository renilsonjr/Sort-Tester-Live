"""Recording the owner's prize-eligibility approval (issue #11, slice 1).

The standings read this decision (``backend/ranked/standings.py``); until
now nothing wrote it, so the only way to approve a sorter was to edit the
database by hand. This module is that missing half, and deliberately
nothing more.

What the owner's settled Q5 allows here, and what it refuses:

* Only the owner approves. There is no delegation: an owner flag is the
  whole authority, and nobody else can record or withdraw an approval.
* The owner cannot approve themselves. Being the person who decides and
  the person who wins is the one combination the rule cannot allow.
* An approval is for one sorter and one account: the roster reference is
  who they are on the owner's roster, and the schema allows it once
  (migration 0024).
* It must be recorded while the season is open. From the season's end
  onward, including the finishing window, no new approval is admitted
  (#23). A player approved before the end who finishes a quiz inside the
  window still qualifies, because the attempt keeps the season it began in.
* Approving changes no points, no badge and no history, and gives the
  owner no access to anybody's private history. Nothing here reads a quiz
  result or a support case.

Withdrawing is the counterpart: the owner can remove an approval they
should not have recorded, which takes that account out of the standings
and changes nothing else about it.
"""

from dataclasses import dataclass
from uuid import UUID

from backend.db import migrate
from backend.ranked import seasons
# The same two kinds of attempt the standings count: a tie-break alone
# never satisfied the one-completed-quiz minimum, so it cannot stand for
# accumulation here either.
from backend.ranked.standings import QUALIFYING_MODES


class EligibilityError(Exception):
    """A refusal with a reason the caller may show. Never says more about
    an account than the person asking already knows."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class Approval:
    account_id: UUID
    username: str
    tag: str
    roster_reference: str
    established_at: object


def _require_owner(conn, owner_account_id: UUID) -> None:
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM accounts"
        " WHERE id = %s AND is_owner = true AND deleted_at IS NULL",
        (owner_account_id,),
    )
    if row is None:
        raise EligibilityError("Only the owner may approve prize eligibility.")


def account_id_for_tag(conn, tag: str) -> UUID:
    """Resolve the tag the owner typed to an account.

    The owner works from a tag, because that is what a sorter can read off
    their own profile and say out loud; account ids are not something
    anybody carries around. A leading ``#`` and the surrounding space are
    what people type, so they are accepted rather than refused, and the
    answer is only yes-or-no: this returns an id or raises, and never
    reports anything else about the account.
    """
    cleaned = (tag or "").strip().lstrip("#").strip().upper()
    if not cleaned:
        raise EligibilityError("A player tag is required.")
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM accounts WHERE tag = %s AND deleted_at IS NULL",
        (cleaned,),
    )
    if row is None:
        raise EligibilityError("No account with that tag.")
    return row["id"]


def _refuse_a_second_account_for_this_sorter(
    conn, reference: str, account_id: UUID
) -> None:
    """The approved account is fixed for the official season (settled Q5).

    Withdrawing an approval is still allowed, because the owner must be
    able to take back one that should not stand. What may not follow is a
    **swap**: approving a different account for the same sorter once the
    first one has played, which would move eligibility onto a balance it
    did not earn. So a second account is refused when the sorter already
    has an official-season record under this reference, by either route:

    * a completed quiz on the account that was withdrawn, which is the
      accumulation the rule exists to stop; or
    * a season marker, written when an account is deleted. Deletion
      withdraws the account from the season and a fresh one "cannot regain
      this season's prizes", and the marker says so after the account
      itself is gone.

    Correcting a mistyped tag stays possible, because a tag approved by
    mistake and withdrawn straight away has neither.
    """
    marker = migrate.fetch_one(
        conn,
        "SELECT ineligible FROM season_markers"
        " WHERE roster_reference = %s AND ineligible = true",
        (reference,),
    )
    if marker is not None:
        raise EligibilityError(
            "That sorter is out of this season and cannot be approved again."
        )
    played = migrate.fetch_one(
        conn,
        """
        SELECT 1 AS played
        FROM withdrawn_approvals wa
        JOIN attempts at ON at.account_id = wa.account_id
        WHERE wa.roster_reference = %s
          -- putting the same account back is not a move, so it is not
          -- the withdrawn account's own quizzes that block it
          AND wa.account_id <> %s
          AND at.state = 'finalized'
          AND at.final_outcome = 'completed'
          AND at.mode = ANY(%s)
        LIMIT 1
        """,
        (reference, account_id, list(QUALIFYING_MODES)),
    )
    if played is not None:
        raise EligibilityError(
            "That sorter has already played this season on another account,"
            " so the approval cannot move."
        )


def approve(
    conn,
    owner_account_id: UUID,
    account_id: UUID,
    roster_reference: str,
    *,
    clock,
) -> Approval:
    """Record that this account is the one approved for that sorter."""
    _require_owner(conn, owner_account_id)
    reference = (roster_reference or "").strip()
    if not reference:
        raise EligibilityError("A roster reference is required.")
    if len(reference) > 128:
        raise EligibilityError("That roster reference is too long.")
    if account_id == owner_account_id:
        raise EligibilityError("The owner cannot approve their own account.")
    if not seasons.approvals_open(conn, clock.now()):
        raise EligibilityError(
            "The season is no longer open, so no new approval can be recorded."
        )
    target = migrate.fetch_one(
        conn,
        "SELECT id, username, tag FROM accounts"
        " WHERE id = %s AND deleted_at IS NULL",
        (account_id,),
    )
    if target is None:
        raise EligibilityError("No such account.")
    _refuse_a_second_account_for_this_sorter(conn, reference, account_id)
    existing = migrate.fetch_one(
        conn,
        "SELECT account_id, roster_reference FROM participant_links"
        " WHERE account_id = %s OR roster_reference = %s",
        (account_id, reference),
    )
    if existing is not None:
        if existing["account_id"] == account_id:
            raise EligibilityError("That account is already approved.")
        raise EligibilityError(
            "That sorter already has an approved account. Withdraw it first."
        )
    row = migrate.fetch_one(
        conn,
        "INSERT INTO participant_links (account_id, roster_reference)"
        " VALUES (%s, %s) RETURNING established_at",
        (account_id, reference),
    )
    return Approval(
        account_id=target["id"],
        username=target["username"],
        tag=target["tag"],
        roster_reference=reference,
        established_at=row["established_at"],
    )


def withdraw(conn, owner_account_id: UUID, account_id: UUID) -> None:
    """Remove an approval. The account keeps its points, badge and history
    and may go on playing; it simply leaves the standings."""
    _require_owner(conn, owner_account_id)
    removed = migrate.fetch_one(
        conn,
        "DELETE FROM participant_links WHERE account_id = %s"
        " RETURNING account_id, roster_reference",
        (account_id,),
    )
    if removed is None:
        raise EligibilityError("That account is not approved.")
    # Remember that this sorter held this account, so that approving a
    # different one for them later can tell a correction from a swap.
    migrate.execute(
        conn,
        "INSERT INTO withdrawn_approvals (account_id, roster_reference)"
        " VALUES (%s, %s)"
        " ON CONFLICT (account_id, roster_reference) DO NOTHING",
        (removed["account_id"], removed["roster_reference"]),
    )


def approvals(conn, owner_account_id: UUID) -> list[Approval]:
    """Every approval the owner has recorded, for the owner's own screen.

    Carries the account's public name and tag and the roster reference the
    owner typed. No points, no history, no support case: approving is not
    a way into anybody's record.
    """
    _require_owner(conn, owner_account_id)
    rows = migrate.fetch_all(
        conn,
        "SELECT a.id, a.username, a.tag, pl.roster_reference, pl.established_at"
        " FROM participant_links pl"
        " JOIN accounts a ON a.id = pl.account_id"
        " WHERE a.deleted_at IS NULL"
        " ORDER BY pl.established_at",
    )
    return [
        Approval(
            account_id=row["id"],
            username=row["username"],
            tag=row["tag"],
            roster_reference=row["roster_reference"],
            established_at=row["established_at"],
        )
        for row in rows
    ]
