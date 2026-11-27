"""The Versus duel: one shared draw, two private scoreboards, one clock.

The quiz duel reuses the tie-break idea without touching its tables: the
match draws once and stores the set as question versions, and each player
walks the same sequence at their own pace against a five-second question
clock. Faster correct answers score more; a wrong or late answer scores
nothing but still advances. The handler duel stores no questions at all:
both clients deal the same belt order from the match's shared seed, play
their own conveyor, and report the score as it grows.

The match ends when both players have finished or its hard deadline
passes, whichever is first -- and the deadline is judged lazily, at read
time, like a room's expiry: no background job. Scores never leave these
tables; a duel changes nothing in Ranked.
"""
import secrets
from datetime import timedelta
from random import SystemRandom

from backend.db import migrate
from backend.ranked import belt_options
from backend.ranked.versions import materialize_question_version
from backend.ranked_bank.identity import question_content_digest
from backend.ranked_bank.selection import select_assignment

# The quiz duel's shape: ten questions, drawn from the harder two thirds
# of the ordinary fifteen-question draw (its five Medium and five Hard),
# five seconds each.
QUIZ_QUESTIONS = 10
QUESTION_SECONDS = 5

# A correct answer is worth this much, plus up to as much again for
# speed: the bonus is the fraction of the question clock still unspent.
CORRECT_POINTS = 100
SPEED_POINTS = 100

# An answer arriving this long after the question clock ran out is still
# accepted -- the network is not the player's fault -- but scores nothing.
LATE_GRACE = timedelta(seconds=2)

# The whole duel's hard deadline: question clock plus a feedback pause
# per question, with slack for the slow network the grace already
# expects. After it, the duel is over whatever remains unanswered.
QUIZ_MATCH_SECONDS = QUIZ_QUESTIONS * (QUESTION_SECONDS + 3) + 15

# The handler duel is one round of the mini-game as it already exists,
# plus the same slack.
HANDLER_ROUND_SECONDS = 60
HANDLER_MATCH_SECONDS = HANDLER_ROUND_SECONDS + 15

# What a duel's score can plausibly reach; the ceiling guards the table
# against nonsense, as the Handler best-score ceiling does.
SCORE_CEILING = 100_000


class MatchRefused(Exception):
    """The move is not one this duel accepts; the message can be shown."""


def start(conn, room, bank, *, now) -> str:
    """Turn a full *room* into a playing match and answer the match id.
    Only the host starts, and only once: the room's `match_id` is both
    the pointer the guest polls and the latch against a double start."""
    if not room["you_are_host"]:
        raise MatchRefused("Only the player who opened the room starts the duel.")
    if room["state"] != "full":
        raise MatchRefused("The room does not have two players.")
    claimed = migrate.fetch_one(
        conn,
        "SELECT host_account_id, guest_account_id, game FROM versus_rooms"
        " WHERE id = %s AND match_id IS NULL FOR UPDATE",
        (room["id"],),
    )
    if claimed is None:
        raise MatchRefused("The duel has already started.")
    game = claimed["game"]
    seconds = QUIZ_MATCH_SECONDS if game == "quiz" else HANDLER_MATCH_SECONDS
    match = migrate.fetch_one(
        conn,
        """
        INSERT INTO versus_matches
            (game, host_account_id, guest_account_id, seed, question_count, started_at, ends_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s)
        RETURNING id
        """,
        (
            game,
            claimed["host_account_id"],
            claimed["guest_account_id"],
            secrets.token_hex(8) if game == "handler" else None,
            QUIZ_QUESTIONS if game == "quiz" else 0,
            now,
            now + timedelta(seconds=seconds),
        ),
    )
    match_id = match["id"]
    for account_id in (claimed["host_account_id"], claimed["guest_account_id"]):
        migrate.execute(
            conn,
            "INSERT INTO versus_match_players (match_id, account_id, question_sent_at)"
            " VALUES (%s, %s, %s)",
            (match_id, account_id, now if game == "quiz" else None),
        )
    if game == "quiz":
        _store_draw(conn, match_id, bank)
    migrate.execute(
        conn,
        "UPDATE versus_rooms SET match_id = %s, state = 'closed' WHERE id = %s",
        (match_id, room["id"]),
    )
    return match_id


def _store_draw(conn, match_id, bank) -> None:
    """Draw once for both players: the ordinary selection's five Medium
    and five Hard, shuffled, stored as versions with their options."""
    snapshot = select_assignment(bank)
    harder = [q for q in snapshot.questions if q.difficulty in ("Medium", "Hard")]
    SystemRandom().shuffle(harder)
    belts = belt_options.all_belts(bank)
    for seq, question in enumerate(harder[:QUIZ_QUESTIONS], start=1):
        version_id = materialize_question_version(conn, question)
        migrate.execute(
            conn,
            "INSERT INTO versus_match_questions (match_id, seq, question_version_id, options)"
            " VALUES (%s, %s, %s, %s)",
            (match_id, seq, version_id, belt_options.draw_options(question.correct_belt, belts)),
        )


