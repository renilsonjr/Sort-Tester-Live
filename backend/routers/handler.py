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

from backend.handler import best_scores
from backend.routers.ranked import _current_account, get_db

router = APIRouter(prefix="/api/handler", tags=["handler"])


class BestScoreRequest(BaseModel):
    mode: str = Field(max_length=16)
    # A ceiling on what is parsed at all; best_scores.record is where the
    # real rule lives.
    score: int = Field(ge=0, le=best_scores.SCORE_CEILING)


@router.get("/best")
def read_best(account: dict = Depends(_current_account), conn=Depends(get_db)):
    """Every mode's best for this account. Private to the account: it names
    nobody else and reveals nothing about anyone else's play."""
    return {"best": best_scores.best_scores(conn, account["id"])}


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
    try:
        best = best_scores.record(conn, account["id"], payload.mode, payload.score)
    except best_scores.ScoreRefused as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
    # get_db does not commit: the routes that write do it themselves, and a
    # refused score above leaves nothing to commit.
    conn.commit()
    return {"mode": payload.mode, "best": best}
