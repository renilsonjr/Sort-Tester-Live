"""Prize tie-breaks: finding the ties that need one, and opening round 1
(issue #24, slice 1).

The owner's rule, settled 2026-11-15: **a quiz runs only when more players
are competing for the three hats than there are hats.** Players tied
inside the top three share their place and all take a hat; nobody plays a
quiz that cannot change who wins something.

In practice: take the eligible standings, find the score of the player in
third position, and count how many players have at least that score. Three
or fewer, and every one of them wins outright. More than three, and the
players **at** that score form a tie group competing for the hats left over
once everybody strictly above has taken theirs.

    900, 900, 800, 700  ->  places 1, 1, 3: three winners, no quiz
    900, 800, 700, 700  ->  places 1, 2, 3, 3: the two at 700 play for one hat
    900, 900, 900, 900  ->  four players for three hats: all four play

Fewer than three eligible players means fewer hats and no quiz (settled
Q14: never fabricate winners).

Round 1's deadline is the season's **scheduled** close plus 24 hours, as
the record words it, not the moment the freeze happened to run. The round
opens at the freeze, because that is when every eligible attempt has
settled and the tied score is final.
"""

import secrets
from dataclasses import dataclass
from datetime import timedelta

from backend.db import migrate
from backend.ranked import standings
from backend.ranked.versions import materialize_question_version

HATS = 3
ROUND_WINDOW = timedelta(hours=24)
QUESTIONS_PER_ROUND = 5

# Unpredictable rather than reproducible: a player who could work out the
# next round's questions from the last one would have them before the
# round opened. Tests pass their own generator.
_SYSTEM_RANDOM = secrets.SystemRandom()


class NoFreshSet(Exception):
    """Fewer than five unused Hard questions remain this season.

    Settled Decisions 9-10: the affected prize places then wait for the
    owner's selection. Questions are never reused and content is never
    approved on the fly to fill the gap.
    """


def _hard_questions(bank):
    return [q for q in bank.questions if q.difficulty.lower() == "hard"]


def fresh_questions(conn, season_id, bank) -> list:
    """The Hard questions no tie-break round of this season has used yet,
    valid or voided alike, since every one of them was seen by players."""
    used = {
        row["bank_key"]
        for row in migrate.fetch_all(
            conn,
            "SELECT bank_key FROM tiebreak_round_questions WHERE season_id = %s",
            (season_id,),
        )
    }
    return [q for q in _hard_questions(bank) if q.canonical_id not in used]


def assign_round_questions(conn, round_id, season_id, bank, *, rng=None) -> list:
    """Give a round its five shared questions, or raise ``NoFreshSet``.

    Does not commit. The schema refuses a reused question even if this code
    were wrong, so a race between two rounds fails loudly instead of
    quietly handing both the same question.
    """
    pool = fresh_questions(conn, season_id, bank)
    if len(pool) < QUESTIONS_PER_ROUND:
        raise NoFreshSet()
    random_ = rng or _SYSTEM_RANDOM
    chosen = random_.sample(pool, QUESTIONS_PER_ROUND)
    belts = all_belts(bank)
    for seq, question in enumerate(chosen, start=1):
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_round_questions"
            " (round_id, seq, question_version_id, season_id, bank_key, options)"
            " VALUES (%s, %s, %s, %s, %s, %s)",
            (
                round_id,
                seq,
                materialize_question_version(conn, question),
                season_id,
                question.canonical_id,
                draw_options(question.correct_belt, belts, random_),
            ),
        )
    return chosen


OPTIONS_PER_QUESTION = 4


def all_belts(bank) -> list:
    """Every belt the bank routes to, in a fixed order."""
    return sorted({q.correct_belt for q in bank.questions})


def draw_options(correct, belts, random_) -> list:
    """The right belt and three others drawn at random, in random order
    (owner decision 2026-11-15). Drawn with the server's randomness and
    stored, never derived: see migration 0033 for why a formula would leak
    the answer."""
    others = [b for b in belts if b != correct]
    options = random_.sample(others, OPTIONS_PER_QUESTION - 1) + [correct]
    random_.shuffle(options)
    return options


