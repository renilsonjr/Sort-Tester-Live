"""Who is in the official competition, and in what order (issue #12, slice 1).

This module answers one question — "what does the leaderboard show?" — and
nothing else. It starts no attempt, awards no prize and writes nothing; the
screen and its endpoint are built on top of it.

The eligibility rules are the owner's settled Q5, not choices made here:

* Only sorters in Primary Sort on the Twilight shift at Saddle Brook may win
  the hats. That approval is a row in ``participant_links``, established by
  the owner before the season closes; this module never decides who is
  approved, it only reads the decision.
* An approved player must also have **one valid completed Ranked quiz
  credited to the official season**. A negative score still counts: the rule
  is about finishing a quiz, not about doing well at one. Pre-Season,
  void, unfinished and tie-break attempts do not qualify, so the only
  attempts that count are ordinary or promotion ones, finalized, with the
  outcome ``completed``, in the official season.
* Everyone else may play and see their own points and badge; they simply
  have no competition position. Being left out of the standings is not a
  penalty and changes nobody's points.

Order is current points, highest first (settled Q6: the old
first-reached-score fallback was superseded by tie-break quizzes, so there
is no timestamp here and none may be added). Players on the same points
share a place and the next place skips, as the approved mockup shows. That
shared number is the honest statement: this module does not know which of
two tied players is ahead, and must not invent it. Deciding a tie that
affects a prize is a tie-break quiz, which is #24's work, not a sort order.
"""

from dataclasses import dataclass
from uuid import UUID

from backend.db import migrate
from backend.ranked import ranks

# The attempt outcomes that satisfy the one-completed-quiz minimum. Only
# 'completed' is a completed quiz: 'season_close' is an attempt the close
# ended for the player, 'quit' and 'disconnect' speak for themselves, and
# 'launch_reset' and 'outage_void' are attempts that never counted at all.
QUALIFYING_OUTCOME = "completed"

# Tie-break attempts never satisfy the minimum on their own (settled Q5), so
# only the two kinds of season quiz are counted.
QUALIFYING_MODES = ("normal", "promotion")


@dataclass(frozen=True)
class Standing:
    """One row of the board. Nothing private is carried here on purpose."""

    place: int
    account_id: UUID
    username: str
    tag: str
    points: int
    badge: str
    tied: bool


def eligible_accounts(conn, season_id) -> list[UUID]:
    """The accounts the official competition includes, unordered.

    Approved by the owner, not deleted, and with at least one valid
    completed quiz in this season.
    """
    rows = migrate.fetch_all(
        conn,
        """
        SELECT a.id
        FROM accounts a
        JOIN participant_links pl ON pl.account_id = a.id
        WHERE a.deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM attempts at
            WHERE at.account_id = a.id
              AND at.season_id = %s
              AND at.state = 'finalized'
              AND at.final_outcome = %s
              AND at.mode = ANY(%s)
          )
        """,
        (season_id, QUALIFYING_OUTCOME, list(QUALIFYING_MODES)),
    )
    return [row["id"] for row in rows]


def standings(conn, season_id) -> list[Standing]:
    """The board, best first, with shared places for equal points.

    A player with no balance row has not scored yet and stands at 0, which
    is what the rest of the app shows them too.
    """
    rows = migrate.fetch_all(
        conn,
        """
        SELECT a.id, a.username, a.tag, COALESCE(b.current_points, 0) AS points
        FROM accounts a
        JOIN participant_links pl ON pl.account_id = a.id
        LEFT JOIN balances b ON b.account_id = a.id
        WHERE a.deleted_at IS NULL
          AND EXISTS (
            SELECT 1 FROM attempts at
            WHERE at.account_id = a.id
              AND at.season_id = %s
              AND at.state = 'finalized'
              AND at.final_outcome = %s
              AND at.mode = ANY(%s)
          )
        -- username only steadies the listing when points are equal; it is
        -- not a ranking, and the two rows carry the same place number.
        ORDER BY points DESC, a.username ASC
        """,
        (season_id, QUALIFYING_OUTCOME, list(QUALIFYING_MODES)),
    )
    return place_rows(rows)


def place_rows(rows) -> list[Standing]:
    """Number an ordered listing: equal points share a place, then it skips.

    Three players on 900, 900 and 800 are first, first and third. Nobody is
    second, because saying so would claim one of the two tied players is
    ahead of the other.
    """
    standings_out: list[Standing] = []
    points_at_place: dict[int, int] = {}
    place = 0
    previous_points = None
    for index, row in enumerate(rows, start=1):
        points = row["points"]
        if points != previous_points:
            place = index
            previous_points = points
        points_at_place[place] = points_at_place.get(place, 0) + 1
        standings_out.append(
            Standing(
                place=place,
                account_id=row["id"],
                username=row["username"],
                tag=row["tag"],
                points=points,
                badge=ranks.badge_for(points),
                tied=False,
            )
        )
    # A row is tied when it shares its place with another row.
    return [
        Standing(**{**row.__dict__, "tied": points_at_place[row.place] > 1})
        for row in standings_out
    ]


def place_of(standings_rows: list[Standing], account_id) -> int | None:
    """This account's place, or ``None`` when it is not in the standings."""
    for row in standings_rows:
        if row.account_id == account_id:
            return row.place
    return None
