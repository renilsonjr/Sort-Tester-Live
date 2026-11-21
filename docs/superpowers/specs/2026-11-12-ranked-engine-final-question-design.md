# Ranked attempt engine — final question completes without Next (Issue #8, slice 5)

Fifth slice of the ranked attempt engine. It builds on slice 4
(`2026-11-12-ranked-engine-page-capability-design.md`) and implements the last
part of the pacing rule in #8: "feedback waits for Next; the next timer starts
once on accepted Next; the final answer or timeout completes without Next".

Until now the attempt completed only when the player pressed Next after
question 15. A player who answered it and left was later closed as a
`disconnect`.

## Rules

- **Final answer completes.** `submit_answer` on question 15 records the
  answer and, in the same transaction, moves the attempt to `terminal_pending`
  with `final_outcome='completed'`. `AnswerResult` gains `finished: bool`.
- **Final timeout completes.** There is no background timer. Every engine call
  first checks whether question 15 is sent, unanswered and past its deadline;
  if so it records `timeout` and completes the attempt before doing anything
  else. This check runs ahead of the connection-grace check, in both the
  per-call synchronisation and `expire_stale_attempts`.
- **Next after question 15 is gone.** The attempt has already ended, so
  `advance` raises `AttemptEndedError` like any other call. `AdvanceResult`
  loses `finished`; it only reports `next_seq`.

## Consequences

- A player silent during question 15 always ends `completed`, never
  `disconnect`: the question deadline (10 s after it was sent) always precedes
  the grace deadline (at least 18 s after it was sent), and a timeout on the
  final question completes the attempt. Owner approved, 2026-11-12.
- A late answer to question 15 finds the attempt already completed by the
  timeout and gets `AttemptEndedError` (410 over HTTP).
- Quit on question 15 inside its deadline is still `quit`. Quit after the
  deadline returns `completed`.
- A retried final answer gets 410 rather than the stored result; the page
  treats 410 as "the attempt is over".

## HTTP

The answer response gains `finished`. The advance response is
`{"next_seq": n}`.

## Out of scope

Promotion entry, phase hooks, loss IDs and flags (#25), WebSocket transport,
front-end wiring.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Answering question 15 completes the attempt; earlier answers report
  `finished` false.
- Advance after the final answer raises `AttemptEndedError`.
- Question 15 timing out is completed by the next heartbeat, by
  `expire_stale_attempts`, and before a grace expiry could apply.
- A late answer to question 15 raises `AttemptEndedError`; the stored answer
  is `timeout`.
- Quit on a live question 15 is `quit`; after its deadline it is `completed`.
- An all-timeout attempt still ends `completed` with 15 timeouts.
- HTTP round trip finishes on the fifteenth answer with no advance.
