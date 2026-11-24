"""Server-authoritative ranked attempt engine (issue #8).

Runs an attempt from start to finish on the server: it assigns the questions,
serves them one at a time on server-owned deadlines (how many questions and
how many seconds come from the attempt's mode, see ``modes``),
accepts a single locked answer each, runs forward-only, and ends the attempt
in ``terminal_pending``. It records per-answer results only; computing the
score, caps, and balance is #9, which reads the finalized answers and
transitions ``terminal_pending -> finalized``.

The engine also owns the connection clock. The page sends a heartbeat every
second; three seconds of silence is a connection loss, and the player then has
fifteen seconds of grace to come back. There is no background timer: each call
first checks how long the attempt has been silent, and an attempt silent past
its grace deadline ends as a ``disconnect``.

Every function takes an explicit DB connection and (where time matters) a clock,
so callers own transactions and tests control time. The engine never reads the
wall clock directly.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.db import migrate
from backend.ranked import belt_options, modes, ranks, seasons
from backend.ranked.capability import hash_token
from backend.ranked.versions import materialize_question_version
from backend.ranked_bank.identity import question_content_digest
from backend.ranked_bank.display import routing_code_for
from backend.ranked_bank.selection import select_assignment

HEARTBEAT_LOSS_SECONDS = 3
GRACE_SECONDS = 15

# When this server process started, or ``None`` when nobody has said.
#
# Owner decision 2026-11-22 (issue #13, box 3): the app's own restart is the
# trusted evidence of a common outage; there are no external probes. An
# attempt that went silent *before* this process started and is found past
# its grace deadline was cut off by the server going away, not by the
# player, so it is voided with a zero adjustment instead of being charged
# as a disconnect. A silence that began after the start is the player's own.
#
# That alone would be far too generous: attempts are ended lazily, so one
# abandoned days ago would be voided by the next deploy, and walking away
# from a bad quiz would beat quitting it. So the silence must also reach
# the outage: the attempt's grace deadline must not be older than the last
# thing the server is known to have done before this process started (an
# answer accepted, an attempt started, a login). If the server went on
# working after this player's deadline, the silence was their own.
#
# Known and accepted: a player who dropped by themselves within those last
# seconds before a restart (a deploy is one) is voided too. A database
# outage with no restart is not seen here.
#
# ``backend.main`` sets it when the server really starts and clears it when
# it stops. Left at ``None`` the engine behaves as it did before, which is
# what tests with their own clock want.
_process_started_at: datetime | None = None
# (process start it was read for, moment or None): read once per process.
# Safe to keep: these are timestamps of rows written before the start, and
# no such row can be written afterwards.
_activity_before_start: tuple | None = None


def set_process_started_at(moment: datetime | None) -> None:
    global _process_started_at, _activity_before_start
    _process_started_at = moment
    _activity_before_start = None


def _last_activity_before_start(conn):
    global _activity_before_start
    started = _process_started_at
    if _activity_before_start is None or _activity_before_start[0] != started:
        row = migrate.fetch_one(
            conn,
            "SELECT GREATEST("
            " (SELECT max(accepted_at) FROM attempt_answers WHERE accepted_at < %s),"
            " (SELECT max(started_at) FROM attempts WHERE started_at < %s),"
            " (SELECT max(created_at) FROM sessions WHERE created_at < %s)) AS at",
            (started, started, started),
        )
        _activity_before_start = (started, row["at"])
    return _activity_before_start[1]


def _cut_off_by_restart(conn, heard_at, deadline) -> bool:
    if _process_started_at is None or heard_at >= _process_started_at:
        return False
    alive_until = _last_activity_before_start(conn)
    return alive_until is None or deadline >= alive_until


class _At:
    """A clock fixed at one moment, for code that asks a clock the time."""

    def __init__(self, moment):
        self._moment = moment

    def now(self):
        return self._moment


class EngineError(Exception):
    """Base class for ranked engine errors."""


class NoOpenSeasonError(EngineError):
    """No season is open to admit a new attempt."""


class ActiveAttemptExistsError(EngineError):
    """The account already has an unfinished attempt."""


class PromotionRequiredError(EngineError):
    """The account is at its badge cap: only a promotion attempt may start."""


class PromotionNotAvailableError(EngineError):
    """The account is not at a badge cap: a promotion attempt cannot start."""


class AnswerRejectedError(EngineError):
    """The submitted answer is not acceptable (wrong question, late, or done)."""


class NotAnsweredError(EngineError):
    """Advance was requested before the current question was answered."""


class AttemptEndedError(EngineError):
    """The attempt has ended; no further calls are accepted for it."""


@dataclass(frozen=True)
class EntryStatus:
    points: int
    badge: str
    mode: str  # the only kind of attempt this account may start now


@dataclass(frozen=True)
class QuestionView:
    seq: int
    deadline_at: datetime
    prompt_en: str
    prompt_es: str
    # What the question is actually about. The prompt alone is "Which belt
    # does this go to?", so a screen needs the service, the state and the
    # code to ask anything at all. None of this reveals the answer.
    service: str = ""
    mode: str = ""
    routing_code: str = ""
    region_label: str = ""
    named_destination: str | None = None
    # The four belts offered, for a tie-break; None where the screen offers
    # every belt or has not been built yet.
    options: list | None = None


@dataclass(frozen=True)
class AnswerResult:
    seq: int
    correct: bool
    outcome: str  # 'correct', 'wrong' or 'timeout'
    finished: bool  # True when this answer was the final one and ended the attempt
    # Feedback for an ordinary or promotion screen: the belt that was
    # actually right, its difficulty, the worth of this one question under
    # ordinary scoring, and the bilingual explanation. None for a tie-break,
    # which reveals none of this until its round closes (settled Q4).
    correct_belt: str | None = None
    difficulty: str | None = None
    worth: int | None = None
    explanation_en: str | None = None
    explanation_es: str | None = None


@dataclass(frozen=True)
class AdvanceResult:
    next_seq: int


def entry_status(conn, account_id) -> EntryStatus:
    """Report the account's points, badge and the attempt kind it may start.

    Read-only. An account with no balance row has zero points.
    """
    row = migrate.fetch_one(
        conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,)
    )
    points = row["current_points"] if row is not None else 0
    return EntryStatus(
        points=points, badge=ranks.badge_for(points), mode=ranks.entry_mode(points)
    )


def start_attempt(
    conn, account_id, *, clock, bank, page_capability=None, mode=ranks.NORMAL
) -> str:
    """Assign the questions, open an ``active`` attempt, and send question 1.

    ``mode`` is the kind of attempt the player explicitly asked for. At a
    badge cap only ``promotion`` may start, anywhere else only ``normal``; the
    engine never converts one into the other. A refusal raises
    :class:`PromotionRequiredError` or :class:`PromotionNotAvailableError`
    before anything is written. A promotion attempt runs exactly like a
    normal one here; its scoring is #9.

    Raises :class:`NoOpenSeasonError` when no season is open and
    :class:`ActiveAttemptExistsError` when the account already has an
    unfinished attempt. On the latter the whole transaction is rolled back.

    ``page_capability`` is the raw page-instance token issued to the starting
    page; only its hash is stored, in the same transaction as the attempt.
    """
    capability_hash = (
        hash_token(page_capability) if page_capability is not None else None
    )
    # close out an attempt this account walked away from before admitting
    expire_stale_attempts(conn, clock=clock, account_id=account_id)
    if mode not in (ranks.NORMAL, ranks.PROMOTION):
        raise EngineError(f"unsupported attempt mode: {mode!r}")
    # the gate reads current server state; an ended-but-unsettled attempt
    # still holds the account lock, so this total is never stale
    allowed = entry_status(conn, account_id).mode
    if mode != allowed:
        if allowed == ranks.PROMOTION:
            raise PromotionRequiredError("at the badge cap only promotion can start")
        raise PromotionNotAvailableError("promotion is only available at a badge cap")
    season_id = _open_season(conn, clock.now())
    snapshot = select_assignment(bank)
    expected = modes.settings_for(mode).question_count
    if len(snapshot.questions) != expected:
        # refuse before writing: a quiz of the wrong length must never start
        raise EngineError(
            f"assignment has {len(snapshot.questions)} questions,"
            f" {mode} attempts need {expected}"
        )
    assignment = migrate.fetch_one(
        conn,
        "INSERT INTO assignments (account_id, mode, season_id)"
        " VALUES (%s, %s, %s) RETURNING id",
        (account_id, mode, season_id),
    )
    assignment_id = assignment["id"]
    now = clock.now()
    try:
        # started_at comes from the engine clock, not the database default,
        # so every time the engine compares is from one source
        attempt = migrate.fetch_one(
            conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, state, season_id,"
            " started_at, last_heartbeat_at, page_capability_sha256)"
            " VALUES (%s, %s, %s, 'active', %s, %s, %s, %s) RETURNING id",
            (account_id, assignment_id, mode, season_id, now, now, capability_hash),
        )
    except migrate.IntegrityError:
        conn.rollback()
        raise ActiveAttemptExistsError(
            "account already has an unfinished attempt"
        ) from None
    attempt_id = attempt["id"]
    belts = belt_options.all_belts(bank)
    for seq, question in enumerate(snapshot.questions, start=1):
        version_id = materialize_question_version(conn, question)
        migrate.execute(
            conn,
            "INSERT INTO assignment_questions"
            " (assignment_id, seq, question_version_id, options)"
            " VALUES (%s, %s, %s, %s)",
            (
                assignment_id, seq, version_id,
                belt_options.draw_options(question.correct_belt, belts),
            ),
        )
    _send_question(conn, attempt_id, 1, clock)
    conn.commit()
    return attempt_id


class TiebreakEntryError(EngineError):
    """This account may not start an attempt in this tie-break round. The
    message says why in words a player can be shown."""


def start_tiebreak_attempt(
    conn, account_id, round_id, *, clock, page_capability=None
) -> str:
    """Open this player's one attempt in a tie-break round and send question 1.

    Only a member of the round's group, only while the round is open and
    before its deadline, and only once per round (settled Decisions 9-10). A
    late start does not move the deadline. The five questions are the
    round's shared set, copied into the attempt's own assignment so the
    rest of the engine plays them like any other attempt.
    """
    capability_hash = (
        hash_token(page_capability) if page_capability is not None else None
    )
    expire_stale_attempts(conn, clock=clock, account_id=account_id)
    now = clock.now()
    round_ = migrate.fetch_one(
        conn,
        "SELECT r.id, r.round_number, r.status, r.deadline_at,"
        " g.id AS group_id, g.status AS group_status, g.season_id"
        " FROM tiebreak_rounds r JOIN tiebreak_groups g ON g.id = r.group_id"
        " WHERE r.id = %s FOR UPDATE OF r",
        (round_id,),
    )
    if round_ is None:
        conn.commit()
        raise TiebreakEntryError("There is no such tie-break round.")
    # the round's own players, not the whole group: a later round is played
    # only by those still tied after the one before it
    member = migrate.fetch_one(
        conn,
        "SELECT 1 AS m FROM tiebreak_round_players WHERE round_id = %s AND account_id = %s",
        (round_id, account_id),
    )
    if member is None:
        # a non-member learns nothing about the round's state
        conn.commit()
        raise TiebreakEntryError("There is no such tie-break round.")
    # A round past its deadline is usually closed already -- every request
    # closes due rounds first -- so both cases get the same, plain answer.
    if round_["status"] == "closed" or now >= round_["deadline_at"]:
        conn.commit()
        raise TiebreakEntryError("This round has closed.")
    if round_["status"] != "open" or round_["group_status"] != "open":
        conn.commit()
        raise TiebreakEntryError("This round is no longer open.")
    already = migrate.fetch_one(
        conn,
        "SELECT attempt_id FROM tiebreak_attempts WHERE round_id = %s AND account_id = %s",
        (round_id, account_id),
    )
    if already is not None:
        conn.commit()
        raise TiebreakEntryError(
            "You have already played this round. Each round is played once."
        )
    questions = migrate.fetch_all(
        conn,
        "SELECT seq, question_version_id FROM tiebreak_round_questions"
        " WHERE round_id = %s ORDER BY seq",
        (round_id,),
    )
    if len(questions) != modes.TIEBREAK_QUESTIONS:
        conn.rollback()
        raise EngineError("the round does not have its five questions")
    assignment_id = migrate.fetch_one(
        conn,
        "INSERT INTO assignments (account_id, mode, season_id)"
        " VALUES (%s, 'tiebreak', %s) RETURNING id",
        (account_id, round_["season_id"]),
    )["id"]
    try:
        attempt_id = migrate.fetch_one(
            conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, tiebreak_round,"
            " state, season_id, started_at, last_heartbeat_at, page_capability_sha256)"
            " VALUES (%s, %s, 'tiebreak', %s, 'active', %s, %s, %s, %s) RETURNING id",
            (account_id, assignment_id, round_["round_number"], round_["season_id"],
             now, now, capability_hash),
        )["id"]
    except migrate.IntegrityError:
        conn.rollback()
        raise ActiveAttemptExistsError("account already has an unfinished attempt") from None
    for row in questions:
        migrate.execute(
            conn,
            "INSERT INTO assignment_questions (assignment_id, seq, question_version_id)"
            " VALUES (%s, %s, %s)",
            (assignment_id, row["seq"], row["question_version_id"]),
        )
    migrate.execute(
        conn,
        "INSERT INTO tiebreak_attempts (round_id, account_id, attempt_id) VALUES (%s, %s, %s)",
        (round_id, account_id, attempt_id),
    )
    _send_question(conn, attempt_id, 1, clock)
    conn.commit()
    return attempt_id


def current_question(conn, attempt_id, *, clock, bank) -> QuestionView | None:
    """Return the single live question (the one awaiting an answer), or None.

    Reading does not count as activity: it checks the connection clock but
    does not reset it.
    """
    now = clock.now()
    _sync_connection(conn, attempt_id, now, touch=False)
    if _is_tiebreak(conn, attempt_id):
        _advance_timed_out_tiebreak(conn, attempt_id, now, clock)
    row = migrate.fetch_one(
        conn,
        "SELECT seq, question_version_id AS vid, deadline_at FROM attempt_answers"
        " WHERE attempt_id = %s AND answer IS NULL ORDER BY seq LIMIT 1",
        (attempt_id,),
    )
    if row is None:
        conn.commit()  # releases the attempt lock
        return None
    question = _question_for_version(conn, bank, row["vid"])
    if _is_tiebreak(conn, attempt_id):
        from backend.ranked import tiebreaks

        options = tiebreaks.options_for(conn, attempt_id, row["seq"], bank)
    else:
        options = _options_for_assignment(conn, attempt_id, row["seq"], question, bank)
    conn.commit()  # releases the attempt lock
    return QuestionView(
        seq=row["seq"],
        deadline_at=row["deadline_at"],
        prompt_en=question.text.en.prompt,
        prompt_es=question.text.es.prompt,
        service=question.context.service,
        mode=question.context.mode,
        routing_code=routing_code_for(question, attempt_id=attempt_id, seq=row["seq"]),
        region_label=question.presentation.region_label,
        named_destination=question.presentation.named_destination,
        options=options,
    )


def submit_answer(conn, attempt_id, seq, choice, *, clock, bank) -> AnswerResult:
    """Grade and lock one answer. Idempotent: a second submit changes nothing.

    The answer to the final question also completes the attempt, in the same
    transaction: there is no Next after it. So does the first miss of a
    promotion (owner decision, #268): it needs all fifteen right, so nothing
    is sent after a wrong or late answer.
    """
    now = clock.now()
    _sync_connection(conn, attempt_id, now, touch=True)
    row = migrate.fetch_one(
        conn,
        "SELECT question_version_id AS vid, deadline_at, answer FROM attempt_answers"
        " WHERE attempt_id = %s AND seq = %s",
        (attempt_id, seq),
    )
    if row is None:
        conn.commit()  # keep the recorded activity, release the attempt lock
        raise AnswerRejectedError(f"question {seq} has not been sent")
    if row["answer"] is not None:
        # already resolved: report the stored result, write nothing more
        tiebreak = _is_tiebreak(conn, attempt_id)
        conn.commit()
        if tiebreak:
            return _hidden_result(seq)
        question = _question_for_version(conn, bank, row["vid"])
        return _answer_result(seq, row["answer"], question)
    question = _question_for_version(conn, bank, row["vid"])
    if now > row["deadline_at"]:
        # too late: the question timed out and the submitted choice is discarded
        graded = "timeout"
    elif choice is None:
        # No choice means "the clock ran out" (#428), and this clock says it
        # did not. Refusing keeps that the only thing it can mean: a page
        # running fast cannot turn a question nobody answered into a wrong
        # answer, and it still has its remaining seconds when it asks again.
        conn.commit()  # keep the recorded activity, release the attempt lock
        raise AnswerRejectedError(f"question {seq} is still open: a belt is required")
    else:
        graded = "correct" if choice == question.correct_belt else "wrong"
    _record_answer(conn, attempt_id, seq, graded, now)
    finished = (
        seq == _settings(conn, attempt_id).question_count
        or _promotion_lost(conn, attempt_id, graded)
    )
    if finished:
        _complete(conn, attempt_id, now)
    tiebreak = _is_tiebreak(conn, attempt_id)
    if tiebreak and not finished:
        # no Next in a tie-break: the next question opens with its own clock
        # the moment this answer is accepted (settled Q8)
        _send_question(conn, attempt_id, seq + 1, clock)
    conn.commit()
    if tiebreak:
        return _hidden_result(seq, finished=finished)
    return _answer_result(seq, graded, question, finished=finished)


def advance(conn, attempt_id, *, clock) -> AdvanceResult:
    """Send the next question.

    Never finishes an attempt: the final answer or timeout does that, so a
    call after the final question finds the attempt ended. Requires the current (latest sent) question to be resolved first. An
    unanswered question whose deadline has passed is recorded as a timeout
    here; one still inside its deadline cannot be skipped.
    """
    now = clock.now()
    if _is_tiebreak(conn, attempt_id):
        conn.commit()
        raise NotAnsweredError("a tie-break has no Next: questions advance by themselves")
    _sync_connection(conn, attempt_id, now, touch=True)
    row = migrate.fetch_one(
        conn,
        "SELECT seq, answer, deadline_at FROM attempt_answers WHERE attempt_id = %s"
        " ORDER BY seq DESC LIMIT 1",
        (attempt_id,),
    )
    if row is None:
        conn.commit()  # keep the recorded activity, release the attempt lock
        raise NotAnsweredError("no question has been sent")
    if row["answer"] is None:
        if now <= row["deadline_at"]:
            conn.commit()
            raise NotAnsweredError(f"question {row['seq']} is not answered")
        _record_answer(conn, attempt_id, row["seq"], "timeout", now)
        if _promotion_lost(conn, attempt_id, "timeout"):
            # the timeout is the miss that ends a promotion: no next question
            _complete(conn, attempt_id, now)
            conn.commit()
            raise AttemptEndedError("attempt ended: promotion lost on a timeout")
    next_seq = row["seq"] + 1
    _send_question(conn, attempt_id, next_seq, clock)
    conn.commit()
    return AdvanceResult(next_seq=next_seq)


def heartbeat(conn, attempt_id, *, clock) -> None:
    """Record that the page is still connected."""
    _sync_connection(conn, attempt_id, clock.now(), touch=True)
    conn.commit()


def quit_attempt(conn, attempt_id, *, clock) -> str:
    """End the attempt on the player's explicit Quit; return its final outcome.

    The ``quit`` outcome is the penalty marker that #9 reads; no points are
    applied here. A sent question still inside its deadline stays unanswered
    (not deducted); one already past its deadline is a timeout. On an attempt
    that has already ended nothing changes and the stored outcome is returned,
    so a retried Quit gets the same answer and a Quit arriving after the grace
    deadline or after completion does not replace that ending.
    """
    now = clock.now()
    try:
        _sync_connection(conn, attempt_id, now, touch=True)
    except AttemptEndedError:
        row = migrate.fetch_one(
            conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
        )
        return row["final_outcome"]
    _end_early(conn, attempt_id, "quit", now)
    conn.commit()
    return "quit"


def end_attempts_for_season_close(conn, season_id, *, clock) -> int:
    """End the season's unfinished attempts as ``season_close``; return how many.

    A hook for #23, which calls it once the five-minute finishing window is
    over; the engine keeps no season timer. Endings that had already happened
    by the clock are applied first, so an attempt silent past its grace
    deadline is a ``disconnect`` and one whose final question ran out is
    ``completed``. For the rest, a sent question past its deadline is a
    timeout and one still inside it stays unanswered; never-sent questions get
    no row. No Quit marker is recorded. Other seasons and attempts that have
    already ended are untouched.
    """
    now = clock.now()
    expire_stale_attempts(conn, clock=clock)
    rows = migrate.fetch_all(
        conn,
        "SELECT id FROM attempts WHERE season_id = %s"
        " AND state IN ('active', 'grace') FOR UPDATE",
        (season_id,),
    )
    for row in rows:
        _end_early(conn, row["id"], "season_close", now)
    conn.commit()
    return len(rows)


def void_attempts_for_launch(conn, season_id) -> int:
    """Void the season's unfinished attempts as ``launch_reset``; return how many.

    A hook for #23's official-season launch, which ends every unfinished
    Pre-Season attempt without applying its result. Recorded answers are kept
    as history; #9 settles a launch-reset attempt with a zero adjustment.
    Attempts that have already ended, including completed ones awaiting
    settlement, and attempts of other seasons are untouched.
    """
    rows = migrate.fetch_all(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'launch_reset'"
        " WHERE season_id = %s AND state IN ('active', 'grace') RETURNING id",
        (season_id,),
    )
    conn.commit()
    return len(rows)


def void_attempts_for_outage(conn, *, outage_start, outage_end) -> int:
    """Void the attempts a confirmed server-wide outage interrupted.

    Returns how many were voided. Each becomes ``terminal_pending`` with
    ``final_outcome='outage_void'``, which #9 settles with a zero adjustment.
    Affected are attempts still running that started before the outage ended,
    and unsettled disconnects whose silence (last heartbeat to grace deadline)
    overlaps the outage. Completed and quit attempts are the player's own
    ending and stay; settled attempts are never reversed. Recorded answers are
    kept as history.

    The caller is responsible for the outage being confirmed from trusted
    evidence (#13); this function only applies the rule to a given window.

    Tie-break attempts are left out on purpose. They are never settled, so
    ``terminal_pending`` would hold the account's one-unfinished-attempt
    lock for good; and an outage restarts a tie-break's whole round, not one
    attempt (``tiebreaks.void_rounds_for_outage``).
    """
    rows = migrate.fetch_all(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'outage_void'"
        " WHERE mode <> 'tiebreak' AND ("
        "  (state IN ('active', 'grace') AND started_at <= %s)"
        "  OR (state = 'terminal_pending' AND final_outcome = 'disconnect'"
        "      AND COALESCE(last_heartbeat_at, started_at) <= %s"
        "      AND grace_deadline_at >= %s))"
        " RETURNING id",
        (outage_end, outage_end, outage_start),
    )
    conn.commit()
    return len(rows)


def expire_stale_attempts(conn, *, clock, account_id=None) -> None:
    """Apply the connection clock to attempts nobody is calling.

    A silent attempt inside its grace window is marked ``grace`` with its
    deadline; one past the deadline ends as a disconnect. Limited to one
    account when ``account_id`` is given, otherwise every unfinished attempt.
    """
    now = clock.now()
    sql = (
        "SELECT id, state, COALESCE(last_heartbeat_at, started_at) AS heard_at"
        " FROM attempts WHERE state IN ('active', 'grace')"
    )
    params = ()
    if account_id is not None:
        sql += " AND account_id = %s"
        params = (account_id,)
    restarted_rounds = []
    for row in migrate.fetch_all(conn, sql + " FOR UPDATE", params):
        if now >= _loss_at(row["heard_at"]):
            _record_event(conn, row["id"], "loss", _loss_at(row["heard_at"]))
        deadline = _grace_deadline(row["heard_at"])
        # before the final-question rule: a question that ran out while the
        # server was away is not the player's timeout
        if now >= deadline and _cut_off_by_restart(conn, row["heard_at"], deadline):
            if _void_for_restart(conn, row["id"], deadline):
                restarted_rounds.append(row["heard_at"])
            continue
        if _complete_if_final_question_timed_out(conn, row["id"], now):
            continue
        if now >= deadline:
            _finalize_disconnect(conn, row["id"], deadline, now)
        elif row["state"] == "active" and now >= _loss_at(row["heard_at"]):
            migrate.execute(
                conn,
                "UPDATE attempts SET state = 'grace', grace_deadline_at = %s"
                " WHERE id = %s",
                (deadline, row["id"]),
            )
    conn.commit()
    # after the commit, so the rows above stay locked until they are written
    for heard_at in restarted_rounds:
        _restart_tiebreak_rounds(conn, heard_at, now)


def _loss_at(heard_at) -> datetime:
    return heard_at + timedelta(seconds=HEARTBEAT_LOSS_SECONDS)


def _grace_deadline(heard_at) -> datetime:
    return _loss_at(heard_at) + timedelta(seconds=GRACE_SECONDS)


def _sync_connection(conn, attempt_id, now, *, touch) -> None:
    """Check the connection clock before doing anything for an attempt.

    Raises :class:`AttemptEndedError` when the attempt is over, including when
    this very call finds it silent past its grace deadline. With ``touch`` the
    call counts as activity: the attempt is (back to) ``active`` and its
    silence is measured from ``now``. Question deadlines are never moved.

    The attempt row stays locked from here until the caller's commit, so calls
    for one attempt run one at a time: a second call waits, then sees the
    first call's committed result. The caller must commit on every path.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT state, COALESCE(last_heartbeat_at, started_at) AS heard_at"
        " FROM attempts WHERE id = %s FOR UPDATE",
        (attempt_id,),
    )
    if row is None:
        raise EngineError("unknown attempt")
    if row["state"] not in ("active", "grace"):
        conn.commit()  # nothing to do for an ended attempt: release the lock
        raise AttemptEndedError("attempt has ended")
    lost = now >= _loss_at(row["heard_at"])
    if lost:
        _record_event(conn, attempt_id, "loss", _loss_at(row["heard_at"]))
    deadline = _grace_deadline(row["heard_at"])
    if now >= deadline and _cut_off_by_restart(conn, row["heard_at"], deadline):
        # the server restarted during the silence: nobody's disconnect, and
        # not a timeout either, even on the final question
        round_too = _void_for_restart(conn, attempt_id, deadline)
        conn.commit()
        if round_too:
            _restart_tiebreak_rounds(conn, row["heard_at"], now)
        raise AttemptEndedError("attempt ended: the server restarted")
    # checked before grace: the final question's deadline always comes first
    if _complete_if_final_question_timed_out(conn, attempt_id, now):
        conn.commit()
        raise AttemptEndedError("attempt ended: final question timed out")
    if now >= deadline:
        # finalization wins over a request arriving at or after the deadline
        _finalize_disconnect(conn, attempt_id, deadline, now)
        conn.commit()
        raise AttemptEndedError("attempt ended: connection grace expired")
    if touch:
        if lost:
            # a return inside grace; the next silence is a new interruption
            _record_event(conn, attempt_id, "recovery", now)
        migrate.execute(
            conn,
            "UPDATE attempts SET last_heartbeat_at = %s, state = 'active',"
            " grace_deadline_at = NULL WHERE id = %s",
            (now, attempt_id),
        )


def _record_event(conn, attempt_id, kind, occurred_at) -> None:
    """Record a connection event for #25 to read. Write-only for the engine.

    A loss's time is derived from the stored heartbeat, so noticing one
    silence several times writes one row: the unique key discards repeats.
    """
    migrate.execute(
        conn,
        "INSERT INTO attempt_connection_events (attempt_id, kind, occurred_at)"
        " VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (attempt_id, kind, occurred_at),
    )


def _finalize_tiebreak(conn, attempt_id, now) -> None:
    """A tie-break attempt never waits for settlement: it changes no
    seasonal points (settled Decisions 9-10), so there is nothing to
    settle. It goes straight to ``finalized``. Ordinary attempts are left
    untouched by the ``mode`` condition."""
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'finalized', settled_at = %s"
        " WHERE id = %s AND mode = 'tiebreak' AND state = 'terminal_pending'",
        (now, attempt_id),
    )