def read(conn, match_id, account_id, *, now) -> dict:
    """The duel as this player sees it, or ``None`` for an outsider. This
    is the once-a-second poll behind the tug bar, and the lazy judge: a
    match past its deadline is finished here, winner decided."""
    row = migrate.fetch_one(
        conn,
        "SELECT id, game, state, seed, question_count, host_account_id, guest_account_id,"
        " started_at, ends_at, finished_at, winner_account_id"
        " FROM versus_matches WHERE id = %s",
        (match_id,),
    )
    if row is None or account_id not in (row["host_account_id"], row["guest_account_id"]):
        return None
    if row["state"] == "playing":
        row = _finish_if_due(conn, row, now)
    players = {
        p["account_id"]: p
        for p in migrate.fetch_all(
            conn,
            "SELECT account_id, score, seq, correct_count, finished_at"
            " FROM versus_match_players WHERE match_id = %s",
            (match_id,),
        )
    }
    opponent_id = (
        row["guest_account_id"] if account_id == row["host_account_id"] else row["host_account_id"]
    )
    names = {
        n["id"]: n
        for n in migrate.fetch_all(
            conn,
            "SELECT id, username, tag, avatar FROM accounts WHERE id IN (%s, %s)",
            (account_id, opponent_id),
        )
    }
    seconds_left = max(0, int((row["ends_at"] - now).total_seconds()))
    winner = row["winner_account_id"]
    return {
        "id": str(row["id"]),
        "game": row["game"],
        "state": row["state"],
        "seed": row["seed"],
        "question_count": row["question_count"],
        "seconds_left": 0 if row["state"] == "finished" else seconds_left,
        "you": _player_view(players[account_id], names[account_id]),
        "opponent": _player_view(players[opponent_id], names[opponent_id]),
        "outcome": None if row["state"] != "finished" else (
            "tie" if winner is None else ("you" if winner == account_id else "opponent")
        ),
    }


def _player_view(player, name) -> dict:
    return {
        "username": name["username"],
        "tag": name["tag"],
        "avatar": name.get("avatar"),
        "score": player["score"],
        "seq": player["seq"],
        "correct": player["correct_count"],
        "finished": player["finished_at"] is not None,
    }


def _finish_if_due(conn, row, now):
    """Finish the match when its deadline passed or both players are
    done. The row comes back as it now stands."""
    done = migrate.fetch_one(
        conn,
        "SELECT COUNT(*) FILTER (WHERE finished_at IS NOT NULL) AS done"
        " FROM versus_match_players WHERE match_id = %s",
        (row["id"],),
    )
    if now < row["ends_at"] and done["done"] < 2:
        return row
    scores = migrate.fetch_all(
        conn,
        "SELECT account_id, score FROM versus_match_players WHERE match_id = %s"
        " ORDER BY score DESC",
        (row["id"],),
    )
    winner = None
    if len(scores) == 2 and scores[0]["score"] != scores[1]["score"]:
        winner = scores[0]["account_id"]
    updated = migrate.fetch_one(
        conn,
        "UPDATE versus_matches SET state = 'finished', finished_at = %s, winner_account_id = %s"
        " WHERE id = %s AND state = 'playing'"
        " RETURNING id, game, state, seed, question_count, host_account_id, guest_account_id,"
        " started_at, ends_at, finished_at, winner_account_id",
        (now, winner, row["id"]),
    )
    # A concurrent poll may have finished it first; read what stands.
    if updated is not None:
        return updated
    return migrate.fetch_one(
        conn,
        "SELECT id, game, state, seed, question_count, host_account_id, guest_account_id,"
        " started_at, ends_at, finished_at, winner_account_id"
        " FROM versus_matches WHERE id = %s",
        (row["id"],),
    )


# -- the quiz duel ---------------------------------------------------------


def current_question(conn, match_id, account_id, bank, *, now) -> dict | None:
    """This player's live question, or ``None`` when they are done or the
    match is not theirs. Reading restarts nothing: the question clock
    started when the previous answer advanced them (or at the start)."""
    state = read(conn, match_id, account_id, now=now)
    if state is None or state["game"] != "quiz" or state["state"] != "playing":
        return None
    player = migrate.fetch_one(
        conn,
        "SELECT seq, question_sent_at, finished_at FROM versus_match_players"
        " WHERE match_id = %s AND account_id = %s",
        (match_id, account_id),
    )
    if player["finished_at"] is not None:
        return None
    stored = migrate.fetch_one(
        conn,
        "SELECT seq, question_version_id, options FROM versus_match_questions"
        " WHERE match_id = %s AND seq = %s",
        (match_id, player["seq"]),
    )
    if stored is None:
        return None
    question = _question_for_version(conn, bank, stored["question_version_id"])
    deadline = player["question_sent_at"] + timedelta(seconds=QUESTION_SECONDS)
    return {
        "seq": stored["seq"],
        "of": QUIZ_QUESTIONS,
        "deadline_at": deadline,
        "prompt_en": question.text.en.prompt,
        "prompt_es": question.text.es.prompt,
        "service": question.context.service,
        "mode": question.context.mode,
        "region_label": question.presentation.region_label,
        "named_destination": question.presentation.named_destination,
        "options": list(stored["options"]),
    }


