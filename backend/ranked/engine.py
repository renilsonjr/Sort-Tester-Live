"""Server-authoritative ranked attempt engine (issue #8).

Runs a normal-mode attempt from start to finish on the server: it assigns 15
questions, serves them one at a time on server-owned ten-second deadlines,
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
from backend.ranked import ranks
from backend.ranked.capability import hash_token
from backend.ranked.versions import materialize_question_version
from backend.ranked_bank.identity import question_content_digest
from backend.ranked_bank.selection import select_assignment

QUESTION_COUNT = 15
QUESTION_SECONDS = 10
HEARTBEAT_LOSS_SECONDS = 3
GRACE_SECONDS = 15


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


@dataclass(frozen=True)
class AnswerResult:
    seq: int
    correct: bool
    outcome: str  # 'correct', 'wrong' or 'timeout'
    finished: bool  # True when this answer was the final one and ended the attempt


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
    """Assign 15 questions, open an ``active`` attempt, and send question 1.

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
    season_id = _open_season(conn)
    snapshot = select_assignment(bank)
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
    for seq, question in enumerate(snapshot.questions, start=1):
        version_id = materialize_question_version(conn, question)
        migrate.execute(
            conn,
            "INSERT INTO assignment_questions (assignment_id, seq, question_version_id)"
            " VALUES (%s, %s, %s)",
            (assignment_id, seq, version_id),
        )
    _send_question(conn, attempt_id, 1, clock)
    conn.commit()
    return attempt_id


def current_question(conn, attempt_id, *, clock, bank) -> QuestionView | None:
    """Return the single live question (the one awaiting an answer), or None.

    Reading does not count as activity: it checks the connection clock but
    does not reset it.
    """
    _sync_connection(conn, attempt_id, clock.now(), touch=False)
    row = migrate.fetch_one(
        conn,
        "SELECT seq, question_version_id AS vid, deadline_at FROM attempt_answers"
        " WHERE attempt_id = %s AND answer IS NULL ORDER BY seq LIMIT 1",
        (attempt_id,),
    )
    if row is None:
        return None
    question = _question_for_version(conn, bank, row["vid"])
    return QuestionView(
        seq=row["seq"],
        deadline_at=row["deadline_at"],
        prompt_en=question.text.en.prompt,
        prompt_es=question.text.es.prompt,
    )