def _void_for_restart(conn, attempt_id, deadline) -> bool:
    """End an attempt the server's own restart cut off.

    An ordinary or promotion attempt becomes ``outage_void``, which
    settlement applies as a zero adjustment with no flag, exactly as for an
    outage the owner records. Answers already given stay as history and the
    open question is left unanswered: it is nobody's timeout.

    Returns True for a tie-break attempt, which is not ended here: an
    interruption restarts its whole round for everyone (settled Decisions
    9-10), and the caller does that once its own transaction is committed.
    Does not commit.
    """
    if _is_tiebreak(conn, attempt_id):
        return True
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending',"
        " final_outcome = 'outage_void', grace_deadline_at = %s"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (deadline, attempt_id),
    )
    return False


def _restart_tiebreak_rounds(conn, heard_at, now) -> None:
    """Restart the open rounds a restart of this server interrupted: those
    with an attempt running between the last time it was heard and the
    moment this process started. Commits."""
    from backend.ranked import tiebreaks  # tiebreaks is built on this module's callers

    tiebreaks.void_rounds_for_outage(
        conn, outage_start=heard_at, outage_end=_process_started_at, clock=_At(now)
    )


def _finalize_disconnect(conn, attempt_id, deadline, now) -> None:
    _record_event(conn, attempt_id, "expiry", deadline)
    # the sent-but-unanswered question times out; unsent questions get no row
    migrate.execute(
        conn,
        "UPDATE attempt_answers SET answer = 'timeout', accepted_at = %s"
        " WHERE attempt_id = %s AND answer IS NULL",
        (now, attempt_id),
    )
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending',"
        " final_outcome = 'disconnect', grace_deadline_at = %s"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (deadline, attempt_id),
    )
    _finalize_tiebreak(conn, attempt_id, now)


