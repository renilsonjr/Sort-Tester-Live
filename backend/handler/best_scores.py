"""Read and raise the Handler best score (#396).

The whole server side of the mini-game's first release. It stores one
number per account per mode and nothing else: no round history, no
timestamps, no telemetry. Scores from different modes are never compared or
summed, because a two-minute round in Easy is not a two-minute round in
Hard, so they are separate rows and separate answers.

A score only ever goes up. The client is not trusted to know the previous
best, so the raise happens in the database in one statement rather than as
a read followed by a write, which two tabs could interleave.
"""
from backend.db import migrate

# The four modes, repeated from the migration's CHECK so a bad mode is
# refused before it reaches the database.
MODES = ("easy", "medium", "hard", "expert")

# A two-minute round cannot plausibly pass this. It is a guard against a
# nonsense or tampered value reaching the table, not a game rule: the engine
# is what decides a score, and #397 may change its constants.
SCORE_CEILING = 100_000


class ScoreRefused(Exception):
    """The mode or the score is not one this table accepts."""


def best_scores(conn, account_id) -> dict:
    """Every mode's best for this account, zero where nothing is stored."""
    rows = migrate.fetch_all(
        conn,
        "SELECT mode, score FROM handler_best_scores WHERE account_id = %s",
        (account_id,),
    )
    stored = {row["mode"]: row["score"] for row in rows}
    return {mode: stored.get(mode, 0) for mode in MODES}


def record(conn, account_id, mode: str, score: int) -> int:
    """Keep *score* if it beats what is stored. Returns the best after."""
    if mode not in MODES:
        raise ScoreRefused(f"Unknown mode: {mode}")
    if not isinstance(score, int) or isinstance(score, bool):
        raise ScoreRefused("A score is a whole number.")
    if score < 0 or score > SCORE_CEILING:
        raise ScoreRefused("A score is between 0 and the ceiling.")
    return _upsert(conn, account_id, mode, score)


def _upsert(conn, account_id, mode: str, score: int) -> int:
    row = migrate.fetch_one(
        conn,
        """
        INSERT INTO handler_best_scores (account_id, mode, score)
        VALUES (%s, %s, %s)
        ON CONFLICT (account_id, mode) DO UPDATE
            SET score = GREATEST(handler_best_scores.score, EXCLUDED.score)
        RETURNING score
        """,
        (account_id, mode, score),
    )
    return row["score"]
