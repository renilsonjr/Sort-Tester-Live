"""The Handler mini-game's two routes (#396).

Read the signed-in account's best score per mode, and raise it. That is the
whole server side of the first release: the spec's persistence boundary
keeps mini-game results out of Ranked points, prizes, badges, the
leaderboard and the Shift log, and nothing here writes to any of them.

A guest has no account and so no stored best. That is not an error: the
game is fully playable signed out, and the end-of-round screen says the
score was not saved rather than showing a silent zero. Both routes
therefore require a session, and the client treats 401 as "guest".
"""
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from backend.handler import best_scores, leaderboard
from backend.ranked.clock import system_clock
from backend.routers.ranked import _current_account, get_db

router = APIRouter(prefix="/api/handler", tags=["handler"])

_CLOCK = system_clock()

# How many rows one answer carries. A ceiling, not pagination: the reader's
# own place is worked out before the cut, so it survives it.
BOARD_ROWS_SHOWN = 100


class BestScoreRequest(BaseModel):
    mode: str = Field(max_length=16)
    # A ceiling on what is parsed at all; best_scores.record is where the
    # real rule lives.
    score: int = Field(ge=0, le=best_scores.SCORE_CEILING)


@router.get("/best")
def read_best(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Every mode's best for this account in the current season. Private to
    the account: it names nobody else and reveals nothing about anyone
    else's play. ``in_season`` is false between seasons, when every best is
    zero and a new score would not be stored."""
    season_id = best_scores.current_season(conn, _CLOCK.now())
    return {
        "best": best_scores.best_scores(conn, account["id"], season_id),
        "in_season": season_id is not None,
    }


@router.put("/best")
def raise_best(
    payload: BestScoreRequest,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """Keep the score if it beats what is stored, and answer with the best
    after. A score never goes down, and the comparison happens in the
    database rather than here, so two tabs cannot interleave a read and a
    write and lose the higher one."""
    season_id = best_scores.current_season(conn, _CLOCK.now())
    try:
        best = best_scores.record(conn, account["id"], season_id, payload.mode, payload.score)
    except best_scores.ScoreRefused as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
    # get_db does not commit: the routes that write do it themselves, and a
    # refused score above leaves nothing to commit.
    conn.commit()
    # Between seasons nothing was stored. That is an answer, not an error:
    # the round was real, and the screen says the score was not saved.
    if best is None:
        return {"mode": payload.mode, "best": 0, "saved": False}
    return {"mode": payload.mode, "best": best, "saved": True}


@router.get("/leaderboard")
def read_leaderboard(
    mode: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    """One mode's Handler board for the newest season (#417). Login is
    required to see it, as on the Ranked board.

    It carries only what the screen shows: place, username, tag, icon and
    score. No account id leaves the server; ``you`` marks the reader's own
    row instead. ``open`` is false once the season has ended, when the board
    is shown as it finished and new scores are not being stored.
    """
    if mode not in best_scores.MODES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Unknown mode: {mode}")
    season = leaderboard.newest_season(conn)
    if season is None:
        return {"mode": mode, "season_label": None, "open": False, "rows": [], "players": 0, "you": None}
    rows = leaderboard.board(conn, season["id"], mode)
    mine = next((row for row in rows if row.account_id == account["id"]), None)
    return {
        "mode": mode,
        "season_label": season["label"],
        "open": best_scores.current_season(conn, _CLOCK.now()) == season["id"],
        "rows": [
            {
                "place": row.place,
                "username": row.username,
                "tag": row.tag,
                "avatar": row.avatar,
                "score": row.score,
                "tied": row.tied,
                "you": row.account_id == account["id"],
            }
            for row in rows[:BOARD_ROWS_SHOWN]
        ],
        "players": len(rows),
        "you": None if mine is None else {"place": mine.place, "score": mine.score, "tied": mine.tied},
    }
