"""The Ranked season over HTTP: launching it, its dates, its leaderboard,
a player's history, and the public notice.

Same /api/ranked prefix as ranked.py; the rules live in backend/ranked.
"""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from backend.db import migrate
from backend.routers import deps
from backend.routers.deps import current_account, get_db, get_plain_db, require_recent_reauth, unprocessable, utc
from backend.ranked import launch, seasons
from backend.ranked import standings as ranked_standings
from backend.ranked import history as ranked_history
from backend.text_input import PlainText

router = APIRouter(prefix="/api/ranked", tags=["ranked"])

# How many leaderboard rows one response carries. A ceiling on the answer,
# not pagination: there is no cursor, and the player's own place is worked
# out before the cut so it survives it.
STANDINGS_ROWS_SHOWN = 500


LAUNCH_CONFIRMATION = "LAUNCH"


class LaunchRequest(BaseModel):
    # every field is optional here so that the owner check runs before any
    # complaint about the body; the endpoint validates them itself
    label: PlainText = ""
    confirm: PlainText = ""
    closes_at: datetime | None = None


@router.post("/season/launch", status_code=status.HTTP_201_CREATED)
def launch_season(
    request: Request,
    payload: LaunchRequest,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """Launch the official season. Irreversible: it voids unfinished
    Pre-Season attempts and resets every balance. Owner only, and only with
    the typed confirmation, so a stray or replayed request does nothing."""
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    # the most destructive action there is -- it voids unfinished attempts
    # and resets every balance -- and the only owner action that did not
    # ask for the login ID again. A session left open was enough.
    require_recent_reauth(request, conn)
    if payload.confirm != LAUNCH_CONFIRMATION:
        raise unprocessable("Type LAUNCH to confirm")
    if payload.closes_at is not None and payload.closes_at.tzinfo is None:
        raise unprocessable("closes_at needs a time zone")
    options = {} if payload.closes_at is None else {"closes_at": payload.closes_at}
    try:
        season_id = launch.launch_official_season(
            conn, label=payload.label, clock=deps.CLOCK, **options
        )
    except launch.InvalidLaunchError as exc:
        raise unprocessable(str(exc)) from None
    except launch.AlreadyLaunchedError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Already launched"
        ) from None
    except launch.NoPreSeasonError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="No Pre-Season to launch from"
        ) from None
    row = migrate.fetch_one(
        conn, "SELECT label, closes_at FROM seasons WHERE id = %s", (season_id,)
    )
    return {
        "season_id": str(season_id),
        "label": row["label"],
        "closes_at": row["closes_at"].astimezone(timezone.utc).isoformat(),
    }


@router.get("/history")
def history(
    phase: Literal["pre_season", "official"] | None = None,
    account: dict = Depends(current_account),
    conn=Depends(get_db),
):
    """The signed-in account's own scored attempts, newest first. Private to
    the account: the request cannot name another account, and the owner gets
    no exception."""
    entries = ranked_history.account_history(conn, account["id"], phase)
    return [
        {
            "attempt_id": str(entry["attempt_id"]),
            "phase": entry["phase"],
            "label": entry["label"],
            "mode": entry["mode"],
            "final_outcome": entry["final_outcome"],
            "raw_score": entry["raw_score"],
            "adjustment": entry["adjustment"],
            "points_before": entry["points_before"],
            "points_after": entry["points_after"],
            "badge_before": entry["badge_before"],
            "badge_after": entry["badge_after"],
            "settled_at": entry["settled_at"].astimezone(timezone.utc).isoformat(),
        }
        for entry in entries
    ]


@router.get("/season")
def season(account: dict = Depends(current_account), conn=Depends(get_db)):
    """Where the current season is in its life. Read-only. ``points_final``
    is true once the season is frozen; prize standings stay provisional
    after that until they are finalized elsewhere."""
    current = seasons.current_season_status(conn, deps.CLOCK.now())
    if current is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No season")
    closes_at = current.closes_at
    return {
        "season_id": str(current.season_id),
        "phase": current.phase,
        "label": current.label,
        "status": current.status,
        "closes_at": None if closes_at is None
        else closes_at.astimezone(timezone.utc).isoformat(),
        "points_final": current.status == "frozen",
        "approvals_open": current.approvals_open,
        # the owner's announced start (#452), for the Pre-Season line
        "announced_start": utc(launch.ANNOUNCED_OFFICIAL_START),
    }


