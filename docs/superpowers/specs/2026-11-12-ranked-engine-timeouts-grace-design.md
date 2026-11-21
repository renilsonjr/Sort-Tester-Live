# Ranked attempt engine — timeouts, heartbeat and grace (Issue #8, slice 2)

Second slice of the ranked attempt engine. It builds on slice 1
(`2026-11-12-ranked-engine-core-design.md`) and adds the two server-owned
clocks that slice left out: the ten-second question clock running out, and the
fifteen-second connection grace. Scoring stays in #9; every ending here stops at
`terminal_pending`.

## Owner decisions (2026-11-12)

- **Heartbeat cadence:** the page sends a heartbeat every 1 second; the server
  declares a loss after 3 seconds without one. Grace is 15 seconds from that
  declaration (so 18 seconds after the last heartbeat).
- **Transport:** this slice builds the engine rules behind a plain HTTP
  heartbeat request. The persistent-connection (WebSocket) choice in the
  security/operations design waits until the backend is hosted, where it can be
  tested against the real platform.

## Known limit (not solved here)

"Reloading the page cannot resume the attempt" depends on the page-instance
capability, which is a later slice (#8 check 4). Until then any request carrying
the account session and attempt id can return within grace. This slice does not
claim original-page-only recovery.

## Part A — question timeouts

The server has no background timer. A timeout is recorded the next time a
request for that attempt arrives after the deadline.

- **Late answer:** `submit_answer` after `deadline_at` on an unanswered question
  records `answer='timeout'` and returns a timeout result. The submitted choice
  is discarded. This replaces slice 1's rejection of late answers.
- **Advance past a timeout:** `advance` on an unanswered question whose deadline
  has passed records `answer='timeout'`, then sends the next question or
  finishes. An unanswered question still inside its deadline is not skippable
  (`NotAnsweredError`, unchanged).
- **Idempotent:** once a question is `timeout`, later submits return that stored
  result and write nothing.
- `AnswerResult` gains `outcome` (`correct` / `wrong` / `timeout`).

## Part B — heartbeat, loss, grace and disconnect

**Schema:** migration `0014` adds `attempts.last_heartbeat_at timestamptz NULL`.
`start_attempt` sets it to the start time.

**Rules** (constants `HEARTBEAT_LOSS_SECONDS = 3`, `GRACE_SECONDS = 15`):

- Loss is declared at `last_heartbeat_at + 3s`. The grace deadline is that
  instant `+ 15s`. Both are derived from the stored heartbeat, never from when
  the server happened to notice.
- Every engine call for an attempt first synchronises its connection state:
  - no loss yet → continue;
  - loss declared, now strictly before the grace deadline → the request is a
    return: the attempt stays (or goes back to) `active`, question clocks are
    untouched, grace is not extended beyond this return;
  - now at or after the grace deadline → finalization wins: an unanswered sent
    question is recorded `timeout`, questions never sent get no row, and the
    attempt becomes `terminal_pending` with `final_outcome='disconnect'`.
- `heartbeat(conn, attempt_id, clock)` synchronises, then records
  `last_heartbeat_at = now`. Answer and advance requests also count as activity.
- A call on an attempt that has ended raises `AttemptEndedError`.
- `expire_stale_attempts(conn, clock, account_id=None)` applies the same rules
  to attempts nobody is calling: a silent attempt inside grace is marked
  `grace` with its `grace_deadline_at`; one past the deadline is finalized as a
  disconnect. `start_attempt` runs it for the account first, so an abandoned
  attempt is closed instead of staying `active` forever. The closed attempt
  still holds the one-unfinished-attempt lock until #9 settles it
  (`terminal_pending -> finalized`); only then can a new attempt start. A
  scheduler can call it for all accounts later.

## Part C — HTTP

`POST /api/ranked/attempts/{attempt_id}/heartbeat` with the same session and
ownership checks as the other endpoints. An ended attempt returns 410 on every
attempt endpoint.

## Out of scope

Explicit Quit and its penalty marker, confirmed-outage void, promotion entry,
phase/round hooks, the page capability, loss IDs and review flags (#25), the
rule that the fifteenth question finishes without Next, and the WebSocket
transport.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Late answer → `timeout`; advance past a timed-out question; live question not
  skippable; an all-timeout attempt reaches `terminal_pending`/`completed`.
- Heartbeats keep an attempt alive past 18 seconds.
- Return just before the grace deadline continues; the question clock was not
  reset.
- Call exactly at the grace deadline → `disconnect`, current question `timeout`,
  unsent questions have no row, later calls raise `AttemptEndedError`.
- `expire_stale_attempts` marks `grace`, then finalizes; starting again closes
  an abandoned attempt, and a new one can start once the old one is settled.
- Migration 0014 upgrades and downgrades cleanly; full suites stay green.