def options_for(conn, attempt_id, seq, bank) -> list | None:
    """The four belts a tie-break question offers, the same for every
    player in the round, or ``None`` for an attempt that is not a
    tie-break. A row written before options existed gets them drawn and
    stored now, once, under a lock, so every player still sees the same."""
    row = migrate.fetch_one(
        conn,
        "SELECT q.round_id, q.options, q.bank_key FROM tiebreak_attempts t"
        " JOIN tiebreak_round_questions q ON q.round_id = t.round_id AND q.seq = %s"
        " WHERE t.attempt_id = %s FOR UPDATE OF q",
        (seq, attempt_id),
    )
    if row is None:
        return None
    if row["options"] is not None:
        return list(row["options"])
    correct = next(q.correct_belt for q in bank.questions if q.canonical_id == row["bank_key"])
    options = draw_options(correct, all_belts(bank), _SYSTEM_RANDOM)
    migrate.execute(
        conn,
        "UPDATE tiebreak_round_questions SET options = %s WHERE round_id = %s AND seq = %s",
        (options, row["round_id"], seq),
    )
    return options


def fresh_sets_left(conn, season_id, bank) -> int:
    """How many more rounds this season can still be given fresh questions."""
    return len(fresh_questions(conn, season_id, bank)) // QUESTIONS_PER_ROUND


@dataclass(frozen=True)
class PrizeTie:
    tied_points: int
    hats_available: int
    account_ids: tuple


def prize_tie(rows) -> PrizeTie | None:
    """The tie that needs a quiz in these standings, or ``None``.

    ``rows`` is the eligible standings, best first, as
    ``backend.ranked.standings.standings`` returns them. Pure: no database.
    """
    if len(rows) <= HATS:
        return None
    cut = rows[HATS - 1].points
    contenders = [row for row in rows if row.points >= cut]
    if len(contenders) <= HATS:
        return None
    above = sum(1 for row in rows if row.points > cut)
    tied = tuple(row.account_id for row in rows if row.points == cut)
    return PrizeTie(tied_points=cut, hats_available=HATS - above, account_ids=tied)


def open_prize_tiebreaks(conn, season_id, *, clock, bank=None, rng=None):
    """Open the season-close tie group and its round 1, when one is needed.

    Called inside the freeze's transaction, so the freeze and the group
    are written together or not at all. Safe to call again: a season has
    at most one season-close group. Returns the group id, or ``None`` when
    the standings need no quiz. Does not commit.
    """
    season = migrate.fetch_one(
        conn,
        "SELECT phase, closes_at, closed_at FROM seasons WHERE id = %s",
        (season_id,),
    )
    if season is None or season["phase"] != "official":
        return None  # Pre-Season awards no hats
    existing = migrate.fetch_one(
        conn,
        "SELECT id FROM tiebreak_groups"
        " WHERE season_id = %s AND reason = 'season_close'",
        (season_id,),
    )
    if existing is not None:
        return existing["id"]
    tie = prize_tie(standings.standings(conn, season_id))
    if tie is None:
        return None
    scheduled_close = season["closes_at"] or season["closed_at"]
    now = clock.now()
    group_id = migrate.fetch_one(
        conn,
        "INSERT INTO tiebreak_groups"
        " (season_id, reason, tied_points, hats_available, opened_at)"
        " VALUES (%s, 'season_close', %s, %s, %s) RETURNING id",
        (season_id, tie.tied_points, tie.hats_available, now),
    )["id"]
    for account_id in tie.account_ids:
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
            (group_id, account_id),
        )
    deadline = scheduled_close + ROUND_WINDOW
    if deadline <= now:
        # The freeze ran so late that the scheduled deadline has passed. The
        # record says the first deadline is the scheduled close plus 24h, so
        # it is not stretched; but a round must be playable, so it gets the
        # full window from now. Recorded on the round, not hidden.
        deadline = now + ROUND_WINDOW
    if bank is None:
        from backend.ranked_bank.catalog import load_reviewed_bank

        bank = load_reviewed_bank()
    if fresh_sets_left(conn, season_id, bank) == 0:
        # No round can be played, so none is opened: the places wait for
        # the owner, which is the settled fallback, not a failure.
        migrate.execute(
            conn,
            "UPDATE tiebreak_groups SET status = 'owner_selection' WHERE id = %s",
            (group_id,),
        )
        return group_id
    _open_round(
        conn, group_id, season_id, 1, tie.account_ids, tie.hats_available,
        opened_at=now, deadline_at=deadline, bank=bank, rng=rng,
    )
    return group_id


