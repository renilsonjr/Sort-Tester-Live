"""Versus rooms: open one, share the code, wait for an opponent.

This is the lobby half of a duel and the whole of the first slice. A room
is created by a signed-in player, carries which mini-game the duel will
run, and waits five minutes for someone to join by code. The duel itself
is the next slice; a `full` room is as far as this module goes.

Two rules keep the table honest without a background job:

- **One open room per host.** Opening a room closes any earlier one the
  same account still had open, so a player cannot paper the lobby with
  codes.
- **Expiry is judged at read time.** Every lookup treats a room past its
  `expires_at` as closed, and the next `create` sweeps long-dead rows
  away. Nothing needs to fire at the stroke of the deadline.

Room codes look like a word and two digits (HAT-42): short enough to say
out loud across a warehouse floor. A collision with an open room is
retried with a fresh draw; the partial unique index is what makes the
retry safe under two simultaneous creates.
"""
import secrets
from datetime import timedelta

from backend.db import migrate

GAMES = ("quiz", "handler")

# How long a room waits before it stops existing for joiners. Five
# minutes: enough to send a code to the person beside you, short enough
# that a forgotten room frees its code the same shift.
ROOM_TTL = timedelta(minutes=5)

# Closed and expired rows are swept this long after they stop mattering.
# They are kept a little while so "the room is gone" can be answered
# precisely rather than with a generic 404.
SWEEP_AFTER = timedelta(hours=1)

# The words a code draws from. Warehouse floor vocabulary, all distinct
# after the dash-and-digits treatment, none a word the Quiz Code list
# would make a player second-guess.
CODE_WORDS = (
    "HAT", "BOX", "VAN", "RIG", "JIG", "LOT", "BIN", "CAP",
    "TAG", "PIN", "KEY", "LID", "RAMP", "DOCK", "LANE", "CART",
)

# How many fresh draws a create makes before giving up on the night. The
# code space is 16 words x 90 numbers = 1,440; with a handful of rooms
# open at once a second collision in a row is already remarkable.
CODE_RETRIES = 8


class RoomRefused(Exception):
    """The game, the code or the move is not one the lobby accepts."""


def _draw_code() -> str:
    word = secrets.choice(CODE_WORDS)
    number = secrets.randbelow(90) + 10
    return f"{word}-{number}"


def _sweep(conn, now) -> None:
    migrate.execute(
        conn,
        "DELETE FROM versus_rooms WHERE expires_at <= %s",
        (now - SWEEP_AFTER,),
    )


def create(conn, account_id, game: str, *, now) -> dict:
    """Open a room for *game* and answer it. Any earlier open room this
    account hosted is closed first: one code per host, always the newest."""
    if game not in GAMES:
        raise RoomRefused(f"Unknown game: {game}")
    _sweep(conn, now)
    migrate.execute(
        conn,
        "UPDATE versus_rooms SET state = 'closed'"
        " WHERE host_account_id = %s AND state <> 'closed'",
        (account_id,),
    )
    for _ in range(CODE_RETRIES):
        code = _draw_code()
        taken = migrate.fetch_one(
            conn,
            "SELECT 1 AS hit FROM versus_rooms WHERE code = %s AND state <> 'closed'",
            (code,),
        )
        if taken is not None:
            continue
        row = migrate.fetch_one(
            conn,
            """
            INSERT INTO versus_rooms (code, game, host_account_id, state, created_at, expires_at)
            VALUES (%s, %s, %s, 'waiting', %s, %s)
            RETURNING id
            """,
            (code, game, account_id, now, now + ROOM_TTL),
        )
        return read(conn, row["id"], account_id, now=now)
    # Only reachable when the lobby is saturated with open rooms.
    raise RoomRefused("No free room code right now; try again in a moment.")


def join(conn, account_id, code: str, *, now) -> dict:
    """Take the empty seat in the open room with this *code*. The seat is
    claimed in one statement, so two joiners cannot both win it."""
    claimed = migrate.fetch_one(
        conn,
        """
        UPDATE versus_rooms
           SET guest_account_id = %s, state = 'full'
         WHERE code = %s AND state = 'waiting' AND expires_at > %s
           AND host_account_id <> %s
        RETURNING id
        """,
        (account_id, code.strip().upper(), now, account_id),
    )
    if claimed is None:
        raise RoomRefused("That room is not waiting for a player.")
    return read(conn, claimed["id"], account_id, now=now)


def read(conn, room_id, account_id, *, now) -> dict:
    """The room as this account sees it, or ``None`` when it is gone. A
    room past its deadline is answered -- and stored -- as closed, so a
    waiting screen learns its room died by polling this."""
    row = migrate.fetch_one(
        conn,
        """
        SELECT r.id, r.code, r.game, r.state, r.expires_at, r.match_id,
               r.host_account_id, r.guest_account_id,
               h.username AS host_username, h.tag AS host_tag, h.avatar AS host_avatar,
               g.username AS guest_username, g.tag AS guest_tag, g.avatar AS guest_avatar
          FROM versus_rooms r
          JOIN accounts h ON h.id = r.host_account_id
          LEFT JOIN accounts g ON g.id = r.guest_account_id
         WHERE r.id = %s
        """,
        (room_id,),
    )
    if row is None:
        return None
    state = row["state"]
    if state != "closed" and row["expires_at"] <= now:
        migrate.execute(
            conn, "UPDATE versus_rooms SET state = 'closed' WHERE id = %s", (room_id,)
        )
        state = "closed"
    you_are_host = row["host_account_id"] == account_id
    if not you_are_host and row["guest_account_id"] != account_id:
        # The room is not this account's to watch. Answered as absent
        # rather than refused, so a code cannot be used to probe who is
        # playing whom.
        return None
    seconds_left = max(0, int((row["expires_at"] - now).total_seconds()))
    return {
        "id": str(row["id"]),
        "code": row["code"],
        "game": row["game"],
        "state": state,
        "you_are_host": you_are_host,
        "match_id": str(row["match_id"]) if row.get("match_id") is not None else None,
        "seconds_left": 0 if state == "closed" else seconds_left,
        "host": _seat(row, "host"),
        "guest": _seat(row, "guest") if row["guest_account_id"] is not None else None,
    }


def leave(conn, room_id, account_id, *, now) -> None:
    """Walk out. The host leaving closes the room; the guest leaving puts
    it back to waiting for someone else, clock unchanged."""
    room = read(conn, room_id, account_id, now=now)
    if room is None or room["state"] == "closed":
        return
    if room["you_are_host"]:
        migrate.execute(
            conn, "UPDATE versus_rooms SET state = 'closed' WHERE id = %s", (room_id,)
        )
    else:
        migrate.execute(
            conn,
            "UPDATE versus_rooms SET guest_account_id = NULL, state = 'waiting'"
            " WHERE id = %s AND state = 'full'",
            (room_id,),
        )


def _seat(row, who: str) -> dict:
    return {
        "username": row[f"{who}_username"],
        "tag": row[f"{who}_tag"],
        "avatar": row.get(f"{who}_avatar"),
    }
