"""The Versus leaderboard: duels won this season.

Read-only, and the app's third board: it is not the Ranked leaderboard
and not the Handler's. Nothing here reads or feeds Ranked points, prizes
or badges. It follows the Handler board's rules where they apply:

* A row shows username, tag and chosen icon, and nothing more.
* Every account that finished a duel this season is listed; a deleted
  account is not.
* The board belongs to a season and shows the newest one: live while it
  admits play, and as it finished once it has ended.

The order is wins first, then points scored across the season's duels.
Quiz and handler duels count together: a win is a win, and the points
only separate players level on wins. Two players level on both share a
place and the next place skips, as on the other boards.
"""
from dataclasses import dataclass

from backend.db import migrate


@dataclass(frozen=True)
class Row:
    """One line of the board. The account id is here so the caller can
    mark the reader's own row; it must not be sent to the browser."""

    place: int
    account_id: object
    username: str
    tag: str
    avatar: str | None
    wins: int
    played: int
    points: int
    tied: bool


def newest_season(conn) -> dict | None:
    """The season the board belongs to: the newest one, open or ended."""
    return migrate.fetch_one(
        conn, "SELECT id, label FROM seasons ORDER BY opened_at DESC LIMIT 1"
    )


def board(conn, season_id) -> list[Row]:
    """This season's board, most duels won first."""
    listing = migrate.fetch_all(
        conn,
        """
        SELECT a.id, a.username, a.tag, a.avatar,
               COUNT(*) FILTER (WHERE m.winner_account_id = a.id) AS wins,
               COUNT(*) AS played,
               COALESCE(SUM(p.score), 0) AS points
        FROM versus_match_players p
        JOIN versus_matches m ON m.id = p.match_id
        JOIN accounts a ON a.id = p.account_id
        WHERE m.season_id = %s AND m.state = 'finished'
          AND a.deleted_at IS NULL
        GROUP BY a.id, a.username, a.tag, a.avatar
        -- username only steadies the listing between level players; it
        -- ranks nobody, and level rows carry the same place
        ORDER BY wins DESC, points DESC, a.username ASC
        """,
        (season_id,),
    )
    sharing: dict[int, int] = {}
    placed = []
    place = 0
    previous = None
    for index, row in enumerate(listing, start=1):
        standing = (row["wins"], row["points"])
        if standing != previous:
            place = index
            previous = standing
        sharing[place] = sharing.get(place, 0) + 1
        placed.append((place, row))
    return [
        Row(
            place=place,
            account_id=row["id"],
            username=row["username"],
            tag=row["tag"],
            avatar=row.get("avatar"),
            wins=row["wins"],
            played=row["played"],
            points=int(row["points"]),
            tied=sharing[place] > 1,
        )
        for place, row in placed
    ]