def _end_early(conn, attempt_id, final_outcome, now) -> None:
    """End an unfinished attempt before its last question, keeping the partial
    result: a sent question past its deadline is a timeout, one still inside
    it stays unanswered and is not deducted."""
    migrate.execute(
        conn,
        "UPDATE attempt_answers SET answer = 'timeout', accepted_at = %s"
        " WHERE attempt_id = %s AND answer IS NULL AND deadline_at < %s",
        (now, attempt_id, now),
    )
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = %s"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (final_outcome, attempt_id),
    )
    _finalize_tiebreak(conn, attempt_id, now)


def _hidden_result(seq, *, finished=False) -> AnswerResult:
    """What a tie-break answer reveals before the round closes: that it was
    received, and nothing about whether it was right (settled Q4). Not even
    a timeout is distinguished, since that too says something about the
    player's score."""
    return AnswerResult(seq=seq, correct=None, outcome="submitted", finished=finished)


def _answer_result(seq, answer, question, *, finished=False) -> AnswerResult:
    from backend.ranked import scoring

    difficulty = question.difficulty.lower()
    return AnswerResult(
        seq=seq, correct=answer == "correct", outcome=answer, finished=finished,
        correct_belt=question.correct_belt,
        difficulty=difficulty,
        worth=scoring.answer_points(difficulty, answer),
        explanation_en=question.text.en.explanation,
        explanation_es=question.text.es.explanation,
    )


