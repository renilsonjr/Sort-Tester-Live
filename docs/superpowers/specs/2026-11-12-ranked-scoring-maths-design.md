# Ranked scoring — points maths (Issue #9, slice 1)

First slice of #9. It turns the answers of one ended attempt into a result:
raw score, applied adjustment, points and badge before and after. It is pure
arithmetic with no database and no HTTP. Writing the result exactly once
(settlement, balance, history, `terminal_pending -> finalized`) is the next
slice.

Rules come from the decision record (Baseline, Decisions 1–5) and the
owner-confirmed worked examples.

## Owner decisions (2026-11-12)

- **Disconnects are scored at once**, like any other ending. This replaces the
  security/operations design's proposal to hold a disconnect's settlement
  until outage classification commits. Consequence: because a committed
  balance is never reversed, `void_attempts_for_outage` can no longer
  reclassify a disconnect once it is settled; it still voids attempts that are
  running when an outage is confirmed.
- **First slice is the maths only.**

## Rules

**Per question** (ordinary value):

| difficulty | correct | wrong or timeout |
|---|---|---|
| easy | +10 | −15 |
| medium | +20 | −10 |
| hard | +30 | −5 |

A sent question left unanswered and a question never sent score 0.

**Raw score** is the sum of ordinary values over the attempt's answers. A
complete attempt ranges from −150 to +300. It is recorded for history in every
mode and is not a second balance.

**Normal attempt.** Result = raw score, minus 10 when the outcome is `quit`.
Add it to the points before, then apply the cap of the badge held before the
attempt, once; overflow is discarded. Challenger is uncapped. Totals may be
negative; a negative total is Iron.

**Promotion attempt.** Correct answers add 0; wrong answers and timeouts
deduct their ordinary amount; `quit` deducts 10 more. A `completed` attempt in
which every answer is correct sets the points to the cap of the badge held
before, plus 1, in place of any sum.

**Outcomes.**

| outcome | effect |
|---|---|
| `completed` | full result |
| `quit` | partial result and −10 |
| `disconnect`, `season_close` | partial result, no penalty |
| `outage_void`, `launch_reset` | zero adjustment |

**Adjustment** is points after minus points before. Badges before and after
come from `ranks.badge_for`, so a loss that crosses below a bracket demotes.

## Code shape

`backend/ranked/scoring.py`:

- `answer_points(difficulty, result) -> int`
- `raw_score(answers) -> int`
- `settle(points_before, mode, final_outcome, answers) -> Settlement`, where
  `answers` is a sequence of `(difficulty, result)` with `result` one of
  `'correct'`, `'wrong'`, `'timeout'` or `None`, and `Settlement` carries
  `raw_score`, `adjustment`, `points_before`, `points_after`, `badge_before`
  and `badge_after`.

`ranks.cap_for(badge)` returns a badge's cap, or `None` for Challenger.

Unknown difficulties, results, modes and outcomes raise `ValueError`.

## Out of scope

Persisting settlements and balances, idempotency under concurrency, when
settlement runs, per-answer point feedback over HTTP, tie-break scoring (#24).

## Testing (unit tests, no database)

- Per-question values for every difficulty and result.
- Raw score bounds −150 and +300.
- Worked examples 1–6, 8–11 and 13 with the document's numbers.
- Cap edges: landing exactly on a cap, one point under, far over; Challenger
  uncapped; negative totals; demotion across each bracket.
- Promotion: perfect, one mistake, early ending with no mistake, Quit.
- Void outcomes leave points unchanged whatever the answers.
- Invalid inputs raise.