def _open_round(conn, group_id, season_id, number, players, hats, *,
                opened_at, deadline_at, bank, rng=None):
    """Open a round for exactly these players, deciding ``hats`` hats, with
    its five fresh questions. Raises ``NoFreshSet`` before writing anything
    when no fresh set is left."""
    if fresh_sets_left(conn, season_id, bank) == 0:
        raise NoFreshSet()
    round_id = migrate.fetch_one(
        conn,
        "INSERT INTO tiebreak_rounds"
        " (group_id, round_number, opened_at, deadline_at, hats)"
        " VALUES (%s, %s, %s, %s, %s) RETURNING id",
        (group_id, number, opened_at, deadline_at, hats),
    )["id"]
    for account_id in players:
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_round_players (round_id, account_id) VALUES (%s, %s)",
            (round_id, account_id),
        )
    assign_round_questions(conn, round_id, season_id, bank, rng=rng)
    return round_id


# --- closing a round (slice 4) -------------------------------------------

CHALLENGER_MAX_ROUNDS = 3
LOWER_MAX_ROUNDS = 5


@dataclass(frozen=True)
class RoundResult:
    account_id: object
    outcome: str        # 'completed', 'incomplete' or 'no_show'
    score: int | None   # 0-5 when completed, else None


@dataclass(frozen=True)
class RoundDecision:
    statuses: dict          # account_id -> 'hat', 'no_hat', 'excluded',
                            #               'owner_selection' or 'next_round'
    next_round_hats: int    # hats the next round decides, 0 if none


def decide_round(results, hats, *, challenger, round_number) -> RoundDecision:
    """What a closed round settles, by the record's rules. Pure: no database.

    * Completed attempts outrank incomplete ones and no-shows. A completed
      0/5 is still completed.
    * Among completed players, higher scores take hats first. A score level
      that fits in the hats left takes them all; one that does not is still
      tied and plays the next round for the hats left -- or, after the
      maximum number of rounds, waits for the owner.
    * Challenger: an incomplete attempt or a no-show is excluded from the
      prizes, both players if both fail. Their hats are not handed down
      here; filling them is the backfill (slice 8).
    * Lower ranks: hats still left after every completed player go to the
      incomplete and no-show players only if they all fit; if several are
      competing for fewer hats, the owner selects, with no extra quiz.
    """
    max_rounds = CHALLENGER_MAX_ROUNDS if challenger else LOWER_MAX_ROUNDS
    completed = sorted(
        (r for r in results if r.outcome == "completed"), key=lambda r: -r.score
    )
    others = [r for r in results if r.outcome != "completed"]
    statuses = {}
    remaining = hats
    next_hats = 0
    for score in sorted({r.score for r in completed}, reverse=True):
        level = [r for r in completed if r.score == score]
        if remaining == 0:
            status = "no_hat"
        elif len(level) <= remaining:
            status = "hat"
            remaining -= len(level)
        else:
            if round_number < max_rounds:
                status = "next_round"
                next_hats = remaining
            else:
                status = "owner_selection"
            remaining = 0
        for r in level:
            statuses[r.account_id] = status
    if challenger:
        for r in others:
            statuses[r.account_id] = "excluded"
    elif remaining > 0 and others:
        status = "hat" if len(others) <= remaining else "owner_selection"
        for r in others:
            statuses[r.account_id] = status
    else:
        for r in others:
            statuses[r.account_id] = "no_hat"
    return RoundDecision(statuses=statuses, next_round_hats=next_hats)


