# Ranked settlement — apply a result exactly once (Issue #9, slice 2)

Second slice of #9. It builds on the points maths
(`2026-11-12-ranked-scoring-maths-design.md`) and persists one ended attempt's
result: the settlement row, the account balance, the balance history row and
the attempt's move from `terminal_pending` to `finalized`, atomically and at
most once.

## Design

`backend/ranked/settlement.py`.

`settle_attempt(conn, attempt_id, *, clock) -> scoring.Settlement` runs one
transaction:

1. Lock the attempt row (`SELECT ... FOR UPDATE`).
2. If the attempt is `finalized`, change nothing and return the stored result.
   If it is `active` or `grace`, raise `AttemptNotEndedError`.
3. Ensure the account has a `balances` row (a new account starts at 0) and
   lock it.
4. Read the attempt's answers with each question version's difficulty and
   compute the result with `scoring.settle`.
5. Insert the `settlements` row and the `balance_history` row, update
   `balances.current_points`, and set the attempt `finalized` with
   `settled_at`.
6. Commit.

Any failure rolls the whole transaction back: there is never a balance change
without its history, or a history row without a finalized attempt.

**Exactly once** rests on three layers: the attempt row lock serialises
concurrent settlements; the state check makes the second one a no-op that
returns the stored result; and `settlements.attempt_id` is the primary key
(with `balance_history.settlement_id` unique), so a second row cannot exist.

`settle_pending(conn, *, clock) -> int` settles every `terminal_pending`
attempt and returns how many it settled. It is the sweep a scheduler runs.

Times (`settled_at`, `recorded_at`, `updated_at`) come from the injected
clock.

## Consequences

- A finalized attempt no longer holds the one-unfinished-attempt lock, so the
  account can start again.
- A finalized attempt is never touched again: `void_attempts_for_outage`
  already ignores it.

## Out of scope

Running settlement automatically when an attempt ends and returning the
result to the player (next slice, per the owner's score-at-once decision);
the launch reset of balances (#23); tie-break results (#24); admin
corrections (not authorised).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Each outcome persists the numbers `scoring.settle` gives: completed, quit,
  disconnect, season close, outage void, launch reset.
- Absolute cases: perfect from 0 is +300; 950 perfect is capped to 1,000 with
  adjustment +50; Quit with no answers is −10; void outcomes leave the balance
  unchanged.
- Promotion: perfect at 1,000 persists 1,001 and Bronze; one mistake deducts.
- A new account gets its balance row.
- Settling twice writes one settlement and one history row and returns the
  same result.
- A running attempt is refused and nothing is written.
- After settlement a new attempt can start.
- Two concurrent settlements of one attempt produce one settlement.
- `settle_pending` settles every pending attempt and ignores the rest.
