"""Read and raise the Handler best score (#396).

The whole server side of the mini-game's first release. It stores one
number per account per mode and nothing else: no round history, no
timestamps, no telemetry. Scores from different modes are never compared or
summed, because a two-minute round in Easy is not a two-minute round in
Hard, so they are separate rows and separate answers.

Since #417 that number belongs to a season (owner decision, 2026-11-26):
the personal best and the leaderboard both start over when a new season
does. The season is the one admitting Ranked play at that moment, the same
answer Ranked itself uses. Between seasons there is none, and a score made
then is not stored: the caller says so on screen, as it does for a guest.

Within a season a score only ever goes up. The client is not trusted to know the previous
best, so the raise happens in the database in one statement rather than as
a read followed by a write, which two tabs could interleave.
"""
from backend.db import migrate
from backend.ranked import seasons

# The four modes, repeated from the migration's CHECK so a bad mode is
# refused before it reaches the database.
MODES = ("easy", "medium", "hard", "expert")

# A two-minute round cannot plausibly pass this. It is a guard against a
# nonsense or tampered value reaching the table, not a game rule: the engine
# is what decides a score, and #397 may change its constants.
SCORE_CEILING = 100_000


class ScoreRefused(Exception):
    """The mode or the score is not one this table accepts."""


def current_season(conn, now):
    """The season a Handler score made at ``now`` belongs to, or ``None``
    between seasons. Ranked's own rule, read rather than repeated."""
    return seasons.admitting_season(conn, now)


def best_scores(conn, account_id, season_id) -> dict:
    """Every mode's best for this account in this season, zero where
    nothing is stored -- which is every mode when there is no season."""
    if season_id is None:
        return {mode: 0 for mode in MODES}
    rows = migrate.fetch_all(
        conn,
        "SELECT mode, score FROM handler_best_scores"
        " WHERE account_id = %s AND season_id = %s",
        (account_id, season_id),
    )
    stored = {row["mode"]: row["score"] for row in rows}
    return {mode: stored.get(mode, 0) for mode in MODES}


def record(conn, account_id, season_id, mode: str, score: int) -> int | None:
    """Keep *score* if it beats this season's stored best. Returns the best
    after, or ``None`` when there is no season to store it in."""
    if mode not in MODES:
        raise ScoreRefused(f"Unknown mode: {mode}")
    if not isinstance(score, int) or isinstance(score, bool):
        raise ScoreRefused("A score is a whole number.")
    if score < 0 or score > SCORE_CEILING:
        raise ScoreRefused("A score is between 0 and the ceiling.")
    if season_id is None:
        return None
    return _upsert(conn, account_id, season_id, mode, score)


def _upsert(conn, account_id, season_id, mode: str, score: int) -> int:
    row = migrate.fetch_one(
        conn,
        """
        INSERT INTO handler_best_scores (season_id, account_id, mode, score)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (season_id, account_id, mode) DO UPDATE
            SET score = GREATEST(handler_best_scores.score, EXCLUDED.score)
        RETURNING score
        """,
        (season_id, account_id, mode, score),
    )
    return row["score"]


def forget_account(conn, account_id) -> None:
    """Remove every Handler score this account ever made, in every season.
    Part of deleting an account: its scores go with it rather than staying
    in the table behind the account's deletion mark."""
    migrate.execute(
        conn, "DELETE FROM handler_best_scores WHERE account_id = %s", (account_id,)
    )