def close_round(conn, round_id, *, clock, bank=None, rng=None) -> bool:
    """Close a round whose deadline has passed: end what is still running,
    score every player, write where each one stands, and open the next
    round when the rules call for one. Returns True when this call closed
    it; False when it was not due or already closed. Commits.
    """
    now = clock.now()
    round_ = migrate.fetch_one(
        conn,
        "SELECT r.id, r.round_number, r.status, r.deadline_at, r.hats,"
        " g.id AS group_id, g.season_id, g.tied_points"
        " FROM tiebreak_rounds r JOIN tiebreak_groups g ON g.id = r.group_id"
        " WHERE r.id = %s FOR UPDATE OF r",
        (round_id,),
    )
    if round_ is None or round_["status"] != "open" or now < round_["deadline_at"]:
        conn.commit()
        return False
    # an attempt still running at the deadline ends there: the deadline is
    # the round's, and a late start never moved it
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'finalized', final_outcome = 'round_deadline',"
        " settled_at = %s"
        " WHERE id IN (SELECT attempt_id FROM tiebreak_attempts WHERE round_id = %s)"
        " AND state IN ('active', 'grace')",
        (now, round_id),
    )
    players = [
        row["account_id"]
        for row in migrate.fetch_all(
            conn,
            "SELECT account_id FROM tiebreak_round_players WHERE round_id = %s",
            (round_id,),
        )
    ]
    results = [_result_for(conn, round_id, account_id) for account_id in players]
    for r in results:
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_round_results (round_id, account_id, outcome, score)"
            " VALUES (%s, %s, %s, %s)",
            (round_id, r.account_id, r.outcome, r.score),
        )
    from backend.ranked import ranks

    decision = decide_round(
        results,
        round_["hats"],
        challenger=ranks.badge_for(round_["tied_points"]) == ranks.TOP_BADGE,
        round_number=round_["round_number"],
    )
    still_tied = [a for a, s in decision.statuses.items() if s == "next_round"]
    if still_tied:
        if bank is None:
            from backend.ranked_bank.catalog import load_reviewed_bank

            bank = load_reviewed_bank()
        try:
            _open_round(
                conn, round_["group_id"], round_["season_id"],
                round_["round_number"] + 1, still_tied, decision.next_round_hats,
                opened_at=now, deadline_at=now + ROUND_WINDOW, bank=bank, rng=rng,
            )
        except NoFreshSet:
            # no fresh questions left: the still-tied players wait for the
            # owner, which is the settled fallback
            for account_id in still_tied:
                decision.statuses[account_id] = "owner_selection"
            still_tied = []
    for account_id, status in decision.statuses.items():
        if status == "next_round":
            continue
        migrate.execute(
            conn,
            "INSERT INTO tiebreak_placements"
            " (group_id, account_id, status, decided_in_round)"
            " VALUES (%s, %s, %s, %s)",
            (round_["group_id"], account_id, status, round_["round_number"]),
        )
    migrate.execute(
        conn, "UPDATE tiebreak_rounds SET status = 'closed' WHERE id = %s", (round_id,)
    )
    if not still_tied:
        waiting = any(s == "owner_selection" for s in decision.statuses.values())
        migrate.execute(
            conn,
            "UPDATE tiebreak_groups SET status = %s WHERE id = %s",
            ("owner_selection" if waiting else "resolved", round_["group_id"]),
        )
    conn.commit()
    return True


def _result_for(conn, round_id, account_id) -> RoundResult:
    attempt = migrate.fetch_one(
        conn,
        "SELECT a.id, a.final_outcome FROM tiebreak_attempts t"
        " JOIN attempts a ON a.id = t.attempt_id"
        " WHERE t.round_id = %s AND t.account_id = %s",
        (round_id, account_id),
    )
    if attempt is None:
        return RoundResult(account_id, "no_show", None)
    if attempt["final_outcome"] != "completed":
        return RoundResult(account_id, "incomplete", None)
    score = migrate.fetch_one(
        conn,
        "SELECT count(*) AS n FROM attempt_answers"
        " WHERE attempt_id = %s AND answer = 'correct'",
        (attempt["id"],),
    )["n"]
    return RoundResult(account_id, "completed", score)