def submit_answer(conn, match_id, account_id, seq: int, choice: str, bank, *, now) -> dict:
    """Judge one answer, bank the points, advance the player. The row
    lock serializes a double submit of the same seq: the second finds the
    player already past it and is refused."""
    state = read(conn, match_id, account_id, now=now)
    if state is None:
        raise MatchRefused("No such duel.")
    if state["state"] != "playing":
        raise MatchRefused("The duel is over.")
    if state["game"] != "quiz":
        raise MatchRefused("This duel has no questions.")
    player = migrate.fetch_one(
        conn,
        "SELECT seq, question_sent_at, finished_at, score, correct_count"
        " FROM versus_match_players WHERE match_id = %s AND account_id = %s FOR UPDATE",
        (match_id, account_id),
    )
    if player["finished_at"] is not None or player["seq"] != seq:
        raise MatchRefused("That question is not the live one.")
    stored = migrate.fetch_one(
        conn,
        "SELECT question_version_id, options FROM versus_match_questions"
        " WHERE match_id = %s AND seq = %s",
        (match_id, seq),
    )
    question = _question_for_version(conn, bank, stored["question_version_id"])
    elapsed = now - player["question_sent_at"]
    late = elapsed > timedelta(seconds=QUESTION_SECONDS) + LATE_GRACE
    correct = (not late) and choice == question.correct_belt
    gained = 0
    if correct:
        left = max(0.0, QUESTION_SECONDS - elapsed.total_seconds())
        gained = CORRECT_POINTS + round(SPEED_POINTS * left / QUESTION_SECONDS)
    finished = seq >= QUIZ_QUESTIONS
    migrate.execute(
        conn,
        "UPDATE versus_match_players SET score = score + %s,"
        " correct_count = correct_count + %s, seq = %s,"
        " question_sent_at = %s, finished_at = %s"
        " WHERE match_id = %s AND account_id = %s",
        (
            gained,
            1 if correct else 0,
            seq + (0 if finished else 1),
            None if finished else now,
            now if finished else None,
            match_id,
            account_id,
        ),
    )
    return {
        "seq": seq,
        "correct": correct,
        "correct_belt": question.correct_belt,
        "gained": gained,
        "finished": finished,
    }


# -- the handler duel ------------------------------------------------------


def report_progress(conn, match_id, account_id, score: int, *, now, final: bool = False) -> dict:
    """Take the handler duel's growing score. The stored score only ever
    goes up, in the database, so a late or repeated report cannot lower
    it -- the Handler best-score rule, applied to a live duel."""
    if not isinstance(score, int) or isinstance(score, bool) or score < 0 or score > SCORE_CEILING:
        raise MatchRefused("A score is a whole number between 0 and the ceiling.")
    state = read(conn, match_id, account_id, now=now)
    if state is None:
        raise MatchRefused("No such duel.")
    if state["game"] != "handler":
        raise MatchRefused("This duel's score comes from its answers.")
    if state["state"] != "playing":
        raise MatchRefused("The duel is over.")
    migrate.execute(
        conn,
        "UPDATE versus_match_players SET score = GREATEST(score, %s),"
        " finished_at = COALESCE(finished_at, %s)"
        " WHERE match_id = %s AND account_id = %s",
        (score, now if final else None, match_id, account_id),
    )
    return read(conn, match_id, account_id, now=now)


def forfeit(conn, match_id, account_id, *, now) -> None:
    """Walk out of a playing duel: this player is finished where they
    stand, and the next poll settles the result."""
    state = read(conn, match_id, account_id, now=now)
    if state is None or state["state"] != "playing":
        return
    migrate.execute(
        conn,
        "UPDATE versus_match_players SET finished_at = COALESCE(finished_at, %s)"
        " WHERE match_id = %s AND account_id = %s",
        (now, match_id, account_id),
    )


def _question_for_version(conn, bank, version_id):
    """The bank question a stored version points at -- the engine's own
    lookup, repeated here so Versus does not reach into its privates."""
    row = migrate.fetch_one(
        conn,
        "SELECT bank_key, content_sha256 FROM question_versions WHERE id = %s",
        (version_id,),
    )
    for question in bank.questions:
        if (
            question.canonical_id == row["bank_key"]
            and question_content_digest(question) == row["content_sha256"]
        ):
            return question
    raise MatchRefused("The stored question is not in the current bank.")
