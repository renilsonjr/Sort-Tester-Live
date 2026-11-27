"""The Versus lobby's routes: open a room, join one, watch it, leave it.

Every route requires a session, as the Handler routes do: a duel is
between two named accounts, and the client treats 401 as "guest". The
waiting screen polls the read route once a second, the same cadence the
Ranked heartbeat already proved on this hardware.

Nothing here starts a duel. A room reaching `full` is where this slice
ends; the match engine is the next one.
"""
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from backend.ranked.clock import system_clock
from backend.routers.deps import current_account, reviewed_bank
from backend.routers.ranked import get_db
from backend.versus import rooms

router = APIRouter(prefix="/api/versus", tags=["versus"])

_CLOCK = system_clock()


class CreateRoomRequest(BaseModel):
    game: str = Field(max_length=16)


class JoinRoomRequest(BaseModel):
    code: str = Field(max_length=16)


@router.post("/rooms")
def create_room(
    payload: CreateRoomRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Open a room and answer it, code included. Opening another closes
    the first: one open room per host."""
    try:
        room = rooms.create(conn, account["id"], payload.game, now=_CLOCK.now())
    except rooms.RoomRefused as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from None
    conn.commit()
    return room


@router.post("/rooms/join")
def join_room(
    payload: JoinRoomRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Take the empty seat in the room with this code. One answer covers
    every way that can fail -- no such code, expired, already full, your
    own room -- so a code cannot be used to tell those apart."""
    try:
        room = rooms.join(conn, account["id"], payload.code, now=_CLOCK.now())
    except rooms.RoomRefused as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from None
    conn.commit()
    return room


@router.get("/rooms/{room_id}")
def read_room(
    room_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """The room as this account sees it. The waiting screen polls this;
    a room that expired is answered as closed, and a room this account is
    not in is answered as absent."""
    room = rooms.read(conn, _room_uuid(room_id), account["id"], now=_CLOCK.now())
    # read() may have stored the lazy close it answered with.
    conn.commit()
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such room.")
    return room


@router.post("/rooms/{room_id}/leave")
def leave_room(
    room_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Walk out. Host gone closes the room; guest gone reopens the seat.
    Leaving a room that is already gone is not an error."""
    rooms.leave(conn, _room_uuid(room_id), account["id"], now=_CLOCK.now())
    conn.commit()
    return {"ok": True}


def _room_uuid(room_id: str):
    """A path id that is not a UUID is a 404, not a database error."""
    try:
        return uuid.UUID(room_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such room.") from None


# -- the duel itself -------------------------------------------------------

from backend.versus import match as versus_match  # noqa: E402


class AnswerRequest(BaseModel):
    seq: int = Field(ge=1, le=versus_match.QUIZ_QUESTIONS)
    choice: str = Field(max_length=32)


class ProgressRequest(BaseModel):
    score: int = Field(ge=0, le=versus_match.SCORE_CEILING)
    final: bool = False


@router.post("/rooms/{room_id}/start")
def start_match(
    room_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """The host turns a full room into a playing duel. Both players'
    room polls answer with the match id from here on."""
    now = _CLOCK.now()
    room = rooms.read(conn, _room_uuid(room_id), account["id"], now=now)
    if room is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such room.")
    if room["match_id"] is not None:
        conn.commit()
        return versus_match.read(conn, room["match_id"], account["id"], now=now)
    try:
        match_id = versus_match.start(conn, room, reviewed_bank(), now=now)
    except versus_match.MatchRefused as error:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    conn.commit()
    return versus_match.read(conn, match_id, account["id"], now=now)


@router.get("/matches/{match_id}")
def read_match(
    match_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """The once-a-second poll behind the tug bar. It is also the lazy
    judge: a duel past its deadline finishes here."""
    state = versus_match.read(conn, _room_uuid(match_id), account["id"], now=_CLOCK.now())
    conn.commit()
    if state is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No such duel.")
    return state


@router.get("/matches/{match_id}/question")
def read_match_question(
    match_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """This player's live quiz question. ``None``-shaped 404 when they
    are done, the duel is over, or it is not theirs to see."""
    view = versus_match.current_question(
        conn, _room_uuid(match_id), account["id"], reviewed_bank(), now=_CLOCK.now()
    )
    conn.commit()
    if view is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No live question.")
    return view


@router.post("/matches/{match_id}/answer")
def answer_match_question(
    match_id: str,
    payload: AnswerRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Judge one answer and advance. The result carries the right belt,
    so the feedback screen never asks again."""
    try:
        result = versus_match.submit_answer(
            conn, _room_uuid(match_id), account["id"], payload.seq, payload.choice,
            reviewed_bank(), now=_CLOCK.now(),
        )
    except versus_match.MatchRefused as error:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    conn.commit()
    return result


@router.post("/matches/{match_id}/progress")
def report_match_progress(
    match_id: str,
    payload: ProgressRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """The handler duel's score as it stands, reported as it changes. It
    follows the round down as well as up; ``final`` closes this player's
    round, and nothing is taken from them after it."""
    try:
        state = versus_match.report_progress(
            conn, _room_uuid(match_id), account["id"], payload.score,
            now=_CLOCK.now(), final=payload.final,
        )
    except versus_match.MatchRefused as error:
        conn.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
    conn.commit()
    return state


@router.post("/matches/{match_id}/forfeit")
def forfeit_match(
    match_id: str,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Walk out where you stand. Not an error when the duel is already
    over: the next poll settles the result either way."""
    versus_match.forfeit(conn, _room_uuid(match_id), account["id"], now=_CLOCK.now())
    conn.commit()
    return {"ok": True}


# -- the leaderboard -------------------------------------------------------

from backend.ranked import seasons as ranked_seasons  # noqa: E402
from backend.versus import leaderboard as versus_board  # noqa: E402

# How many rows one answer carries. A ceiling, not pagination: the reader's
# own place is worked out before the cut, so it survives it.
BOARD_ROWS_SHOWN = 100


@router.get("/leaderboard")
def read_leaderboard(account: dict = Depends(current_account), conn=Depends(get_db)):
    """The Versus board for the newest season: duels won, then points.
    Login is required to see it, as on the other boards.

    It carries only what the screen shows. No account id leaves the
    server; ``you`` marks the reader's own row instead. ``open`` is false
    once the season has ended, when the board is shown as it finished.
    """
    season = versus_board.newest_season(conn)
    if season is None:
        return {"season_label": None, "open": False, "rows": [], "players": 0, "you": None}
    rows = versus_board.board(conn, season["id"])
    mine = next((row for row in rows if row.account_id == account["id"]), None)
    return {
        "season_label": season["label"],
        "open": ranked_seasons.admitting_season(conn, _CLOCK.now()) == season["id"],
        "rows": [
            {
                "place": row.place,
                "username": row.username,
                "tag": row.tag,
                "avatar": row.avatar,
                "wins": row.wins,
                "played": row.played,
                "points": row.points,
                "tied": row.tied,
                "you": row.account_id == account["id"],
            }
            for row in rows[:BOARD_ROWS_SHOWN]
        ],
        "players": len(rows),
        "you": None if mine is None else {
            "place": mine.place, "wins": mine.wins, "points": mine.points, "tied": mine.tied,
        },
    }
