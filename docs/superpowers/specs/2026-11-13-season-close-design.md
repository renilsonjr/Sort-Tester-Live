# Seasons — close, finishing window and freeze (Issue #23, slice 3)

Third slice of #23. It builds on the season clock and the launch. It
implements the end of a season from the decision record (Decision 13): stop
new Ranked admission at closing; attempts already started get five extra
minutes; at that deadline end unfinished attempts and apply partial results
without a Quit penalty, deductions for never-sent questions or flags; freeze
points after settlement.

Admission by the clock is already in place (slice 1). This slice adds what
happens when the finishing window is over.

## Design

`backend/ranked/season_close.py`.

`finish_season(conn, season_id, *, clock) -> bool` returns True when this call
froze the season.

1. Lock the season row. If it is frozen, or has not ended, or its finishing
   window (`seasons.FINISHING_WINDOW_SECONDS` after its end) is not over yet,
   do nothing and return False.
2. Record the end in `closed_at` if it is not set (the scheduled end).
   Committed.
3. `engine.end_attempts_for_season_close`: endings the clock had already
   decided are applied first (an attempt silent past grace is a `disconnect`,
   a timed-out final question is `completed`); the rest end as
   `season_close`, with a sent question past its deadline a timeout and one
   still inside it left unanswered.
4. `settlement.settle_pending`: every ended attempt gets its result.
5. Final transaction: re-lock the season; if no attempt of the season remains
   unsettled, set `frozen_at`.

`finish_due_seasons(conn, *, clock) -> int` finishes every unfrozen season
whose window is over and returns how many it froze.

**Exactly once.** A frozen season is never finished again. Steps 2–4 are
idempotent and the freeze is written only after checking that nothing of the
season is unsettled, so an interrupted finish completes when run again. Once
frozen, settlement of any attempt of that season applies zero (slice 2).

## Trigger

There is no background timer. Every Ranked HTTP request first calls
`finish_due_seasons`; when nothing is due it is a single read. A request that
arrives after the window therefore finds its attempt ended and settled (410).
If no request arrives, the season stays `closed` until the first one; every
time involved is stored, so the result does not depend on when it runs. A
scheduler that runs it on time comes with hosting (#13).

## Out of scope

Prize standings, provisional versus final prizes and tie-breaks (#12/#24);
the HTTP lifecycle status and the private history read (slice 4); the
scheduler (#13).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Before the end and during the window nothing happens; a running attempt can
  still be answered inside the window.
- At the end of the window a running attempt ends `season_close` with its
  partial result, a live question inside its deadline is not deducted, the
  season is frozen and `closed_at` is the scheduled end.
- An attempt silent since before the end ends as a `disconnect`.
- An attempt that ended before the window closed gets its real result.
- Finishing twice changes nothing; an interrupted finish completes.
- After the freeze no attempt can start.
- `finish_due_seasons` freezes what is due and nothing else.
- Race: finish waits for an answer in progress.
- HTTP: a request after the window gets 410 with the attempt settled; `entry`
  after the window freezes the season.
