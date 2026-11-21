# Connection review flags — the counting rule (Issue #25, slice 1)

First slice of #25. It decides, from one attempt's connection events, whether
the attempt contains a run of losses that qualifies for a private review flag.
Pure arithmetic: no database. Saving flags, confirmed outages and the review
lifecycle are later slices.

The rule is the owner's (decision record, Decision 7): count distinct losses
after recovery; duplicates for one uninterrupted loss count once; four losses
qualify when each consecutive gap is under five seconds; a gap of exactly five
seconds or more starts a new sequence. Example: server-observed losses at 0,
4, 8 and 12 seconds with recovery between them.

## Owner decisions (2026-11-13)

- **One flag per attempt.** A second qualifying run in the same attempt adds
  nothing.
- **Confirmed outages are saved** (start and end), so losses inside one never
  count and a flag is removed if an outage covering it is confirmed later.
  Slice 2.

## Plan for #25

1. The counting rule (this slice).
2. Flags and confirmed outages: create a flag when an attempt ends, exclude
   losses inside confirmed outages, reconcile when an outage is confirmed
   later. Never touches points or admission.
3. Review closure, the 15-day clean-up and an owner-only read.

## Design

`backend/ranked/instability.py`.

Input is the attempt's connection events as `(kind, occurred_at)` pairs, as
the engine writes them (#8): `loss` at the declaration instant, `recovery` on
a return inside grace, `expiry` at the grace deadline.

- `distinct_losses(events)` returns the loss instants in time order, counting
  one loss per uninterrupted interruption: a loss with no recovery since the
  previous loss is the same interruption and is not counted again. `expiry`
  events are ignored. Events at the same instant are ordered loss, recovery,
  expiry.
- `qualifying_run(events)` returns the first run of `RUN_LENGTH` (4) distinct
  losses in which every consecutive gap is strictly less than
  `MAX_GAP_SECONDS` (5), as `Run(first_loss_at, last_loss_at)`; otherwise
  `None`. A gap of five seconds or more ends the current run and the later
  loss starts a new one.

An unknown event kind raises `ValueError`.

A real attempt can produce such gaps: the engine declares a loss three seconds
after the last heartbeat, so a connection that gets one heartbeat through and
drops again yields losses about four seconds apart.

## Out of scope

Persistence, outage exclusion, the sequence reset at attempt end (the rule is
applied per attempt by its caller), review and retention.

## Testing (unit tests, no database)

- The decision's example (0/4/8/12) qualifies; three losses do not.
- A gap of exactly five seconds resets; a gap just under five qualifies.
- After a reset, a later run of four still qualifies and reports its own
  first and last loss.
- Losses without an intervening recovery count once.
- More than four close losses report the first qualifying run.
- Unordered input, `expiry` events, an empty list, and an unknown kind.