def _promotion_lost(conn, attempt_id, graded) -> bool:
    """Whether this answer is the miss that ends a promotion attempt.

    Owner decision 2026-11-22 (#268): a promotion stops at its first wrong or
    late answer instead of playing out all fifteen. The outcome stays
    ``completed``, so scoring is unchanged: that one miss deducts its ordinary
    points and nothing else can, because nothing else is asked.
    """
    if graded == "correct":
        return False
    row = migrate.fetch_one(
        conn, "SELECT mode FROM attempts WHERE id = %s", (attempt_id,)
    )
    return row is not None and row["mode"] == ranks.PROMOTION


def _complete(conn, attempt_id, now) -> None:
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'completed'"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (attempt_id,),
    )
    _finalize_tiebreak(conn, attempt_id, now)


def _complete_if_final_question_timed_out(conn, attempt_id, now) -> bool:
    """Complete the attempt when its final question ran out unanswered.

    The final timeout ends the attempt without Next. With no background timer
    this is applied by the first call that arrives after the deadline.
    """
    final_seq = _settings(conn, attempt_id).question_count
    row = migrate.fetch_one(
        conn,
        "SELECT answer, deadline_at FROM attempt_answers"
        " WHERE attempt_id = %s AND seq = %s",
        (attempt_id, final_seq),
    )
    if row is None or row["answer"] is not None or now <= row["deadline_at"]:
        return False
    _record_answer(conn, attempt_id, final_seq, "timeout", now)
    _complete(conn, attempt_id, now)
    return True


