# Seasons — the season clock (Issue #23, slice 1)

First slice of #23. It gives a season a scheduled end and a derived status,
and makes Ranked admission follow the clock. Launch, the finishing-window
ending and the freeze are later slices that build on it.

Rules come from the decision record: Decision 11 (Pre-Season until an
owner-controlled manual launch; the first official season ends December 31,
2026 at 11:59 p.m. America/New_York) and Decision 13 (stop new Ranked
admission at closing; already-started attempts get five extra minutes).

## Owner decisions (2026-11-12)

- **Close is automatic by the clock.** The end time is stored on the season;
  from that instant the server refuses new Ranked attempts without anyone
  acting.
- **Launch requires the owner account and a typed confirmation** (the new
  season's name and the word LAUNCH). Built in slice 2. The second sign-in
  factor the security/operations design asks for owner actions is #11/#13 and
  is not provided by #23.

## Plan for #23

1. Season clock (this slice).
2. Launch exactly once: void unfinished Pre-Season attempts, settle, reset
   balances, open the official season.
3. Close: finishing window, end and settle unfinished attempts, freeze.
4. Lifecycle status over HTTP and phase-race tests.

## Design

**Schema.** Migration `0017` adds to `seasons`:

- `closes_at timestamptz NULL` — the scheduled end. NULL for Pre-Season.
- `frozen_at timestamptz NULL` — when the season's points became final. Set by
  a later slice.

**`backend/ranked/seasons.py`.**

- `FINISHING_WINDOW_SECONDS = 300`.
- `ensure_pre_season(conn, label="Pre-Season")` creates the Pre-Season row if
  the table is empty and returns the newest season's id; otherwise it creates
  nothing.
- `admitting_season(conn, now)` returns the id of the season that admits new
  Ranked attempts at `now`, or `None`. A season admits when it is not closed
  (`closed_at` NULL), not frozen, and its `closes_at` is NULL or still in the
  future. At exactly `closes_at` admission has stopped.
- `season_status(conn, season_id, now)` returns the season's `phase`, `label`,
  `closes_at` and a derived `status`:

| status | meaning |
|---|---|
| `open` | admits new attempts |
| `finishing` | ended less than five minutes ago: no admission, running attempts may finish |
| `closed` | the finishing window is over; not yet frozen |
| `frozen` | `frozen_at` is set |

  A season's end is `closed_at` if set, otherwise `closes_at` once it has
  passed. There is no background timer; status is derived on each call.

**Engine.** `start_attempt` admits into `seasons.admitting_season(conn,
clock.now())` instead of "the season whose `closed_at` is NULL". Nothing else
in the engine changes: an attempt already running when its season ends keeps
running, and is ended by slice 3 after the finishing window.

## Out of scope

Launch and the balance reset, ending and settling at close, the freeze, the
HTTP status endpoint, prize contracts, the launch outbox.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- `ensure_pre_season` creates one row, and a second call creates none.
- Admission: no end time; an end in the future; exactly at the end; after it;
  a closed season; a frozen season.
- Status at each boundary: open, finishing (at the end and one second before
  the window closes), closed (at five minutes), frozen.
- Engine: a start one second before the end succeeds; a start at the end is
  refused with `NoOpenSeasonError`; an attempt started before the end can
  still be answered after it.
- Migration 0017 upgrades and downgrades in the full-chain test.
