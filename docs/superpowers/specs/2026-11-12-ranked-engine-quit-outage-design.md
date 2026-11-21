# Ranked attempt engine — Quit and outage void (Issue #8, slice 3)

Third slice of the ranked attempt engine. It builds on slice 2
(`2026-11-12-ranked-engine-timeouts-grace-design.md`) and adds the two
remaining ways a normal attempt can end besides completion and disconnect:
an explicit Quit and a confirmed-outage void. Scoring stays in #9; both endings
stop at `terminal_pending` and only record `final_outcome`.

## Owner decisions (2026-11-12)

- **Live question on Quit:** a sent question still inside its ten seconds when
  the player quits stays unanswered and is not deducted. Quit costs only the
  −10 that #9 applies. A question whose deadline had already passed is a
  timeout, as it would be without the Quit.
- **Outage scope:** this slice builds the engine rule only. Nothing calls it
  yet; detection and the trigger wait for the hosted backend (#13).

## Part A — Quit

`quit_attempt(conn, attempt_id, *, clock) -> str` returns the attempt's final
outcome.

- On an unfinished attempt it first synchronises the connection clock (slice
  2). If the grace deadline has already passed, the disconnect wins and
  `'disconnect'` is returned; no Quit is recorded.
- Otherwise the attempt becomes `terminal_pending` with
  `final_outcome='quit'`. An unanswered sent question past its deadline is
  recorded `timeout`; one still inside its deadline keeps `answer` NULL.
  Questions never sent get no row.
- On an attempt that has already ended it changes nothing and returns the
  stored outcome. A repeated Quit therefore returns `'quit'` again, and a Quit
  that lost a race with completion returns `'completed'`.
- The `quit` outcome is the penalty marker. The engine applies no points.

HTTP: `POST /api/ranked/attempts/{attempt_id}/quit` with the usual session and
ownership checks returns `200 {"final_outcome": ...}`, including on an attempt
that had already ended (it is the one endpoint that does not answer 410, so a
retried Quit gets the same answer).

## Part B — outage void

`void_attempts_for_outage(conn, *, outage_start, outage_end) -> int` returns
the number of attempts voided. It sets `terminal_pending` with
`final_outcome='outage_void'` on:

- every `active` or `grace` attempt whose `started_at <= outage_end`;
- every `terminal_pending` attempt with `final_outcome='disconnect'` whose
  silence overlaps the outage: `last_heartbeat_at <= outage_end` and
  `grace_deadline_at >= outage_start`.

It leaves alone attempts that ended `completed` or `quit`, attempts already
`finalized` (a committed balance is never reversed), and disconnects whose
silence does not overlap the window. Recorded answers are kept as history; #9
gives a voided attempt a zero adjustment.

Supporting change: `start_attempt` sets `attempts.started_at` from the engine
clock rather than the database default, so the window comparison and its tests
use one time source.

## Out of scope

Outage detection, evidence watermarks, and holding a disconnect's settlement
pending until classification commits (#9/#13); tie-break round restarts (#24);
promotion entry; the page capability; loss IDs and flags (#25); the rule that
the fifteenth question finishes without Next.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Quit on a live question → `quit`, question left unanswered.
- Quit after the question deadline → `quit`, question `timeout`.
- Quit twice → same outcome, nothing rewritten; later calls raise
  `AttemptEndedError`.
- Quit after grace expiry → `disconnect`.
- Quit on a completed attempt → `completed`.
- HTTP: quit returns 200 with the outcome, twice; 401 and 404 checks.
- Outage void: active attempt started before the outage end is voided; one
  started after is not; an overlapping unsettled disconnect is reclassified; a
  non-overlapping disconnect, a quit, a completed and a finalized attempt are
  untouched; answers are kept.
