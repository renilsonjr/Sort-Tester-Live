# Connection review flags — flags and confirmed outages (Issue #25, slice 2)

Second slice of #25. It builds on the counting rule
(`2026-11-13-connection-instability-rule-design.md`). It saves a private review
flag when an attempt's connection events qualify, and saves confirmed outages
so losses the server caused never count.

Rules are the owner's (decision record, Decision 7): use server-confirmed
events; reset the sequence at attempt end; retain a previously created flag;
exclude confirmed server outages; flags are instability signals, not proof of
cheating, and never deduct points, suspend, restrict Ranked or create Support
tickets. A confirmed outage gives "no flag" (worked examples 8 and 64).

## Owner decisions (2026-11-13)

- One flag per attempt.
- Confirmed outages are saved; losses inside one never count, and a flag is
  removed if an outage covering its run is confirmed later.

## Schema

Migration `0018`:

- `confirmed_outages (id, starts_at, ends_at, recorded_at)`, with
  `ends_at >= starts_at`.
- `connection_flags (attempt_id PRIMARY KEY REFERENCES attempts ON DELETE
  CASCADE, first_loss_at, last_loss_at, flagged_at)`. The primary key is the
  one-flag-per-attempt rule; the cascade removes flags with the attempt, and
  so with the account.

## Part A — flag creation

`backend/ranked/flags.py`: `evaluate_attempt(conn, attempt_id, *, clock)`
returns True when the attempt has a flag after the call.

1. A voided attempt (`outage_void`, `launch_reset`) is never flagged.
2. Read the attempt's connection events and drop every event that falls inside
   a confirmed outage.
3. Apply `instability.qualifying_run`. If it qualifies, insert the flag
   (`ON CONFLICT DO NOTHING`).

It runs inside settlement's transaction, right before the commit, so a scored
attempt and its flag are saved together, and every path that scores an attempt
(the HTTP layer, the sweep, launch, season close) evaluates it. Evaluating per
attempt at its end is the "reset at attempt end". A flag changes nothing else.

## Part B — recording an outage

`record_outage(conn, *, starts_at, ends_at, clock) -> int` (Part B):

1. Save the outage.
2. Void the attempts it interrupted (`engine.void_attempts_for_outage`) and
   settle them.
3. Remove every flag whose run overlaps the outage, then re-evaluate those
   attempts without the outage's events; a flag returns only if the attempt
   still qualifies on its own. A voided attempt keeps no flag.

Returns the number of flags removed for good.

## Out of scope

Who may read flags, closing a reviewed flag and the 15-day clean-up (slice 3);
how an outage gets confirmed (monitoring, #13).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Four close losses then an ending: one flag with the run's first and last
  loss; three losses: none.
- A flag changes nothing else: points, badge and history are exactly what
  scoring gives, and the account can start again.
- Settling twice keeps one flag.
- A voided attempt is never flagged.
- Losses inside a saved outage do not count.
- Part B: recording an outage removes an overlapping flag, keeps a flag the
  outage does not explain, leaves other attempts alone, and voids and settles
  interrupted attempts.
- Migration 0018 in the full-chain test.
