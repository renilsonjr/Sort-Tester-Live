# Implementation plan — ranked engine core (Issue #8, slice 1)

Design: `docs/superpowers/specs/2026-11-12-ranked-engine-core-design.md`.
TDD against the local PostgreSQL scratch cluster with an injected fake clock.
Each piece runs green before the next; each is explained to the owner and
confirmed before moving on.

## Piece 1 — the clock (`backend/ranked/clock.py`)

- `Clock` protocol (`now() -> aware UTC datetime`) and `SystemClock`.
- Tests: `SystemClock.now()` is UTC-aware and non-decreasing; a `FakeClock`
  returns a fixed time and advances on demand (the engine's test time source).

## Piece 2 — durable question versions (`backend/ranked/versions.py`)

- `materialize_question_version(conn, question)`: idempotent upsert into
  `question_versions` keyed by `(canonical_id, question_content_digest)`.
- Tests: first call inserts, second call for the same content returns the same
  id with no duplicate row.

## Piece 3 — the engine (`backend/ranked/engine.py`)

- `start_attempt`, `current_question`, `submit_answer`, `advance`.
- Tests (happy path): start → answer 15 within deadline → `terminal_pending`
  with `final_outcome='completed'`, `settled_at IS NULL`, 15 answers; idempotent
  double-submit; forward-only; late submit rejected; no open season errors.

## Piece 4 — thin HTTP router (`backend/routers/ranked.py`)

- start / current / answer / next endpoints adapting HTTP to the engine; not
  wired into `index.html`.
- Tests: a happy-path round trip through the router; validation/404 behavior.

## Verification

- `backend/.venv/bin/python -m unittest discover -s backend/tests` with the
  scratch DB URL set (engine tests run) and unset (clean skips, no tracebacks).
- `node --test tests/*.test.mjs` stays green.
- Branch `codex/ranked-engine-core` → PR into `codex/ranked-mode`; evidence on
  #8 (its happy-path check), remaining #8 checks stay open for later slices.
