# Ranked attempt engine — per-attempt serialization and season endings (Issue #8, slice 7)

Seventh slice of the ranked attempt engine. It builds on slice 6
(`2026-11-12-ranked-engine-promotion-entry-design.md`). It closes a
concurrency gap, adds the race tests #8 asks for, and provides the two season
hooks #23 needs.

## Part A — one call at a time per attempt

**Gap.** The security/operations design requires answer, timeout, Quit, loss
expiry and season cutover to be serialized. Every engine call begins by
locking the attempt row (`SELECT ... FOR UPDATE`), but the lock is released
almost immediately, because recording the call as activity commits. Two calls
for the same attempt arriving together can then interleave: two Next requests
both try to insert the same next question (the second fails with an integrity
error), an answer can be graded against a state another call has just changed,
and an answer can be written into an attempt a concurrent Quit has ended.

**Rule.** An engine call for an attempt holds the attempt row lock from its
first statement until its single commit. A second call for the same attempt
waits, then runs against the committed result of the first.

- `_sync_connection` no longer commits on the activity path. The public
  function that called it commits once, at its end.
- A call that refuses the request after synchronising (`NotAnsweredError`,
  `AnswerRejectedError`) commits before raising, so the activity it recorded
  is kept and the lock is released.
- `current_question` commits at its end to release the lock; it writes nothing
  unless synchronising ended the attempt.
- Paths that end the attempt inside synchronisation (grace expiry, final
  question timeout) already commit before raising and are unchanged.

Results under contention:

- Two answers to one question: the first is stored; the second returns that
  stored result.
- Two Next requests: one sends the next question; the other finds it live and
  unanswered and gets `NotAnsweredError`. Exactly one question is created.
- Answer and Quit: whichever holds the lock first completes; the other then
  sees the result. An answer is never written into an ended attempt.
- Final answer and Quit: exactly one ending is recorded.
- Two starts for one account: the unique index admits one; the other gets
  `ActiveAttemptExistsError`.

A question is never exposed without a running deadline: a question row is
created only by `_send_question`, which sets `first_sent_at` and `deadline_at`
in the same insert, and `current_question` reads only such rows.

## Part B — season close (hook for #23)

`end_attempts_for_season_close(conn, season_id, *, clock) -> int` ends every
unfinished attempt (`active` or `grace`) of that season as `terminal_pending`
with `final_outcome='season_close'` and returns how many it ended.

- #23 decides when to call it: after the five-minute finishing window. The
  engine holds no season timer.
- A sent question past its deadline is recorded `timeout`; one still inside
  its deadline stays unanswered and is not deducted; never-sent questions get
  no row. No Quit marker, no flag.
- If the final question has already timed out, the attempt is `completed`
  instead, as in every other path.
- Attempts of other seasons and attempts that already ended are untouched.

Admission at close needs no new code: `start_attempt` admits only into a
season whose `closed_at` is NULL.

## Part C — season launch (hook for #23)

`void_attempts_for_launch(conn, season_id) -> int` voids every unfinished
attempt of the given (Pre-Season) season as `terminal_pending` with
`final_outcome='launch_reset'` and returns the count. Recorded answers are
kept as history; #9 gives a launch-reset attempt a zero adjustment. Attempts
that already ended, including completed ones awaiting settlement, are
untouched: what happens to those at launch is #23's decision.

## Out of scope

The season state machine, the finishing-window timer, owner-only launch,
balance reset and freeze (#23); connection events (#25, next slice); per-mode
settings for tie-breaks (#24, slice after next); settlement (#9).

## Testing (TDD, live scratch PostgreSQL)

Race tests use two database connections on two threads. The first call is
paused in the middle of its work, after it has synchronised; the test then
starts the second call, checks that it is waiting, releases the first and
checks the combined result.

- Two answers; two Next; answer against Quit; final answer against Quit; two
  starts.
- After an answer and before Next there is no live question and no row for the
  next question.
- Season close: ends active and grace attempts of the season; timeout versus
  unanswered rule; final-question timeout completes; other seasons and ended
  attempts untouched; later calls raise `AttemptEndedError`.
- Season launch: voids unfinished attempts of the season, keeps answers,
  leaves ended attempts and other seasons alone.
