# Connection review flags — review, closure and retention (Issue #25, slice 3)

Third and last slice of #25. It builds on flags and confirmed outages
(`2026-11-13-connection-flags-design.md`). It lets the owner review flags,
close a reviewed flag, and removes closed flags and their detailed connection
events after fifteen days.

Rules are the owner's (decision record, Decisions 7 and 8): flags are
reviewed only by authorized administrators, never shown to other players, on
profiles or leaderboards; review outcomes are closing as network instability,
closing as insufficient evidence without accusation, or leaving open; closure
changes no points or access; each closed review's description and its unshared
detailed connection events are deleted fifteen days after closure, while
seasonal scores and quiz history remain.

## Schema

Migration `0019` adds to `connection_flags`:

- `closed_at timestamptz NULL`
- `closed_outcome varchar NULL`, one of `network_instability`,
  `insufficient_evidence`

Both are set together or both are NULL.

## Part A — owner review

`backend/ranked/flags.py`:

- `open_flags(conn)` returns open flags, oldest first, each with the attempt
  id, the player's username and tag, the run's first and last loss, when it
  was flagged, and the attempt's connection events (`kind`, `occurred_at`).
  Nothing else about the player is returned.
- `close_flag(conn, attempt_id, outcome, *, clock)` closes an open flag.
  Unknown outcome: `ValueError`. No flag: `FlagNotFoundError`. Closing an
  already closed flag changes nothing and returns its stored outcome.

HTTP, owner only (401 without a session, 403 for any other account, including
the flagged player):

- `GET /api/ranked/flags`
- `POST /api/ranked/flags/{attempt_id}/close` with `{"outcome": ...}`; 404
  for no flag, 422 for an unknown outcome.

"Leave open" is not closing. Closing never touches points or access.

**Outage reconciliation keeps reviews.** `record_outage` removes a flag the
outage explains. A flag that still qualifies is updated to its new run only if
it is open; a closed flag that still qualifies keeps its review.

## Part B — retention

`purge_closed_flags(conn, *, clock) -> int` deletes every flag closed fifteen
days or more ago together with that attempt's `attempt_connection_events`, and
returns how many flags it removed. Attempts, answers, settlements and balance
history are untouched. Ranked requests run it before their work, like the
season close; when nothing is due it is one read.

Shared evidence linked to an open Support ticket is #26: there are no tickets
yet, so nothing can be linked and the fifteen-day rule applies directly.
Account deletion already removes flags and events through the cascade (#69);
the deletion flow itself is #47.

## Tests (TDD, live scratch PostgreSQL)

- Read: 401, 403 for a player and for the flagged player, the owner's list
  with only the listed fields and the attempt's events, closed flags absent.
- Close: both outcomes, unknown outcome, no flag, repeat close; points and
  admission unchanged.
- Outage after closure: a closed flag the outage does not explain keeps its
  review; one it explains is removed.
- Retention: purged at fifteen days, kept at fourteen, open flags never
  purged, history kept.
- Races: a second tab's refused heartbeats record no events during a flapping
  run; grace expiry mid-run still evaluates the losses that happened.
