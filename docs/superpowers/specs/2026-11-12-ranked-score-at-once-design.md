# Ranked settlement — score at once (Issue #9, slice 3)

Third slice of #9. It builds on settlement
(`2026-11-12-ranked-settlement-design.md`). Until now nothing ran settlement,
so an ended attempt's points were never applied in the running backend. This
slice settles an attempt as soon as it ends and returns the result to the
player.

Owner decision (2026-11-12): every ending, including a disconnect, is scored
at once.

## Where it runs

In the HTTP layer, immediately after the engine call that ended the attempt.
The engine keeps its boundary: it ends an attempt in `terminal_pending` and
knows nothing of points. `backend/routers/ranked.py` calls
`settlement.settle_attempt` right after.

Ending and settlement are two transactions. If the process stops between
them, the attempt stays `terminal_pending`; `settle_attempt` is idempotent, so
the next request that touches the attempt, the next start by that account, or
the `settle_pending` sweep applies the result. Points are never lost and never
applied twice.

## Behaviour

- **Final answer.** When `submit_answer` reports `finished`, the attempt is
  settled and the response gains `result`.
- **Quit.** The attempt is settled and the response gains `result`. A repeated
  Quit returns the same outcome and the same stored result.
- **A request that finds the attempt ended** (final-question timeout, grace
  expiry, or any earlier ending): the attempt is settled before the 410
  response is sent.
- **Start.** Before admitting, the account's stale attempt is expired and the
  account's pending attempts are settled, so an abandoned attempt no longer
  blocks a new one. `settle_pending` gains an optional `account_id`.
- **`GET /api/ranked/attempts/{attempt_id}/result`** returns the result of an
  ended attempt, settling it first if it is still pending. It requires the
  session and ownership but not the page capability: the attempt is over and
  this reads history. A running attempt answers 409.

`result` is `{final_outcome, raw_score, adjustment, points_before,
points_after, badge_before, badge_after}`.

## Atomicity test

A failure injected after the balance update and before the attempt is
finalized must leave no settlement row, no history row, the balance unchanged
and the attempt still `terminal_pending`; a later settlement then succeeds.

## Out of scope

Per-answer point feedback (#17), the scheduler that runs the sweeps (hosting,
#13), the launch reset of balances (#23), tie-break results (#24).

## Testing (TDD, live scratch PostgreSQL)

- Rollback on an injected failure, then a successful retry.
- HTTP: the fifteenth answer returns the result and `entry` shows the new
  points; Quit returns the result (twice, identical) and −10 is applied; an
  attempt found ended by grace is settled when the 410 is returned; after an
  abandoned attempt a new start succeeds and the old one is settled; the
  result endpoint returns a finished attempt's result, answers 409 for a
  running one, 404 for another account and 401 without a session.
