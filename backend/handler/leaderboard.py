"""The Handler leaderboard: one board per mode, per season (#417).

Read-only. It writes nothing and awards nothing, and it is not the Ranked
leaderboard: nothing here reads or feeds Ranked points, prizes, badges or
the Shift log. The owner's decisions of 2026-11-26 are the rules:

* A row shows what a Ranked leaderboard row shows about a person --
  username, tag and the icon they chose -- and nothing more.
* Nobody opts out: every account with a score in a mode is on that mode's
  board. A score of zero is not a score; it is a mode not yet played well
  enough to count, and it is left off.
* A deleted account is not listed.
* The board belongs to a season. It shows the newest season: live while
  that season admits play, and as it finished once it has ended, until the
  next season opens with an empty board.
* Modes are never compared or combined (rule 16). There is no overall
  board and none may be added.

Two things from Ranked are deliberately absent because they exist for the
prize: the owner's approval of a participant, and the minimum of one
completed Ranked quiz.
"""
from dataclasses import dataclass

from backend.db import migrate
from backend.handler.best_scores import MODES, ScoreRefused


@dataclass(frozen=True)
class Row:
    """One line of a board. The account id is here so the caller can mark
    the reader's own row; it must not be sent to the browser."""

    place: int
    account_id: object
    username: str
    tag: str
    avatar: str | None
    score: int
    tied: bool


def newest_season(conn) -> dict | None:
    """The season the board belongs to: the newest one, open or ended."""
    return migrate.fetch_one(
        conn, "SELECT id, label FROM seasons ORDER BY opened_at DESC LIMIT 1"
    )


def board(conn, season_id, mode: str) -> list[Row]:
    """This season's board for one mode, highest score first.

    Equal scores share a place and the next place skips, as on the Ranked
    board: two players on the same score are both first, and nobody is
    second, because the table does not know which of them is ahead.
    """
    if mode not in MODES:
        raise ScoreRefused(f"Unknown mode: {mode}")
    listing = migrate.fetch_all(
        conn,
        """
        SELECT a.id, a.username, a.tag, a.avatar, h.score
        FROM handler_best_scores h
        JOIN accounts a ON a.id = h.account_id
        WHERE h.season_id = %s AND h.mode = %s AND h.score > 0
          AND a.deleted_at IS NULL
        -- username only steadies the listing when scores are equal; it
        -- ranks nobody, and tied rows carry the same place
        ORDER BY h.score DESC, a.username ASC
        """,
        (season_id, mode),
    )
    return place_rows(listing)


def place_rows(listing) -> list[Row]:
    sharing: dict[int, int] = {}
    placed = []
    place = 0
    previous = None
    for index, row in enumerate(listing, start=1):
        if row["score"] != previous:
            place = index
            previous = row["score"]
        sharing[place] = sharing.get(place, 0) + 1
        placed.append((place, row))
    return [
        Row(
            place=place,
            account_id=row["id"],
            username=row["username"],
            tag=row["tag"],
            avatar=row.get("avatar"),
            score=row["score"],
            tied=sharing[place] > 1,
        )
        for place, row in placed
    ]
