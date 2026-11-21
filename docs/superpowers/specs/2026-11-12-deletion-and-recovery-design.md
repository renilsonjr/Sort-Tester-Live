# Deletion cascade/redaction and migration/restore/concurrency verification

Design for Issue #6 build/acceptance checks 5 and 6. Scope is private
PostgreSQL schema and its test contract only. No engine, API, deletion flow,
Support/connection tables, or backup automation is implemented here; those
belong to #47 (auth/deletion follow-ups), #8/#9 (engine/scoring), #25/#26
(support/connection), and #13 (operational backups).

## Owner decisions driving this design

- **Deletion model (owner, 2026-11-12): pending-purge.** Confirmed deletion
  first marks the account inaccessible by setting `accounts.deleted_at`, while
  a background purge removes the account's owned data and (per #13) provider
  and backup copies. Only after the purge is verified is the account row hard
  deleted, which cascades away anything still attached. The season-ineligibility
  marker survives because `season_markers` has no foreign key to `accounts`
  (established in migration 0004). This matches the decision record's "deletion
  remains pending until every managed purge finishes" and "no permanent
  deletion tombstone": `deleted_at` is a transient pending marker on a row that
  is on its way out, not a kept record of a gone account.
- **Shared-evidence redaction is deferred, not done here.** The decision record
  requires redacting/unlinking a deleted player's detail from shared connection
  evidence. Those tables (Support tickets, connection logs) do not exist yet
  (#25/#26), so there is nothing to redact at the schema level today. This is a
  conscious boundary, recorded so it is not mistaken for a gap.

## Check 5 — deletion cascade/redaction

### Already enforced by existing schema (0002–0011), to be proven by tests

Every account-owned table cascades on `DELETE FROM accounts`: `emails`,
`participant_links`, `login_credentials`, `sessions`, `assignments`,
`assignment_questions` (via `assignments`), `attempts`, `attempt_answers`
(via `attempts`), `balances`, `balance_history`, and `settlements` (via the
`(attempt_id, season_id)` composite FK to `attempts`). Shared, non-personal
content is deliberately **not** cascaded: `question_versions` and `seasons` are
referenced without `ON DELETE CASCADE`, so they survive. `season_markers` has
no FK and survives as the sole approved retention record.

### New schema — migration `0013_pending_deletion.py` (revises 0012)

Give the existing `accounts.deleted_at` column a tested meaning for the
pending-purge window:

- Partial index `accounts_pending_purge ON accounts (deleted_at) WHERE
  deleted_at IS NOT NULL`. This is the index the background purge worker uses
  to enumerate accounts awaiting purge; it also keeps active-account scans off
  the pending rows.
- `CHECK (deleted_at IS NULL OR deleted_at >= created_at)` so a pending
  timestamp cannot predate the account.
- `downgrade()` drops the CHECK constraint and the index. The `deleted_at`
  column itself is owned by 0002 and is left in place.

The migration adds no new table and does not change deletion mechanics
(hard delete + cascade already works); it only makes the pending state
queryable and integrity-checked.

## Check 6 — migration/restart/restore/concurrency tests

A new `backend/tests/test_db_deletion_and_recovery.py`, run against the live
scratch database and skipped cleanly when `SORT_TESTER_TEST_DATABASE_URL` is
unset or malformed, proves:

1. **Full-chain migrate and downgrade.** `0001 → head` applies clean; `head →
   base` runs every `downgrade` with no error and leaves no project table.
2. **Deletion cascade proof.** Seed account A with one row in every owned table
   plus a `season_marker`; seed account B with its own rows and a shared
   `question_version`. `DELETE` A. Assert: every A-owned row is gone across all
   tables, A's `season_marker` survives, and B's rows plus the shared
   `question_version` are untouched. No "Deleted player" row remains anywhere.
3. **Pending-deletion state.** Setting `deleted_at` on an account keeps the row
   and all its owned data (purge has not run), and the `accounts_pending_purge`
   partial index returns exactly that account. The CHECK rejects a `deleted_at`
   earlier than `created_at`.
4. **Restart persistence.** Rows committed on one connection are present after
   that connection closes and a new one opens, across the migrated schema.
5. **Concurrency constraints.** Two concurrent settlement inserts for one
   attempt (two live connections) → exactly one commits, the other fails on the
   `settlements` primary key (the at-most-once settlement key). A second
   `active` attempt for an account that already has one is rejected by the
   one-active-attempt partial unique index.
6. **Real restore.** `pg_dump` the scratch DB, drop and recreate it,
   `pg_restore`, and assert row counts and marker survival match the
   pre-dump state — an actual restore, not just an integrity check, per the
   backup-verification reference in the security/operations design.

## Testing and evidence

- TDD: each behavior gets a failing test first, then the migration/assertion
  that satisfies it, run against a local PostgreSQL 16 scratch cluster.
- Full `backend/tests` and `node --test tests/*.test.mjs` suites must stay
  green, including the clean-skip behavior when the test DB URL is absent.
- Branch `codex/db-deletion-recovery` → PR into `codex/ranked-mode`. Evidence
  recorded on #6; checks 5 and 6 ticked only with merged proof behind them.

## Out of scope (named so deferrals are deliberate)

- Self-service deletion flow, reauthentication, session revocation on delete,
  season-marker creation at acceptance (engine/service: #47).
- Shared-evidence redaction (#25/#26 tables do not exist yet).
- Provider/off-device backup erasure and operational restore runbook (#13).
- Prize-finalization serialization and withdrawal races (#8/#23/#24).