@router.get("/leaderboard")
def leaderboard(account: dict = Depends(current_account), conn=Depends(get_db)):
    """The leaderboard. Login is required to see it (settled Q5).

    Read-only, and it carries only what the approved screen shows: place,
    username, tag, points and badge. ``your_place`` is null for a player
    the competition does not include, which is the "no position" state the
    mockup draws; their own points and badge are unaffected and stay on
    their profile.

    Before the official launch this is the Pre-Season board (#247, owner
    decision 2026-11-20): everyone with one completed Pre-Season Ranked
    quiz, no owner approval, and never a hat or a final state. ``phase``
    says which board it is. The launch resets every balance, so the
    Pre-Season board ends there and the official one starts empty.
    ``points_final`` repeats what /season says: once the season is frozen
    the points no longer move, while prize places stay provisional until
    the tie-breaks in #24 resolve them.
    """
    board = ranked_standings.current_board(conn)
    if board is None:
        return {
            "phase": None,
            "season_label": None,
            "points_final": False,
            "prizes_final": False,
            "rows": [],
            "your_place": None,
            "eligible": False,
        }
    rows = board.rows
    # Worked out over the whole leaderboard, before the cap below, so a
    # player past the cut still learns where they stand.
    place = ranked_standings.place_of(rows, account["id"])
    # The cap lives here rather than in standings(), which the prize
    # tie-break logic also calls: a LIMIT there would compute prizes from
    # a truncated leaderboard -- harmless while there are fewer players
    # than the cap, and invisible on the day there are not.
    rows = rows[:STANDINGS_ROWS_SHOWN]
    points_final = False
    prizes_final = False
    winners = set()
    if board.phase == "official":
        current = seasons.current_season_status(conn, deps.CLOCK.now())
        points_final = current is not None and current.status == "frozen"
        prizes_final, winners = _prize_state(conn, board.season_id)
    return {
        "phase": board.phase,
        "season_label": board.season_label,
        "points_final": points_final,
        # prize places stay provisional until every tie-break and selection
        # is resolved; only then does a row carry a hat
        "prizes_final": prizes_final,
        "rows": [
            {
                "place": row.place,
                "username": row.username,
                "tag": row.tag,
                "points": row.points,
                "badge": row.badge,
                "avatar": row.avatar,
                "tied": row.tied,
                "you": row.account_id == account["id"],
                "hat": row.account_id in winners,
            }
            for row in rows
        ],
        "your_place": place,
        "eligible": place is not None,
    }


def _prize_state(conn, season_id):
    """Whether the official season's prizes are final, and who holds a hat."""
    season_row = migrate.fetch_one(
        conn, "SELECT prizes_final_at FROM seasons WHERE id = %s", (season_id,)
    )
    prizes_final = season_row is not None and season_row["prizes_final_at"] is not None
    winners = set()
    if prizes_final:
        winners = {
            r["account_id"]
            for r in migrate.fetch_all(
                conn, "SELECT account_id FROM season_prizes WHERE season_id = %s",
                (season_id,),
            )
        }
    return prizes_final, winners


@router.get("/season/notice")
def season_notice(conn=Depends(get_plain_db)):
    """The season-start notice, for anyone — signed in or not.

    The approved home page shows a small callout once the official season
    has started, carrying its start date, and **guests see it too**
    (Decision 15, placement settled 2026-11-15). The authenticated
    ``/season`` endpoint cannot serve that, so this one exists.

    It carries nothing about any player and nothing that is not already
    public once the season opens: whether it has started, its label, and
    when it started and ends. Before the official launch it answers
    ``started: false`` and no launch dates.

    ``announced_start`` and ``announced_end`` are the dates the owner
    announced on 2026-11-24 (#452): the season is scheduled to start
    December 1, 2026 at midnight Eastern. They are an announcement, not a
    launch: ``started`` stays false until the owner actually launches.
    """
    announced = {
        "announced_start": utc(launch.ANNOUNCED_OFFICIAL_START),
        "announced_end": utc(launch.DEFAULT_OFFICIAL_END),
    }
    fact = seasons.official_launch(conn)
    if fact is None:
        return {
            "started": False, "label": None, "started_at": None, "closes_at": None,
            **announced,
        }
    current = seasons.current_season_status(conn, deps.CLOCK.now())
    closes_at = current.closes_at if current else None
    return {
        "started": True,
        "label": fact.label,
        "started_at": utc(fact.launched_at),
        "closes_at": None if closes_at is None else utc(closes_at),
        **announced,
    }