def _advance_timed_out_tiebreak(conn, attempt_id, now, clock) -> None:
    """A tie-break question that ran out is a timeout, and the next one
    opens by itself (settled Q8). There is no background timer, so this
    happens on the page's next request -- which also means no next question
    is sent while the page is away, as the record requires. After the fifth
    question the attempt completes; there is no sixth."""
    live = migrate.fetch_one(
        conn,
        "SELECT seq, deadline_at FROM attempt_answers"
        " WHERE attempt_id = %s AND answer IS NULL ORDER BY seq LIMIT 1",
        (attempt_id,),
    )
    if live is None or now <= live["deadline_at"]:
        return
    _record_answer(conn, attempt_id, live["seq"], "timeout", now)
    if live["seq"] >= _settings(conn, attempt_id).question_count:
        _complete(conn, attempt_id, now)
    else:
        _send_question(conn, attempt_id, live["seq"] + 1, clock)


def _record_answer(conn, attempt_id, seq, answer, now) -> None:
    # one-way acceptance: only an unresolved row can be written, exactly once
    migrate.execute(
        conn,
        "UPDATE attempt_answers SET answer = %s, accepted_at = %s"
        " WHERE attempt_id = %s AND seq = %s AND answer IS NULL",
        (answer, now, attempt_id, seq),
    )


