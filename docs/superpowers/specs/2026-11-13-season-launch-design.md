# Seasons — official launch, exactly once (Issue #23, slice 2)

Second slice of #23. It builds on the season clock
(`2026-11-12-season-clock-design.md`) and implements the owner's manual
official-season launch from the decision record (Decision 12): void every
unfinished Pre-Season attempt without applying its result, keep Pre-Season
records, reset every balance to 0, and open the official season, once.

## Owner decisions

- Launch requires the owner account and a typed confirmation: the new
  season's name and the exact word `LAUNCH` (2026-11-12).
- The official season ends December 31, 2026 at 23:59:00 America/New_York
  (2026-11-13: "11:59 p.m." is stored as 23:59:00, so the last attempt can
  start at 23:58:59 and the finishing window runs to 00:04:00).
- The second sign-in factor the security/operations design asks for owner
  actions is #11/#13 and is not provided here.

## Design

`backend/ranked/launch.py` (a separate module: it uses the engine, settlement
and the season clock, and the engine already imports the season clock).

`launch_official_season(conn, *, label, clock, closes_at=DEFAULT_OFFICIAL_END)`
returns the new season's id.

1. **Validate.** `label` must not be blank and `closes_at` must be after now
   (`InvalidLaunchError`).
2. **Lock the seasons and decide.** If an official season exists, raise
   `AlreadyLaunchedError`. If there is no unfrozen Pre-Season, raise
   `NoPreSeasonError`.
3. **Close the Pre-Season** (`closed_at`, kept if already set). Committed:
   from here no Pre-Season attempt can start.
4. **Void unfinished attempts** of the Pre-Season as `launch_reset`
   (`engine.void_attempts_for_launch`).
5. **Settle everything pending.** Voided attempts settle with a zero
   adjustment; an attempt that had ended just before launch gets its real
   Pre-Season result.
6. **Final transaction.** Re-lock the seasons, re-check that no official
   season exists and that no Pre-Season attempt remains unsettled; then set
   every `balances.current_points` to 0, set the Pre-Season's `frozen_at`, and
   insert the official season with its `closes_at`.

**Exactly once.** The official season's existence is the launch marker; a
repeat is refused. Steps 3–5 are idempotent, and the reset happens only in the
transaction that inserts the official season, so a failure before step 6
leaves a state from which running launch again completes it, and there is
never a reset without an official season.

**Records kept.** Accounts, attempts, answers, settlements and balance history
are untouched; Pre-Season rows are identified by their season.

## Phase ownership (a late Pre-Season result never reaches the official balance)

- **Start holds a share lock on its season** (`admitting_season(...,
  lock=True)`) until it commits. Launch's step 2 lock waits for a start in
  progress, so that attempt is visible to step 4; a start arriving after step
  3 is refused.
- **Settlement of an attempt whose season is frozen applies a zero
  adjustment**, whatever its answers. The raw score is still recorded.

## HTTP

`POST /api/ranked/season/launch` with body `{"label", "confirm",
"closes_at"?}`. Session required (401); owner required (403); `confirm` must
be exactly `LAUNCH` and `label` non-blank (422). `AlreadyLaunchedError` and
`NoPreSeasonError` are 409; `InvalidLaunchError` is 422. Success is 201 with
the new season's id, label and `closes_at`.

## Out of scope

The owner's second factor (#11/#13); the "pre season history" view (page
work); launch reminder delivery (#27); the season close flow (slice 3).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Launch voids a running attempt, keeps its answers, settles it at zero,
  resets every balance, freezes the Pre-Season and opens the official season.
- An attempt ended just before launch keeps its real result in history.
- Balance history is preserved.
- A second launch is refused and changes nothing.
- Blank label, past end time and no Pre-Season are refused with nothing
  changed.
- The default end is 2026-12-31 23:59:00 America/New_York.
- A launch interrupted after voiding completes when run again.
- After launch an official attempt starts and scores from 0.
- Settling an attempt of a frozen season applies zero.
- Races: launch waits for an answer in progress and for a start in progress.
- HTTP: 401, 403, 422 without the exact confirmation, 201 for the owner, 409
  on a repeat.