def submit_answer(conn, attempt_id, seq, choice, *, clock, bank) -> AnswerResult:
    """Grade and lock one answer. Idempotent: a second submit changes nothing.

    The answer to the final question also completes the attempt, in the same
    transaction: there is no Next after it.
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
        raise AnswerRejectedError(f"question {seq} has not been sent")
    if row["answer"] is not None:
        # already resolved: report the stored result, write nothing
        return _answer_result(seq, row["answer"])
    if now > row["deadline_at"]:
        # too late: the question timed out and the submitted choice is discarded
        graded = "timeout"
    else:
        question = _question_for_version(conn, bank, row["vid"])
        graded = "correct" if choice == question.correct_belt else "wrong"
    _record_answer(conn, attempt_id, seq, graded, now)
    finished = seq == QUESTION_COUNT
    if finished:
        _complete(conn, attempt_id)
    conn.commit()
    return _answer_result(seq, graded, finished=finished)


def advance(conn, attempt_id, *, clock) -> AdvanceResult:
    """Send the next question.

    Never finishes an attempt: the final answer or timeout does that, so a
    call after question 15 finds the attempt ended. Requires the current (latest sent) question to be resolved first. An
    unanswered question whose deadline has passed is recorded as a timeout
    here; one still inside its deadline cannot be skipped.
    """
    now = clock.now()
    _sync_connection(conn, attempt_id, now, touch=True)
    row = migrate.fetch_one(
        conn,
        "SELECT seq, answer, deadline_at FROM attempt_answers WHERE attempt_id = %s"
        " ORDER BY seq DESC LIMIT 1",
        (attempt_id,),
    )
    if row is None:
        raise NotAnsweredError("no question has been sent")
    if row["answer"] is None:
        if now <= row["deadline_at"]:
            raise NotAnsweredError(f"question {row['seq']} is not answered")
        _record_answer(conn, attempt_id, row["seq"], "timeout", now)
    next_seq = row["seq"] + 1
    _send_question(conn, attempt_id, next_seq, clock)
    conn.commit()
    return AdvanceResult(next_seq=next_seq)


def heartbeat(conn, attempt_id, *, clock) -> None:
    """Record that the page is still connected."""
    _sync_connection(conn, attempt_id, clock.now(), touch=True)


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
    migrate.execute(
        conn,
        "UPDATE attempt_answers SET answer = 'timeout', accepted_at = %s"
        " WHERE attempt_id = %s AND answer IS NULL AND deadline_at < %s",
        (now, attempt_id, now),
    )
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'quit'"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (attempt_id,),
    )
    conn.commit()
    return "quit"


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
    """
    rows = migrate.fetch_all(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'outage_void'"
        " WHERE (state IN ('active', 'grace') AND started_at <= %s)"
        " OR (state = 'terminal_pending' AND final_outcome = 'disconnect'"
        "     AND COALESCE(last_heartbeat_at, started_at) <= %s"
        "     AND grace_deadline_at >= %s)"
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
    for row in migrate.fetch_all(conn, sql + " FOR UPDATE", params):
        if _complete_if_final_question_timed_out(conn, row["id"], now):
            continue
        deadline = _grace_deadline(row["heard_at"])
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
        raise AttemptEndedError("attempt has ended")
    # checked before grace: the final question's deadline always comes first
    if _complete_if_final_question_timed_out(conn, attempt_id, now):
        conn.commit()
        raise AttemptEndedError("attempt ended: final question timed out")
    deadline = _grace_deadline(row["heard_at"])
    if now >= deadline:
        # finalization wins over a request arriving at or after the deadline
        _finalize_disconnect(conn, attempt_id, deadline, now)
        conn.commit()
        raise AttemptEndedError("attempt ended: connection grace expired")
    if touch:
        migrate.execute(
            conn,
            "UPDATE attempts SET last_heartbeat_at = %s, state = 'active',"
            " grace_deadline_at = NULL WHERE id = %s",
            (now, attempt_id),
        )
        conn.commit()


def _finalize_disconnect(conn, attempt_id, deadline, now) -> None:
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


def _answer_result(seq, answer, *, finished=False) -> AnswerResult:
    return AnswerResult(
        seq=seq, correct=answer == "correct", outcome=answer, finished=finished
    )


def _complete(conn, attempt_id) -> None:
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'completed'"
        " WHERE id = %s AND state IN ('active', 'grace')",
        (attempt_id,),
    )


def _complete_if_final_question_timed_out(conn, attempt_id, now) -> bool:
    """Complete the attempt when its final question ran out unanswered.

    The final timeout ends the attempt without Next. With no background timer
    this is applied by the first call that arrives after the deadline.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT answer, deadline_at FROM attempt_answers"
        " WHERE attempt_id = %s AND seq = %s",
        (attempt_id, QUESTION_COUNT),
    )
    if row is None or row["answer"] is not None or now <= row["deadline_at"]:
        return False
    _record_answer(conn, attempt_id, QUESTION_COUNT, "timeout", now)
    _complete(conn, attempt_id)
    return True


def _record_answer(conn, attempt_id, seq, answer, now) -> None:
    # one-way acceptance: only an unresolved row can be written, exactly once
    migrate.execute(
        conn,
        "UPDATE attempt_answers SET answer = %s, accepted_at = %s"
        " WHERE attempt_id = %s AND seq = %s AND answer IS NULL",
        (answer, now, attempt_id, seq),
    )


def _open_season(conn) -> str:
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM seasons WHERE closed_at IS NULL ORDER BY opened_at DESC LIMIT 1",
    )
    if row is None:
        raise NoOpenSeasonError("no open season to admit a ranked attempt")
    return row["id"]


def _send_question(conn, attempt_id, seq, clock) -> None:
    version = migrate.fetch_one(
        conn,
        "SELECT aq.question_version_id AS vid FROM assignment_questions aq"
        " JOIN attempts a ON a.assignment_id = aq.assignment_id"
        " WHERE a.id = %s AND aq.seq = %s",
        (attempt_id, seq),
    )
    now = clock.now()
    deadline = now + timedelta(seconds=QUESTION_SECONDS)
    migrate.execute(
        conn,
        "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
        " first_sent_at, deadline_at, outcome)"
        " VALUES (%s, %s, %s, %s, %s, 'unsent')",
        (attempt_id, seq, version["vid"], now, deadline),
    )


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
