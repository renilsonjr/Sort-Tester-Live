"""Account-private profile stats (issue #218).

Read-only reads for the Profile stats grid: the best correct-answer count
in one settled Ranked attempt, and the account's current leaderboard place.
Pure data access -- no HTTP, no clock. One account id in, never another.
"""
from backend.db import migrate
from backend.ranked import seasons
from backend.ranked import standings as ranked_standings

# A Ranked quiz is fifteen questions; the profile tile shows correct/15.
RANKED_QUIZ_LENGTH = 15

# Settled, score-bearing attempts only: ordinary and promotion quizzes that
# reached a real outcome. `state = 'finalized'` is the schema's own
# "settled" state (it requires settled_at). Voids (launch_reset,
# outage_void) are finalized too but excluded by the outcome filter;
# tie-breaks (mode 'tiebreak', hidden until a round closes) never match.
_BEST_RANKED_SQL = """
    SELECT MAX(c.correct) AS best
    FROM (
        SELECT aa.attempt_id,
               COUNT(*) FILTER (WHERE aa.outcome = 'correct') AS correct
        FROM attempt_answers aa
        JOIN attempts a ON a.id = aa.attempt_id
        WHERE a.account_id = %s
          AND a.state = 'finalized'
          AND a.mode IN ('normal', 'promotion')
          AND a.final_outcome IN ('completed', 'quit', 'disconnect', 'season_close')
        GROUP BY aa.attempt_id
    ) c
"""


def best_ranked_correct(conn, account_id) -> int | None:
    """Highest correct-answer count in one settled Ranked attempt, or None.

    None when the account has no settled Ranked attempt. The denominator is
    always :data:`RANKED_QUIZ_LENGTH`; the caller pairs this count with it.
    """
    row = migrate.fetch_one(conn, _BEST_RANKED_SQL, (account_id,))
    if row is None or row["best"] is None:
        return None
    return int(row["best"])


def leaderboard_place(conn, account_id) -> int | None:
    """The account's current official-standings place, or None.

    None in Pre-Season (no official launch) or when the account is not in
    the standings. Identical to ``/ranked/leaderboard``'s ``your_place``:
    computed over the full, uncapped standings.
    """
    launch = seasons.official_launch(conn)
    if launch is None:
        return None
    rows = ranked_standings.standings(conn, launch.season_id)
    return ranked_standings.place_of(rows, account_id)
