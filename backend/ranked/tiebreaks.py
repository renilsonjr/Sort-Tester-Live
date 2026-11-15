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

import secrets
from dataclasses import dataclass
from datetime import timedelta

from backend.db import migrate
from backend.ranked import standings
from backend.ranked.versions import materialize_question_version

HATS = 3
ROUND_WINDOW = timedelta(hours=24)
QUESTIONS_PER_ROUND = 5

# Unpredictable rather than reproducible: a player who could work out the
# next round's questions from the last one would have them before the
# round opened. Tests pass their own generator.
_SYSTEM_RANDOM = secrets.SystemRandom()


class NoFreshSet(Exception):
    """Fewer than five unused Hard questions remain this season.

    Settled Decisions 9-10: the affected prize places then wait for the
    owner's selection. Questions are never reused and content is never
    approved on the fly to fill the gap.
    """


def _hard_questions(bank):
    return [q for q in bank.questions if q.difficulty.lower() == "hard"]


def fresh_questions(conn, season_id, bank) -> list:
    """The Hard questions no tie-break round of this season has used yet,
    valid or voided alike, since every one of them was seen by players."""
    used = {
        row["bank_key"]
        for row in migrate.fetch_all(
            conn,
            "SELECT bank_key FROM tiebreak_round_questions WHERE season_id = %s",
            (season_id,),
        )
    }
    return [q for q in _hard_questions(bank) if q.canonical_id not in used]


def assign_round_questions(conn, round_id, season_id, bank, *, rng=None) -> list:
    """Give a round its five shared questions, or raise ``NoFreshSet``.

    Does not commit. The schema refuses a reused question even if this code
    were wrong, so a race between two rounds fails loudly instead of
    quietly handing both the same question.
    """
    pool = fresh_questions(conn, season_id, bank)
    if len(pool) < QUESTIONS_PER_ROUND:
        raise NoFreshSet()
    chosen = (rng or _SYSTEM_RANDOM).sample(pool, QUESTIONS_PER_ROUND)
    for seq, question in enumerate(chosen, start=1):
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_round_questions"
            " (round_id, seq, question_version_id, season_id, bank_key)"
            " VALUES (%s, %s, %s, %s, %s)",
            (
                round_id,
                seq,
                materialize_question_version(conn, question),
                season_id,
                question.canonical_id,
            ),
        )
    return chosen


def fresh_sets_left(conn, season_id, bank) -> int:
    """How many more rounds this season can still be given fresh questions."""
    return len(fresh_questions(conn, season_id, bank)) // QUESTIONS_PER_ROUND


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


def open_prize_tiebreaks(conn, season_id, *, clock, bank=None, rng=None):
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
    if bank is None:
        from backend.ranked_bank.catalog import load_reviewed_bank

        bank = load_reviewed_bank()
    if fresh_sets_left(conn, season_id, bank) == 0:
        # No round can be played, so none is opened: the places wait for
        # the owner, which is the settled fallback, not a failure.
        migrate.execute(
            conn,
            "UPDATE tiebreak_groups SET status = 'owner_selection' WHERE id = %s",
            (group_id,),
        )
        return group_id
    round_id = migrate.fetch_one(
        conn,
        "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at)"
        " VALUES (%s, 1, %s, %s) RETURNING id",
        (group_id, now, deadline),
    )["id"]
    assign_round_questions(conn, round_id, season_id, bank, rng=rng)
    return group_id
