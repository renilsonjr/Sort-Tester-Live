# Implementation plan — deletion/recovery verification (Issue #6 checks 5 & 6)

Design: `docs/superpowers/specs/2026-11-12-deletion-and-recovery-design.md`.
TDD against a local PostgreSQL 16 scratch cluster. Each task is one small,
reviewable change that runs green before the next.

## Task 1 — deletion cascade + marker-survival test (check 5, red first)

- Add `backend/tests/test_db_deletion_and_recovery.py` with a base class that
  recreates the scratch DB and migrates to head (mirrors existing schema tests).
- First test: seed account A across every owned table + a `season_marker`;
  seed account B + a shared `question_version`; `DELETE` A; assert full A-owned
  wipe, A marker survives, B and shared content untouched.
- Expected: passes immediately (existing cascades already enforce this). It is
  the regression lock, not a change driver.

## Task 2 — pending-deletion migration 0013 (check 5)

- Red: test that the `accounts_pending_purge` partial index exists and returns
  only accounts with `deleted_at` set, and that the CHECK rejects
  `deleted_at < created_at`. Fails (no index/CHECK yet).
- Green: `0013_pending_deletion.py` adds the partial index and CHECK; downgrade
  drops both.
- Verify full-chain upgrade/downgrade still clean with 0013 as head.

## Task 3 — migration chain + restart persistence (check 6)

- Extend the test module: `0001 → head` clean apply; `head → base` full
  downgrade leaves no project table; a committed row survives connection
  close/reopen.

## Task 4 — concurrency constraints (check 6)

- Two live connections insert a settlement for the same attempt → exactly one
  commits, the other hits the PK. Second `active` attempt rejected by the
  one-active-attempt partial unique index.

## Task 5 — real dump/restore (check 6)

- `pg_dump` scratch → drop/recreate → `pg_restore`; assert row counts and
  marker survival match pre-dump. Skip with a clear message if `pg_dump`/
  `pg_restore` are not on PATH (keep CI/other-machine runs honest).

## Task 6 — full-suite verification and evidence

- `backend/.venv/bin/python -m unittest discover -s backend/tests` with the
  scratch DB URL set (DB tests run) and unset (DB tests skip, no tracebacks).
- `node --test tests/*.test.mjs` stays green.
- Open PR into `codex/ranked-mode`; post evidence on #6; tick checks 5 and 6.
