# Ranked attempt engine — per-mode settings (Issue #8, slice 9)

Ninth slice of the ranked attempt engine. It builds on slice 8
(`2026-11-12-ranked-engine-connection-events-design.md`). It is the round hook
for #24: the engine stops assuming one quiz shape, so prize tie-break attempts
can later bring their own.

Owner decision (2026-11-12): prize tie-breaks stay in project scope (#24, with
its question bank in #55), and #8 prepares the engine with per-mode settings
now.

## Design

`backend/ranked/modes.py` holds the shape of each kind of attempt:

```
ModeSettings(question_count, question_seconds)

normal     -> 15 questions, 10 seconds
promotion  -> 15 questions, 10 seconds
```

`settings_for(mode)` returns the settings and raises `ValueError` for a mode
that has none.

The engine no longer has `QUESTION_COUNT` and `QUESTION_SECONDS`. It reads the
settings of the attempt's own mode wherever it used them:

- the deadline given to a question when it is sent;
- whether an accepted answer was the final one;
- whether the final question has timed out, in the per-call synchronisation
  and in the stale-attempt sweep.

`start_attempt` checks that the assignment it selected has exactly
`question_count` questions and refuses the start, before writing anything, if
it does not.

## Behaviour

Unchanged for normal and promotion attempts: every existing test passes
without modification.

## Not in this slice

No tie-break entry is added. Tie-break timers depend on the badge tier and the
round (five, four, then three seconds), questions advance without Next, and
results stay hidden until the round deadline; those rules, the tie-break
assignment and its settings are #24. A tie-break start is still refused.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- `settings_for` returns 15 and 10 for normal and promotion, and raises for an
  unknown mode and for `tiebreak`.
- With the normal settings temporarily replaced by three questions of four
  seconds (and the selection trimmed to match): the question deadline is four
  seconds after sending, the third answer finishes the attempt, and a
  timed-out third question completes it.
- A selection whose size does not match the settings is refused and nothing is
  written.
- The full existing suite passes unchanged.
