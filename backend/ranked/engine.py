"""Server-authoritative ranked attempt engine — core happy path (issue #8).

This slice runs a normal-mode attempt from start to finish on the server: it
assigns 15 questions, serves them one at a time on server-owned ten-second
deadlines, accepts a single locked answer each, runs forward-only, and ends the
attempt in ``terminal_pending``. It records per-answer results only; computing
the score, caps, and balance is #9, which reads the finalized answers and
transitions ``terminal_pending -> finalized``.

Every function takes an explicit DB connection and (where time matters) a clock,
so callers own transactions and tests control time. The engine never reads the
wall clock directly.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from backend.db import migrate
from backend.ranked.versions import materialize_question_version
from backend.ranked_bank.identity import question_content_digest
from backend.ranked_bank.selection import select_assignment

QUESTION_COUNT = 15
QUESTION_SECONDS = 10


class EngineError(Exception):
    """Base class for ranked engine errors."""


class NoOpenSeasonError(EngineError):
    """No season is open to admit a new attempt."""


class ActiveAttemptExistsError(EngineError):
    """The account already has an unfinished attempt."""


class AnswerRejectedError(EngineError):
    """The submitted answer is not acceptable (wrong question, late, or done)."""


class NotAnsweredError(EngineError):
    """Advance was requested before the current question was answered."""


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


@dataclass(frozen=True)
class AdvanceResult:
    finished: bool
    next_seq: int | None


def start_attempt(conn, account_id, *, clock, bank) -> str:
    """Assign 15 questions, open an ``active`` attempt, and send question 1.

    Raises :class:`NoOpenSeasonError` when no season is open and
    :class:`ActiveAttemptExistsError` when the account already has an
    unfinished attempt. On the latter the whole transaction is rolled back.
    """
    season_id = _open_season(conn)
    snapshot = select_assignment(bank)
    assignment = migrate.fetch_one(
        conn,
        "INSERT INTO assignments (account_id, mode, season_id)"
        " VALUES (%s, 'normal', %s) RETURNING id",
        (account_id, season_id),
    )
    assignment_id = assignment["id"]
    try:
        attempt = migrate.fetch_one(
            conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, state, season_id)"
            " VALUES (%s, %s, 'normal', 'active', %s) RETURNING id",
            (account_id, assignment_id, season_id),
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


def current_question(conn, attempt_id, *, bank) -> QuestionView | None:
    """Return the single live question (the one awaiting an answer), or None."""
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
    """Grade and lock one answer. Idempotent: a second submit changes nothing."""
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
    now = clock.now()
    if now > row["deadline_at"]:
        # too late: the question timed out and the submitted choice is discarded
        graded = "timeout"
    else:
        question = _question_for_version(conn, bank, row["vid"])
        graded = "correct" if choice == question.correct_belt else "wrong"
    _record_answer(conn, attempt_id, seq, graded, now)
    conn.commit()
    return _answer_result(seq, graded)


def advance(conn, attempt_id, *, clock) -> AdvanceResult:
    """Send the next question, or finish the attempt after the 15th.

    Requires the current (latest sent) question to be resolved first. An
    unanswered question whose deadline has passed is recorded as a timeout
    here; one still inside its deadline cannot be skipped.
    """
    row = migrate.fetch_one(
        conn,
        "SELECT seq, answer, deadline_at FROM attempt_answers WHERE attempt_id = %s"
        " ORDER BY seq DESC LIMIT 1",
        (attempt_id,),
    )
    if row is None:
        raise NotAnsweredError("no question has been sent")
    if row["answer"] is None:
        now = clock.now()
        if now <= row["deadline_at"]:
            raise NotAnsweredError(f"question {row['seq']} is not answered")
        _record_answer(conn, attempt_id, row["seq"], "timeout", now)
    current_seq = row["seq"]
    if current_seq >= QUESTION_COUNT:
        migrate.execute(
            conn,
            "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'completed'"
            " WHERE id = %s AND state = 'active'",
            (attempt_id,),
        )
        conn.commit()
        return AdvanceResult(finished=True, next_seq=None)
    next_seq = current_seq + 1
    _send_question(conn, attempt_id, next_seq, clock)
    conn.commit()
    return AdvanceResult(finished=False, next_seq=next_seq)


def _answer_result(seq, answer) -> AnswerResult:
    return AnswerResult(seq=seq, correct=answer == "correct", outcome=answer)


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
