# Ranked attempt engine — promotion entry (Issue #8, slice 6)

Sixth slice of the ranked attempt engine. It builds on slice 5
(`2026-11-12-ranked-engine-final-question-design.md`) and implements the
promotion gate from the decision record (Decision 4, settled Q7): at a capped
badge's point cap, an explicit Start promotion is the only Ranked entry; below
the cap ordinary Ranked play is the only entry; Challenger is uncapped.

The hooks for #23/#24/#25 named in the same part of #8 are a separate slice.

## Rules

Caps: Iron 1,000, Bronze 2,000, Silver 3,000, Gold 4,000. Challenger (4,001
upward) has none.

- The gate is applied when a new attempt starts, from current server state:
  `balances.current_points` for the account, or 0 when the account has no
  balance row.
- Points exactly at a cap → only a `promotion` attempt may start.
- Any other total, including negative totals and Challenger → only a `normal`
  attempt may start.
- The caller states the mode. The server never converts one mode into the
  other and never starts an attempt on its own.
- A promotion attempt runs exactly like a normal one in the engine: the same
  five-per-difficulty assignment, deadlines, Next pacing, final-question
  completion, heartbeat, grace, Quit, outage void and page capability. Only
  `assignments.mode` and `attempts.mode` differ. Promotion scoring, cap+1 and
  badge changes are #9.

The gate cannot read a stale total: an attempt that has ended but is not yet
settled still holds the one-unfinished-attempt lock, so any start that passes
the lock sees a balance with every earlier attempt applied.

## Code shape

- `backend/ranked/ranks.py`: `CAPS`, `badge_for(points)` and
  `entry_mode(points)` (`'normal'` or `'promotion'`). Pure functions, no
  database; #9 reuses them.
- `engine.start_attempt` gains `mode='normal'`. It raises
  `PromotionRequiredError` for a normal start at a cap,
  `PromotionNotAvailableError` for a promotion start off a cap, and
  `EngineError` for any other mode (tie-break attempts are #24). The gate runs
  after stale attempts are expired and before anything is written.
- `engine.entry_status(conn, account_id)` returns the account's points, badge
  and allowed mode without writing anything.

## HTTP

- `GET /api/ranked/entry` → `{"points", "badge", "mode"}` for the signed-in
  account. Read-only: it starts nothing.
- `POST /api/ranked/attempts` accepts an optional body `{"mode": "normal" |
  "promotion"}`; no body means `normal`. The response gains `mode`. A gate
  refusal is 409 with the detail `Promotion required` or
  `Promotion not available`.

## Out of scope

Promotion scoring and badge changes (#9), the Start promotion screen and its
15/15 explanation (#17), tie-break attempts (#24), phase/round/connection
hooks (next slice).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- `badge_for` and `entry_mode` at, just below and just above every cap, at 0,
  at a negative total and in Challenger.
- No balance row → normal allowed, promotion refused.
- At each cap → promotion allowed and stored as `promotion` on the attempt and
  its assignment; normal refused; nothing is written on refusal.
- One point below a cap and one above → normal only.
- A promotion attempt plays through to `terminal_pending`/`completed`.
- An unknown mode is refused.
- HTTP: `entry` reports points, badge and mode and needs a session; start with
  and without a body; both refusals are 409.
