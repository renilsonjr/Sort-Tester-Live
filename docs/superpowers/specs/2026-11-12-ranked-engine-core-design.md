# Ranked attempt engine — core happy path (Issue #8, slice 1)

First slice of the server-authoritative ranked attempt engine. Scope is the
normal-mode happy path: start an attempt, serve questions on server-owned
10-second deadlines, accept locked answers with Next-paced feedback, run
forward-only through 15 questions, and end in `terminal_pending`. No point math
here — scoring, caps, and balance are #9.

## Boundary with #9 (owner decision, 2026-11-12)

The engine records per-answer results and drives the attempt to
`terminal_pending`. It does **not** compute point values. #9 reads the finalized
answers, computes the raw score, applies ±values/caps/promotion, writes the
`settlements` + `balances` rows atomically, and transitions
`terminal_pending → finalized`. The `attempts.terminal_pending` state is exactly
this handoff.

## Out of scope for this slice (later #8 slices)

Timeout resolution, 15-second grace, disconnect/outage void, explicit Quit,
promotion-gate entry, phase/round/connection hooks, and the page-capability
token for one-active-attempt enforcement. This slice still relies on the DB's
one-active-attempt partial unique index to reject a second `active` attempt
with a clean error. Season creation is #23; this slice requires an open season
row (`closed_at IS NULL`) to already exist.

## Components — new `backend/ranked/` package (mirrors `backend/auth/`)

- **`clock.py`** — a `Clock` protocol (`now() -> datetime`, UTC) with a real
  system clock. Tests inject a fake clock so 10-second deadlines are
  deterministic, with no real waiting. The engine never calls
  `datetime.now()` directly; time always arrives through the injected clock.
- **`versions.py`** — `materialize_question_version(conn, question)`: idempotent
  upsert into `question_versions` keyed by `(bank_key, content_sha256)` where
  `bank_key = question.canonical_id` and
  `content_sha256 = question_content_digest(question)`; returns the version id.
  This is the durable bank-content → immutable version-row integration folded in
  from #5. The bank text itself stays in `backend/ranked_bank`, never in the DB.
- **`engine.py`** — the service layer over a DB connection and a clock:
  - `start_attempt(conn, account_id, *, clock, bank)`
  - `current_question(conn, attempt_id)`
  - `submit_answer(conn, attempt_id, seq, choice, *, clock)`
  - `advance(conn, attempt_id, *, clock)`
- **`routers/ranked.py`** — a thin FastAPI router (start / current / answer /
  next) that adapts HTTP to the engine. **Not** wired into `index.html`; the
  published static site is unchanged, matching the auth router.

## Data flow

**start_attempt**
1. Find the open season (`closed_at IS NULL`, newest). None → error.
2. `select_assignment(bank)` → 15-question snapshot (5 Easy / 5 Medium / 5 Hard).
3. For each question, `materialize_question_version` → version id.
4. Insert `assignments` (`mode='normal'`, season) and 15 ordered
   `assignment_questions` (`seq` 1..15 in snapshot order).
5. Insert `attempts` (`state='active'`, season). A second active attempt for the
   account is rejected by the one-active-attempt index → clean error.
6. Send question 1: insert its `attempt_answers` row — `first_sent_at=now`,
   `deadline_at=now+10s`, `answer=NULL`, `outcome='unsent'`.

**current_question** — return the single live question (the `attempt_answers`
row with `answer IS NULL`): its localized text/presentation and the server
`deadline_at`.

**submit_answer** — reject if `seq` is not the live question, `now > deadline_at`,
or the row is already answered. Grade `choice` against the question's
`correct_belt` → `'correct'` / `'wrong'`. One-way
`UPDATE answer=…, accepted_at=now WHERE answer IS NULL` (a double submit changes
nothing — idempotent). Return correctness feedback, which the client holds until
Next.

**advance** — only valid once the live question is answered. If questions remain,
send the next (insert its row, `first_sent_at=now`). On the 15th, transition the
attempt to `terminal_pending` with `final_outcome='completed'`, leaving
`settled_at` NULL for #9.

## Schema-contract notes (non-obvious)

- `answer` (one-way settable: `correct`/`wrong`/`timeout`) is the authoritative
  per-question result. `outcome` stays the `'unsent'` placeholder written at
  send — the immutability trigger forbids changing it. A seq with **no**
  `attempt_answers` row means never-sent → #9 applies no deduction.
- `terminal_pending` requires `final_outcome` set and `settled_at` NULL;
  `finalized` (with `settled_at`) belongs to #9.

## Error handling

- No open season → `NoOpenSeasonError`.
- Second active attempt for an account → `ActiveAttemptExistsError` (surfaced
  from the DB lock).
- Submit to a non-current seq, past the deadline, or an already-answered row →
  `AnswerRejectedError`.
- Advance while the current question is unanswered → `NotAnsweredError`.

## Testing (TDD, live scratch PostgreSQL + fake clock)

- Full happy path: start → answer all 15 within deadline → attempt is
  `terminal_pending`, `final_outcome='completed'`, `settled_at IS NULL`, with 15
  recorded answers.
- Idempotent double-submit: the second submit accepts nothing new.
- Forward-only: answering seq 2 before seq 1 is resolved is rejected.
- Deadline: a submit at `now > deadline_at` is rejected.
- Version materialization is idempotent: the same question twice yields one
  `question_versions` row.
- Backend and Node suites stay green, including clean DB-test skips when
  `SORT_TESTER_TEST_DATABASE_URL` is unset.