def close_due_rounds(conn, *, clock, bank=None) -> int:
    """Close every open round whose deadline has passed. There is no
    background timer, so this runs on requests, like the season close."""
    due = migrate.fetch_all(
        conn,
        "SELECT id FROM tiebreak_rounds WHERE status = 'open' AND deadline_at <= %s",
        (clock.now(),),
    )
    conn.commit()
    return sum(1 for row in due if close_round(conn, row["id"], clock=clock, bank=bank))


def revealed_result(conn, attempt_id) -> dict | None:
    """A player's own tie-break result, or ``None`` while the round is
    still open. Their own line only: never another player's score."""
    row = migrate.fetch_one(
        conn,
        "SELECT r.status AS round_status, r.round_number, r.group_id, t.account_id,"
        " res.outcome, res.score, p.status AS placement"
        " FROM tiebreak_attempts t"
        " JOIN tiebreak_rounds r ON r.id = t.round_id"
        " LEFT JOIN tiebreak_round_results res"
        "   ON res.round_id = t.round_id AND res.account_id = t.account_id"
        " LEFT JOIN tiebreak_placements p"
        "   ON p.group_id = r.group_id AND p.account_id = t.account_id"
        " WHERE t.attempt_id = %s",
        (attempt_id,),
    )
    conn.commit()
    if row is None or row["round_status"] != "closed":
        return None
    return {
        "round": row["round_number"],
        "outcome": row["outcome"],
        "score": row["score"],
        # None means a later round is still deciding this player's place
        "placement": row["placement"],
    }


# --- confirmed outages (slice 5) -----------------------------------------

def void_rounds_for_outage(conn, *, outage_start, outage_end, clock, bank=None,
                           rng=None) -> int:
    """Restart every open round a confirmed outage interrupted; return how many.

    Settled Decisions 9-10: a confirmed server outage interrupting an
    attempt restarts the **whole current round** for all its players,
    including those who had already finished, with fresh questions and a
    new 24-hour window. Earlier valid rounds stand. The restart keeps the
    round's number, so it uses the same seconds per question and does not
    count towards the three- or five-round limit.

    A round is interrupted when one of its attempts was running during the
    outage. A round nobody was playing at the time is not restarted: the
    outage took nothing from it. Rounds already closed are left as they
    are; this applies to the round still being played.

    The voided round's questions stay used for the season, because its
    players saw them, and its results are never revealed.
    """
    rounds = migrate.fetch_all(
        conn,
        "SELECT DISTINCT r.id FROM tiebreak_rounds r"
        " JOIN tiebreak_attempts t ON t.round_id = r.id"
        " JOIN attempts a ON a.id = t.attempt_id"
        " WHERE r.status = 'open'"
        " AND a.started_at <= %s"
        " AND COALESCE(a.settled_at, 'infinity'::timestamptz) >= %s",
        (outage_end, outage_start),
    )
    conn.commit()
    if not rounds:
        return 0
    if bank is None:
        from backend.ranked_bank.catalog import load_reviewed_bank

        bank = load_reviewed_bank()
    restarted = 0
    for row in rounds:
        if _restart_round(conn, row["id"], clock=clock, bank=bank, rng=rng):
            restarted += 1
    return restarted


