"""Ranked settlement: apply one ended attempt's result exactly once (issue #9).

The attempt engine ends an attempt in ``terminal_pending`` and records only
its answers and final outcome. Settlement turns that into points: it computes
the result with :mod:`backend.ranked.scoring` and writes the settlement row,
the account balance, the balance history row and the attempt's move to
``finalized`` in one transaction.

Exactly once rests on three layers: the attempt row lock serialises concurrent
settlements, the state check makes a repeat a no-op that returns the stored
result, and ``settlements.attempt_id`` is the primary key.
"""
from backend.db import migrate
from backend.ranked import scoring


class SettlementError(Exception):
    """Base class for settlement errors."""


class AttemptNotEndedError(SettlementError):
    """The attempt is still running and has no result to settle."""


def settle_attempt(conn, attempt_id, *, clock) -> scoring.Settlement:
    """Apply the attempt's result to its account once; return the result.

    Settling an already ``finalized`` attempt changes nothing and returns the
    stored result. An attempt that has not ended raises
    :class:`AttemptNotEndedError`. Everything is written in one transaction,
    so a failure leaves no partial settlement behind.
    """
    result, _ = _settle(conn, attempt_id, clock)
    return result


def settle_pending(conn, *, clock) -> int:
    """Settle every attempt waiting in ``terminal_pending``; return how many.

    The sweep a scheduler runs. Each attempt is settled in its own
    transaction, so one failure does not undo the others. An attempt another
    caller settles first is not counted: its points were applied there.
    """
    rows = migrate.fetch_all(
        conn, "SELECT id FROM attempts WHERE state = 'terminal_pending' ORDER BY started_at"
    )
    conn.commit()
    settled = 0
    for row in rows:
        _, applied = _settle(conn, row["id"], clock)
        if applied:
            settled += 1
    return settled


def _settle(conn, attempt_id, clock) -> tuple[scoring.Settlement, bool]:
    """Settle one attempt. Returns the result and whether this call applied it."""
    attempt = migrate.fetch_one(
        conn,
        "SELECT account_id, season_id, mode, state, final_outcome"
        " FROM attempts WHERE id = %s FOR UPDATE",
        (attempt_id,),
    )
    if attempt is None:
        raise SettlementError("unknown attempt")
    if attempt["state"] == "finalized":
        stored = _stored_result(conn, attempt_id)
        conn.commit()  # nothing written: release the attempt lock
        return stored, False
    if attempt["state"] != "terminal_pending":
        conn.commit()
        raise AttemptNotEndedError("attempt has not ended")

    now = clock.now()
    account_id = attempt["account_id"]
    # a new account has no balance row yet; it starts at zero points
    migrate.execute(
        conn,
        "INSERT INTO balances (account_id, current_points, updated_at)"
        " VALUES (%s, 0, %s) ON CONFLICT (account_id) DO NOTHING",
        (account_id, now),
    )
    balance = migrate.fetch_one(
        conn,
        "SELECT current_points FROM balances WHERE account_id = %s FOR UPDATE",
        (account_id,),
    )
    answers = migrate.fetch_all(
        conn,
        "SELECT qv.difficulty, aa.answer FROM attempt_answers aa"
        " JOIN question_versions qv ON qv.id = aa.question_version_id"
        " WHERE aa.attempt_id = %s ORDER BY aa.seq",
        (attempt_id,),
    )
    result = scoring.settle(
        balance["current_points"],
        attempt["mode"],
        attempt["final_outcome"],
        [(row["difficulty"], row["answer"]) for row in answers],
    )

    migrate.execute(
        conn,
        "INSERT INTO settlements (attempt_id, season_id, raw_score, adjustment,"
        " final_outcome, settled_at) VALUES (%s, %s, %s, %s, %s, %s)",
        (attempt_id, attempt["season_id"], result.raw_score, result.adjustment,
         attempt["final_outcome"], now),
    )
    migrate.execute(
        conn,
        "INSERT INTO balance_history (account_id, settlement_id, raw_score,"
        " adjustment, points_before, points_after, badge_before, badge_after,"
        " recorded_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
        (account_id, attempt_id, result.raw_score, result.adjustment,
         result.points_before, result.points_after, result.badge_before,
         result.badge_after, now),
    )
    migrate.execute(
        conn,
        "UPDATE balances SET current_points = %s, updated_at = %s"
        " WHERE account_id = %s",
        (result.points_after, now, account_id),
    )
    migrate.execute(
        conn,
        "UPDATE attempts SET state = 'finalized', settled_at = %s WHERE id = %s",
        (now, attempt_id),
    )
    conn.commit()
    return result, True


def _stored_result(conn, attempt_id) -> scoring.Settlement:
    row = migrate.fetch_one(
        conn,
        "SELECT raw_score, adjustment, points_before, points_after,"
        " badge_before, badge_after FROM balance_history WHERE settlement_id = %s",
        (attempt_id,),
    )
    if row is None:
        raise SettlementError("finalized attempt has no recorded settlement")
    return scoring.Settlement(
        raw_score=row["raw_score"],
        adjustment=row["adjustment"],
        points_before=row["points_before"],
        points_after=row["points_after"],
        badge_before=row["badge_before"],
        badge_after=row["badge_after"],
    )