def _settings(conn, attempt_id) -> modes.ModeSettings:
    """The quiz shape (question count and seconds) of this attempt's mode."""
    row = migrate.fetch_one(
        conn, "SELECT mode, tiebreak_round FROM attempts WHERE id = %s", (attempt_id,)
    )
    return modes.settings_for(row["mode"], row["tiebreak_round"])


def is_tiebreak_attempt(conn, attempt_id) -> bool:
    """Whether this attempt is a prize tie-break, for callers outside the
    engine that must treat one differently (no settlement, hidden result)."""
    return _is_tiebreak(conn, attempt_id)


def _is_tiebreak(conn, attempt_id) -> bool:
    row = migrate.fetch_one(
        conn, "SELECT mode FROM attempts WHERE id = %s", (attempt_id,)
    )
    return row is not None and row["mode"] == "tiebreak"


def _open_season(conn, now) -> str:
    # admission follows the season clock: a season past its scheduled end
    # admits nobody, without anyone having to close it
    # share-locked until this start commits, so a season launch waits for it
    season_id = seasons.admitting_season(conn, now, lock=True)
    if season_id is None:
        raise NoOpenSeasonError("no open season to admit a ranked attempt")
    return season_id


def _send_question(conn, attempt_id, seq, clock) -> None:
    version = migrate.fetch_one(
        conn,
        "SELECT aq.question_version_id AS vid FROM assignment_questions aq"
        " JOIN attempts a ON a.assignment_id = aq.assignment_id"
        " WHERE a.id = %s AND aq.seq = %s",
        (attempt_id, seq),
    )
    now = clock.now()
    seconds = _settings(conn, attempt_id).question_seconds
    deadline = now + timedelta(seconds=seconds)
    migrate.execute(
        conn,
        "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
        " first_sent_at, deadline_at, outcome)"
        " VALUES (%s, %s, %s, %s, %s, 'unsent')",
        (attempt_id, seq, version["vid"], now, deadline),
    )


def _options_for_assignment(conn, attempt_id, seq, question, bank):
    """The four belts this ordinary or promotion question offers (migration
    0035). A row written before options existed gets them drawn and stored
    now, once, under a lock -- the same lazy backfill as a tie-break's
    shared options, but personal to this one attempt."""
    row = migrate.fetch_one(
        conn,
        "SELECT aq.assignment_id, aq.options FROM assignment_questions aq"
        " JOIN attempts a ON a.assignment_id = aq.assignment_id"
        " WHERE a.id = %s AND aq.seq = %s FOR UPDATE OF aq",
        (attempt_id, seq),
    )
    if row is None or row["options"] is not None:
        return None if row is None else list(row["options"])
    options = belt_options.draw_options(question.correct_belt, belt_options.all_belts(bank))
    migrate.execute(
        conn,
        "UPDATE assignment_questions SET options = %s"
        " WHERE assignment_id = %s AND seq = %s",
        (options, row["assignment_id"], seq),
    )
    return options


def _question_for_version(conn, bank, version_id):
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
    raise EngineError("stored question version is not in the current bank")