def _restart_round(conn, round_id, *, clock, bank, rng) -> bool:
    now = clock.now()
    round_ = migrate.fetch_one(
        conn,
        "SELECT r.id, r.round_number, r.hats, r.status, g.id AS group_id, g.season_id"
        " FROM tiebreak_rounds r JOIN tiebreak_groups g ON g.id = r.group_id"
        " WHERE r.id = %s FOR UPDATE OF r",
        (round_id,),
    )
    if round_ is None or round_["status"] != "open":
        conn.commit()
        return False
    # every attempt of the round ends, finished ones included: the whole
    # round is played again, so none of its scores will ever count
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'finalized', final_outcome = 'outage_void',"
        " settled_at = COALESCE(settled_at, %s)"
        " WHERE id IN (SELECT attempt_id FROM tiebreak_attempts WHERE round_id = %s)"
        " AND state IN ('active', 'grace')",
        (now, round_id),
    )
    migrate.execute(
        conn, "UPDATE tiebreak_rounds SET status = 'void' WHERE id = %s", (round_id,)
    )
    players = [
        row["account_id"]
        for row in migrate.fetch_all(
            conn,
            "SELECT account_id FROM tiebreak_round_players WHERE round_id = %s",
            (round_id,),
        )
    ]
    try:
        _open_round(
            conn, round_["group_id"], round_["season_id"], round_["round_number"],
            players, round_["hats"],
            opened_at=now, deadline_at=now + ROUND_WINDOW, bank=bank, rng=rng,
        )
    except NoFreshSet:
        # no fresh questions for the restart: the places wait for the owner,
        # as for any round that cannot be given a fresh set
        for account_id in players:
            migrate.execute(
                conn,
                "INSERT INTO tiebreak_placements"
                " (group_id, account_id, status, decided_in_round)"
                " VALUES (%s, %s, 'owner_selection', %s)"
                " ON CONFLICT (group_id, account_id) DO NOTHING",
                (round_["group_id"], account_id, round_["round_number"]),
            )
        migrate.execute(
            conn,
            "UPDATE tiebreak_groups SET status = 'owner_selection' WHERE id = %s",
            (round_["group_id"],),
        )
    conn.commit()
    return True


# --- the owner's selection (slice 6) -------------------------------------

