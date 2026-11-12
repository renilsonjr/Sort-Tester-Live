# Ranked attempt engine — connection events (Issue #8, slice 8)

Eighth slice of the ranked attempt engine. It builds on slice 7
(`2026-11-12-ranked-engine-serialization-season-design.md`). It provides the
connection hook #25 needs and adds the two race tests still missing from #8's
"first send / races" check.

## Part A — remaining race tests

- **Timeout edge.** An answer whose time equals the question deadline is
  graded; one any later is a timeout. (Advance already has the equivalent
  test.)
- **Expiry against a return.** A player returns just inside grace while the
  stale-attempt sweep runs with a clock already past the old grace deadline.
  The return holds the attempt lock first; the sweep waits, then sees the new
  heartbeat and leaves the attempt active. No disconnect is recorded.

These exercise existing behaviour; no engine change is expected.

## Part B — connection events (hook for #25)

The engine notices losses, returns and grace expiries but keeps no record.
#25 needs that history to count loss sequences.

**Schema.** Migration `0016` adds:

```
attempt_connection_events (
    id          uuid primary key,
    attempt_id  uuid not null references attempts(id) on delete cascade,
    kind        'loss' | 'recovery' | 'expiry',
    occurred_at timestamptz not null,
    unique (attempt_id, kind, occurred_at)
)
```

**Events.**

| kind | written when | `occurred_at` |
|---|---|---|
| `loss` | an engine call or the sweep finds the attempt silent for at least `HEARTBEAT_LOSS_SECONDS` | last heartbeat + 3 s (the declaration instant) |
| `recovery` | a call that counts as activity arrives after a loss and before the grace deadline | the time of that call |
| `expiry` | the attempt ends as a disconnect | the grace deadline |

**Rules.**

- One loss per uninterrupted interruption: the loss instant is derived from
  the stored heartbeat, so noticing the same silence again produces the same
  row, which the unique key discards (`ON CONFLICT DO NOTHING`).
- A further loss requires a recovery first: a recovery moves the stored
  heartbeat, so the next silence has a different loss instant.
- A read (`current_question`) during a loss records the loss but is not a
  recovery, matching the rule that reading is not activity.
- A loss is recorded whenever the silence is found, including when the same
  call then completes the attempt on a final-question timeout.
- The engine only writes events. It never reads them to decide anything and
  imports nothing from #25.
- Rows hold an attempt id, a kind and a time. They are removed with the
  attempt, and so with the account.

## Out of scope

Loss-sequence counting, review flags, excluding confirmed outages, staff
views and the 15-day retention (#25/#26); per-mode settings (#24, next
slice).

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Steady heartbeats write no events.
- Return after five seconds of silence: one loss at +3 s, one recovery at +5 s.
- Sweep marks grace, then the player returns: still one loss.
- Two separate interruptions: two losses and two recoveries.
- Grace expiry by a call and by the sweep: loss and expiry, no recovery.
- A read during a loss: loss only.
- Events are deleted with the account.
- Migration 0016 upgrades and downgrades in the full-chain test.
