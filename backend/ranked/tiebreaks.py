"""Prize tie-breaks: finding the ties that need one, and opening round 1
(issue #24, slice 1).

The owner's rule, settled 2026-11-15: **a quiz runs only when more players
are competing for the three hats than there are hats.** Players tied
inside the top three share their place and all take a hat; nobody plays a
quiz that cannot change who wins something.

In practice: take the eligible standings, find the score of the player in
third position, and count how many players have at least that score. Three
or fewer, and every one of them wins outright. More than three, and the
players **at** that score form a tie group competing for the hats left over
once everybody strictly above has taken theirs.

    900, 900, 800, 700  ->  places 1, 1, 3: three winners, no quiz
    900, 800, 700, 700  ->  places 1, 2, 3, 3: the two at 700 play for one hat
    900, 900, 900, 900  ->  four players for three hats: all four play

Fewer than three eligible players means fewer hats and no quiz (settled
Q14: never fabricate winners).

Round 1's deadline is the season's **scheduled** close plus 24 hours, as
the record words it, not the moment the freeze happened to run. The round
opens at the freeze, because that is when every eligible attempt has
settled and the tied score is final.
"""

from dataclasses import dataclass
from datetime import timedelta

from backend.db import migrate
from backend.ranked import standings

HATS = 3
ROUND_WINDOW = timedelta(hours=24)


@dataclass(frozen=True)
class PrizeTie:
    tied_points: int
    hats_available: int
    account_ids: tuple


def prize_tie(rows) -> PrizeTie | None:
    """The tie that needs a quiz in these standings, or ``None``.

    ``rows`` is the eligible standings, best first, as
    ``backend.ranked.standings.standings`` returns them. Pure: no database.
    """
    if len(rows) <= HATS:
        return None
    cut = rows[HATS - 1].points
    contenders = [row for row in rows if row.points >= cut]
    if len(contenders) <= HATS:
        return None
    above = sum(1 for row in rows if row.points > cut)
    tied = tuple(row.account_id for row in rows if row.points == cut)
    return PrizeTie(tied_points=cut, hats_available=HATS - above, account_ids=tied)


def open_prize_tiebreaks(conn, season_id, *, clock):
    """Open the season-close tie group and its round 1, when one is needed.

    Called inside the freeze's transaction, so the freeze and the group
    are written together or not at all. Safe to call again: a season has
    at most one season-close group. Returns the group id, or ``None`` when
    the standings need no quiz. Does not commit.
    """
    season = migrate.fetch_one(
        conn,
        "SELECT phase, closes_at, closed_at FROM seasons WHERE id = %s",
        (season_id,),
    )
    if season is None or season["phase"] != "official":
        return None  # Pre-Season awards no hats
    existing = migrate.fetch_one(
        conn,
        "SELECT id FROM tiebreak_groups"
        " WHERE season_id = %s AND reason = 'season_close'",
        (season_id,),
    )
    if existing is not None:
        return existing["id"]
    tie = prize_tie(standings.standings(conn, season_id))
    if tie is None:
        return None
    scheduled_close = season["closes_at"] or season["closed_at"]
    now = clock.now()
    group_id = migrate.fetch_one(
        conn,
        "INSERT INTO tiebreak_groups"
        " (season_id, reason, tied_points, hats_available, opened_at)"
        " VALUES (%s, 'season_close', %s, %s, %s) RETURNING id",
        (season_id, tie.tied_points, tie.hats_available, now),
    )["id"]
    for account_id in tie.account_ids:
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
            (group_id, account_id),
        )
    deadline = scheduled_close + ROUND_WINDOW
    if deadline <= now:
        # The freeze ran so late that the scheduled deadline has passed. The
        # record says the first deadline is the scheduled close plus 24h, so
        # it is not stretched; but a round must be playable, so it gets the
        # full window from now. Recorded on the round, not hidden.
        deadline = now + ROUND_WINDOW
    migrate.execute(
        conn,
        "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at)"
        " VALUES (%s, 1, %s, %s)",
        (group_id, now, deadline),
    )
    return group_id