class SelectionError(Exception):
    """A refusal with a reason the owner may be shown."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def _require_owner(conn, owner_account_id) -> None:
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM accounts WHERE id = %s AND is_owner AND deleted_at IS NULL",
        (owner_account_id,),
    )
    if row is None:
        raise SelectionError("Only the owner may select.")


def _hats_left(conn, group) -> int:
    given = migrate.fetch_one(
        conn,
        "SELECT count(*) AS n FROM tiebreak_placements WHERE group_id = %s AND status = 'hat'",
        (group["id"],),
    )["n"]
    return group["hats_available"] - given


def selection_cases(conn, owner_account_id) -> list[dict]:
    """The ties waiting for the owner, each with its players' tie-break
    history -- the owner decided on 2026-11-15 to see it, so the choice is
    made with the same information the quiz had. Voided rounds are left out:
    they never counted. Nothing else about the players is returned, and no
    points appear, because none can be changed here."""
    _require_owner(conn, owner_account_id)
    groups = migrate.fetch_all(
        conn,
        "SELECT id, tied_points, hats_available FROM tiebreak_groups"
        " WHERE status = 'owner_selection' ORDER BY tied_points DESC, opened_at",
    )
    cases = []
    for group in groups:
        players = migrate.fetch_all(
            conn,
            "SELECT a.id, a.username, a.tag FROM tiebreak_placements p"
            " JOIN accounts a ON a.id = p.account_id"
            " WHERE p.group_id = %s AND p.status = 'owner_selection' AND a.deleted_at IS NULL"
            " ORDER BY a.username",
            (group["id"],),
        )
        for player in players:
            player["history"] = migrate.fetch_all(
                conn,
                "SELECT r.round_number, res.outcome, res.score"
                " FROM tiebreak_round_results res"
                " JOIN tiebreak_rounds r ON r.id = res.round_id"
                " WHERE r.group_id = %s AND res.account_id = %s AND r.status = 'closed'"
                " ORDER BY r.round_number",
                (group["id"], player["id"]),
            )
        cases.append({
            "group_id": group["id"],
            "tied_points": group["tied_points"],
            "hats": _hats_left(conn, group),
            "players": players,
        })
    conn.commit()
    return cases


def record_selection(conn, owner_account_id, group_id, chosen_ids, *, clock) -> None:
    """Give the hats left in a waiting tie to exactly these players. Final.

    Only the players the rules sent to the owner may be chosen, and exactly
    as many as there are hats left. The others in the tie take none. No
    points, badge or tie-break result changes. Recorded with who chose and
    when; a second selection on the same tie is refused rather than
    overwriting the first.
    """
    _require_owner(conn, owner_account_id)
    group = migrate.fetch_one(
        conn,
        "SELECT id, status, hats_available FROM tiebreak_groups WHERE id = %s FOR UPDATE",
        (group_id,),
    )
    if group is None:
        conn.rollback()
        raise SelectionError("There is no such tie.")
    if group["status"] != "owner_selection":
        conn.rollback()
        raise SelectionError("That tie is already settled. A selection is final.")
    pending = {
        row["account_id"]
        for row in migrate.fetch_all(
            conn,
            "SELECT account_id FROM tiebreak_placements"
            " WHERE group_id = %s AND status = 'owner_selection'",
            (group_id,),
        )
    }
    chosen = set(chosen_ids)
    if not chosen <= pending:
        conn.rollback()
        raise SelectionError("Only the players waiting in this tie can be chosen.")
    hats = _hats_left(conn, group)
    if len(chosen) != hats:
        conn.rollback()
        raise SelectionError(f"Choose exactly {hats}.")
    for account_id in pending:
        migrate.execute(
            conn,
            "UPDATE tiebreak_placements SET status = %s WHERE group_id = %s AND account_id = %s",
            ("hat" if account_id in chosen else "no_hat", group_id, account_id),
        )
    migrate.execute(
        conn,
        "UPDATE tiebreak_groups SET status = 'resolved', selected_by = %s, selected_at = %s"
        " WHERE id = %s",
        (owner_account_id, clock.now(), group_id),
    )
    conn.commit()


# --- what a player is told about their own tie (slice 7) ------------------

def my_tiebreak(conn, account_id) -> dict | None:
    """This player's tie-break, for their own screens, or ``None``.

    Their own state only: the round they may play, whether they have
    played it, and -- once a round has closed -- their own score and where
    they stand. Never another player's score, and never the other players'
    names: the tie is between them, but the screen does not need to say
    with whom.
    """
    group = migrate.fetch_one(
        conn,
        "SELECT g.id, g.status, g.tied_points, g.hats_available"
        " FROM tiebreak_group_members m"
        " JOIN tiebreak_groups g ON g.id = m.group_id"
        " JOIN seasons s ON s.id = g.season_id"
        " WHERE m.account_id = %s"
        " ORDER BY s.opened_at DESC, g.opened_at DESC LIMIT 1",
        (account_id,),
    )
    if group is None:
        conn.commit()
        return None
    placement = migrate.fetch_one(
        conn,
        "SELECT status FROM tiebreak_placements WHERE group_id = %s AND account_id = %s",
        (group["id"], account_id),
    )
    open_round = migrate.fetch_one(
        conn,
        "SELECT r.id, r.round_number, r.deadline_at, r.hats, t.attempt_id"
        " FROM tiebreak_rounds r"
        " JOIN tiebreak_round_players p ON p.round_id = r.id AND p.account_id = %s"
        " LEFT JOIN tiebreak_attempts t ON t.round_id = r.id AND t.account_id = %s"
        " WHERE r.group_id = %s AND r.status = 'open'",
        (account_id, account_id, group["id"]),
    )
    last = migrate.fetch_one(
        conn,
        "SELECT r.round_number, res.outcome, res.score FROM tiebreak_round_results res"
        " JOIN tiebreak_rounds r ON r.id = res.round_id"
        " WHERE r.group_id = %s AND res.account_id = %s AND r.status = 'closed'"
        " ORDER BY r.round_number DESC LIMIT 1",
        (group["id"], account_id),
    )
    conn.commit()
    from backend.ranked import modes, ranks

    out = {
        "tied_points": group["tied_points"],
        "challenger": ranks.badge_for(group["tied_points"]) == ranks.TOP_BADGE,
        "placement": None if placement is None else placement["status"],
        "last_result": None if last is None else {
            "round": last["round_number"], "outcome": last["outcome"], "score": last["score"],
        },
        "round": None,
    }
    if open_round is not None:
        out["round"] = {
            "id": open_round["id"],
            "number": open_round["round_number"],
            "deadline_at": open_round["deadline_at"],
            "hats": open_round["hats"],
            "seconds": modes.TIEBREAK_SECONDS[open_round["round_number"]],
            "played": open_round["attempt_id"] is not None,
            "attempt_id": open_round["attempt_id"],
        }
    return out
