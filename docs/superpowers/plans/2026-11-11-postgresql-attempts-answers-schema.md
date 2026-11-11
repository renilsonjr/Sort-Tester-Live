# PostgreSQL Attempts and Answers Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model issue #6's third acceptance check — immutable question versions, frozen per-attempt assignments, one active attempt per account including grace, immutable answers with first-send/deadline and idempotency, phase/season version guards, and unique settlement keys — as migrations 0005–0007 with constraint-proving tests.

**Architecture:** Schema-only continuation of the identity chain (0001–0004). No engine, no API, no balance math: the balance/adjustment atomicity and outbox are acceptance check 4; scoring values stay application rules. The active-attempt lock, immutability, and once-only settlement are database constraints so later engine work inherits them structurally.

**Tech Stack:** PostgreSQL 18, psycopg 3.3.8, Alembic 1.20.1, Python 3.14 venv — unchanged pins.

**Spec:** `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` (Decision 6 one-active-attempt; Decision 12 phase cutover; Decision 13 season close; Decisions 9–10 tie-break rules) and `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md` (Q8: server-owned current question/deadline, monotonic sequence, immutable answer acceptance, transactional idempotency, serialized terminal transitions, terminal-but-settlement-pending). Issue #6 acceptance check 3: "Model immutable question versions/assignments, attempts/answers, one active account attempt including grace, phase/round version guards and unique answer/settlement keys."

## Global Constraints

- Pins unchanged; credentials/DSNs out of git; harness stays hard-guarded to `sort_tester_unittest_scratch`; rollback isolation (rollback before close; in-transaction assertions); no head-revision pinning in tests; suite runs as the explicit 14-module list (test module count grows as this plan adds files — re-derive from `ls backend/tests` at regression time).
- One active Ranked attempt per account including grace (Decision 6): enforced by a partial unique index on unfinished attempts — `active` and `grace` (and any not-yet-final terminal-pending) states all count as unfinished. The lock releases only at final settlement.
- Question versions are immutable: no UPDATE path; rows are insert-only with a content digest. Assignments freeze their question set at creation (15 rows, `seq` 1–15, unique per assignment; no repeat of a question version within one assignment).
- Answers are immutable once accepted (insert-only; a `(attempt_id, seq)` row can never be replaced or updated); each question row carries exactly one `first_sent_at`/`deadline_at` pair recorded atomically at first send; retries resend the same pair (Q8 owner timing decision).
- Terminal transitions serialize (Q8): an attempt reaches exactly one terminal outcome; repeated terminal requests must be no-ops at the schema level (settlement keyed uniquely per attempt).
- Phase ownership (Decision 12): every attempt carries the season/phase it belongs to; a late Pre-Season result must never touch an official-season row — attempts reference a `seasons` row by FK, and season cutover is once-only (see Task 3).
- Tie-break secrecy and round mechanics (Decisions 9–10) are later feature work (#24); this plan stores only the mode discriminator and round slot so those contracts have a home.
- No employee data, no fictional-data staging change, no Azure work. The 105→119 test suite keeps passing; JS suite untouched (386).

## Review Focus

- Second active attempt for the same account (normal, promotion, or grace overlap) must violate the partial unique index — including the exact case "attempt A in grace while starting attempt B". → pinned by Task 2.
- Answer replacement/immutability: a second insert for the same `(attempt_id, seq)` must fail, and an accepted answer must always carry `accepted_at` (CHECK) — the insert-only contract is pinned by the unique PK plus the accepted-at CHECK. → pinned by Task 2.
- First-send/deadline atomicity: a question row must not exist without both `first_sent_at` and `deadline_at` (CHECK), and must be created exactly once (unique). → pinned by Task 2.
- Duplicate settlement: two settlement rows for one attempt must fail; settlement must reference the attempt's own phase (FK through attempt). → pinned by Task 3.
- Late Pre-Season write after cutover: once a season row is marked closed/cutover, an attempt referencing a DIFFERENT (newer) season cannot be blocked by old-season guards — and an old-season attempt cannot settle into the new season (settlement carries the attempt's season id via FK, not a free-floating value). → pinned by Task 3.

---

### Task 1: Question versions and frozen assignments (migration 0005)

**Files:**
- Create: `backend/migrations/versions/0005_questions_assignments.py`
- Test: `backend/tests/test_db_questions_assignments_schema.py` (new)

**Interfaces:**
- Consumes: identity chain (`accounts.id`), harness (`migrate.connect/execute/fetch_one`, `IntegrityError`).
- Produces:
  - `question_versions(id uuid PK DEFAULT gen_random_uuid(), bank_key varchar(128) NOT NULL, difficulty varchar(8) NOT NULL CHECK (difficulty IN ('easy','medium','hard')), content_sha256 char(64) NOT NULL, UNIQUE (bank_key, content_sha256))` — insert-only; the digest pins the exact reviewed content (content itself stays in `backend/ranked_bank`, not the DB).
  - `assignments(id uuid PK DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, mode varchar(16) NOT NULL CHECK (mode IN ('normal','promotion','tiebreak')), season_id uuid NOT NULL (FK added in Task 3 when `seasons` exists — until then store the uuid WITHOUT FK and note it in a comment), created_at timestamptz NOT NULL DEFAULT now())`.
  - `assignment_questions(assignment_id uuid NOT NULL REFERENCES assignments(id) ON DELETE CASCADE, seq smallint NOT NULL CHECK (seq BETWEEN 1 AND 15), question_version_id uuid NOT NULL REFERENCES question_versions(id), PRIMARY KEY (assignment_id, seq), UNIQUE (assignment_id, question_version_id))` — the no-repeat rule as a unique index; the 15-row 5/5/5 composition is an application invariant (issue #5 owns bank sufficiency).

- [ ] **Step 1: Write the failing test**

Concrete tests (rollback-isolation pattern from the identity plan; helper-created accounts):
- `test_question_version_unique_per_bank_key_and_digest`: same (bank_key, digest) twice → `UniqueViolation`; same bank_key with a different digest coexists (a corrected future version).
- `test_assignment_questions_unique_seq_and_no_repeat`: second row with same `(assignment_id, seq)` → `UniqueViolation`; same `question_version_id` twice in one assignment (different seq) → `UniqueViolation`; a different question at a different seq coexists.
- `test_assignment_seq_bounds`: `seq = 0` and `seq = 16` → `CheckViolation`.
- `test_assignment_cascades_with_account`: delete the account → assignment and its question rows are gone.

- [ ] **Step 2: Run test to verify it fails**

Run (with `SORT_TESTER_TEST_DATABASE_URL` exported): `backend/.venv/bin/python -m unittest backend.tests.test_db_questions_assignments_schema -v`
Expected: FAIL — relations do not exist.

- [ ] **Step 3: Implement `0005_questions_assignments.py`**

Schema per the Interfaces block; downgrade drops `assignment_questions`, `assignments`, `question_versions` in dependency order. The `seasons` FK is deliberately deferred to Task 3 — leave a one-line comment saying so.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0005_questions_assignments.py backend/tests/test_db_questions_assignments_schema.py
git commit -m "feat(db): immutable question versions and frozen assignments"
```

### Task 2: Attempts, active lock, and answers (migration 0006)

**Files:**
- Create: `backend/migrations/versions/0006_attempts_answers.py`
- Test: `backend/tests/test_db_attempts_answers_schema.py` (new)

**Interfaces:**
- Consumes: Task 1 (`assignments.id`, `question_versions.id`).
- Produces:
  - `attempts(id uuid PK DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, assignment_id uuid NOT NULL UNIQUE REFERENCES assignments(id), mode varchar(16) NOT NULL CHECK (mode IN ('normal','promotion','tiebreak')), tiebreak_round smallint NULL CHECK (tiebreak_round IS NULL OR (mode = 'tiebreak' AND tiebreak_round BETWEEN 1 AND 5)), season_id uuid NOT NULL (no FK until Task 3, comment), state varchar(24) NOT NULL CHECK (state IN ('active','grace','terminal_pending','finalized')) CHECK constraints: `grace` requires `grace_deadline_at NOT NULL`, `terminal_pending`/`finalized` require `final_outcome NOT NULL` and `settled_at NOT NULL` for `finalized`, started_at timestamptz NOT NULL DEFAULT now(), grace_deadline_at timestamptz NULL, final_outcome varchar(24) NULL CHECK (final_outcome IN ('completed','quit','disconnect','season_close','launch_reset','outage_void')), settled_at timestamptz NULL)`. The `tiebreak_round` column is the round-version-guard home for #24 (1–5 per Decision Q3; NULL for normal/promotion).
  - **Active-attempt lock**: partial unique index `ON attempts (account_id) WHERE state IN ('active','grace','terminal_pending')` — one unfinished attempt per account across all modes (Decision 6).
  - `attempt_answers(attempt_id uuid NOT NULL REFERENCES attempts(id) ON DELETE CASCADE, seq smallint NOT NULL CHECK (seq BETWEEN 1 AND 15), question_version_id uuid NOT NULL REFERENCES question_versions(id), first_sent_at timestamptz NOT NULL, deadline_at timestamptz NOT NULL CHECK (deadline_at > first_sent_at), answer varchar(16) NULL CHECK (answer IN ('correct','wrong','timeout')) — NULL means sent-but-unanswered at settlement time, outcome varchar(16) NOT NULL CHECK (outcome IN ('correct','wrong','timeout','unsent')), accepted_at timestamptz NULL, PRIMARY KEY (attempt_id, seq))` — insert-only answer acceptance; `accepted_at NOT NULL` when `answer IS NOT NULL` (CHECK).

- [ ] **Step 1: Write the failing test**

Concrete tests:
- `test_one_active_attempt_per_account_including_grace`: insert attempt state='active'; second attempt same account state='active' → `UniqueViolation`; also state='grace' second attempt → `UniqueViolation`; and state='terminal_pending' → `UniqueViolation`; after UPDATE first attempt to 'finalized' (allowed — state transitions are the engine's job; the lock index simply stops counting it), a new 'active' attempt inserts.
- `test_finalized_attempt_allows_new_and_never_reactivates`: setting a 'finalized' attempt back to 'active' is not blocked by SQL (engine concern) — instead assert the lock semantics: two rows can both be 'finalized'; one 'active' + one 'finalized' coexist.
- `test_answer_immutable_unique_key`: second insert same `(attempt_id, seq)` → `UniqueViolation`; an insert with `answer` set but `accepted_at` NULL → `CheckViolation`; `first_sent_at` NULL → `NotNullViolation`; `deadline_at <= first_sent_at` → `CheckViolation`.
- `test_answer_outcome_and_bounds`: outcome outside the enum → `CheckViolation`; seq bounds as in Task 1; `tiebreak_round = 2` with `mode = 'normal'` → `CheckViolation`; `tiebreak_round = 6` with `mode = 'tiebreak'` → `CheckViolation`; `mode = 'tiebreak'` with `tiebreak_round NULL` inserts (round number is engine-assigned at round creation; NULL means not yet slotted).
- `test_attempt_and_answers_cascade_with_account`: account delete removes attempt and its answers.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — relations do not exist.

- [ ] **Step 3: Implement `0006_attempts_answers.py`**

Schema per the Interfaces block. The state CHECKs carry the terminal-serialization contract: `finalized` requires both `final_outcome` and `settled_at`, so a finalized attempt always records its single outcome. Downgrade drops `attempt_answers` then `attempts`.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0006_attempts_answers.py backend/tests/test_db_attempts_answers_schema.py
git commit -m "feat(db): attempts with active lock and immutable answers"
```

### Task 3: Seasons, phase guards, and settlement keys (migration 0007)

**Files:**
- Create: `backend/migrations/versions/0007_seasons_settlements.py` (includes the ALTER TABLE statements adding the deferred FKs — the earlier migration files are NOT edited; 0007 owns the constraints)
- Test: `backend/tests/test_db_seasons_settlements_schema.py` (new)

**Interfaces:**
- Consumes: Tasks 1–2.
- Produces:
  - `seasons(id uuid PK DEFAULT gen_random_uuid(), phase varchar(16) NOT NULL CHECK (phase IN ('pre_season','official')), label varchar(64) NOT NULL UNIQUE, opened_at timestamptz NOT NULL DEFAULT now(), closed_at timestamptz NULL, CHECK (closed_at IS NULL OR closed_at >= opened_at))` — one row per Pre-Season/official season instance; cutover happens by opening the next row, never by mutating history.
  - `settlements(attempt_id uuid PRIMARY KEY REFERENCES attempts(id) ON DELETE CASCADE, season_id uuid NOT NULL REFERENCES seasons(id), raw_score smallint NOT NULL CHECK (raw_score BETWEEN -150 AND 300), adjustment smallint NOT NULL, final_outcome varchar(24) NOT NULL CHECK (final_outcome IN ('completed','quit','disconnect','season_close','launch_reset','outage_void')), settled_at timestamptz NOT NULL DEFAULT now())` — PK on `attempt_id` IS the unique settlement key (Decision: points applied at most once; repeated terminal requests find the existing row). `season_id` additionally CHECKs equal to the attempt's season at insert time via the application; the structural guard is the FK plus the attempt's own season reference.
  - FK additions: `assignments.season_id` and `attempts.season_id` gain `REFERENCES seasons(id)` (raw SQL `ALTER TABLE ... ADD CONSTRAINT` in the migration, since the columns already exist).
- Late-Pre-Season guard: no trigger (engine work); the structural pieces are (a) settlement's `season_id` FK, (b) the attempt's frozen `season_id`, (c) `seasons.closed_at` being queryable. A migration comment states that blocking post-close writes is engine transaction logic (#8/#23), not schema.

- [ ] **Step 1: Write the failing test**

Concrete tests:
- `test_settlement_unique_per_attempt`: second settlement row for the same attempt → `UniqueViolation` (PK violation) — duplicate terminal request is a no-op.
- `test_settlement_raw_score_bounds_and_outcome_enum`: raw_score -151 → `CheckViolation`; +301 → `CheckViolation`; bad outcome → `CheckViolation`.
- `test_season_phase_and_close_ordering`: bad phase → `CheckViolation`; `closed_at < opened_at` → `CheckViolation`; duplicate label → `UniqueViolation`.
- `test_attempts_and_assignments_now_reference_seasons`: inserting an attempt with a `season_id` value that has no `seasons` row → `ForeignKeyViolation` (proves the Task 3 FK additions landed on both tables).
- `test_settlement_cascade_and_season_immutable_history`: settlement cascades with its attempt; a second season row (cutover) coexists with the closed first — history is never mutated.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — `seasons`/`settlements` do not exist and the FK additions are absent.

- [ ] **Step 3: Implement `0007_seasons_settlements.py` + FK alterations**

Create `seasons` and `settlements`, then `ALTER TABLE assignments/attempts ADD CONSTRAINT ... FOREIGN KEY (season_id) REFERENCES seasons(id)`. Downgrade drops the constraints first, then the tables.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0007_seasons_settlements.py backend/tests/test_db_seasons_settlements_schema.py
git commit -m "feat(db): seasons, phase guards, and unique settlement keys"
```

### Task 4: Full regression, docs record, and issue evidence

**Files:**
- Modify: `backend/README.md` (extend the migration-chain paragraph: 0005–0007, one-line constraint summary each — no DSNs)
- Test: none new

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: verified regression evidence recorded on issue #6 by the controller.

- [ ] **Step 1: Run the full backend suite with the live server**

Module list re-derived from `ls backend/tests` (17 modules expected: 14 + 3 new). Record EXACT observed count (119 + 14 new = 133 expected — assert observed).

- [ ] **Step 2: Run without the env var and with a malformed value**

Expect clean skips (16 + 14 = 30 skipped without DB; malformed → controlled skips, no tracebacks). Record observed numbers.

- [ ] **Step 3: Run the JavaScript suite**

Expect 386 pass, 0 fail (unchanged).

- [ ] **Step 4: Update README and commit**

`docs(db): record attempts/answers/settlement schema in the migration chain`. Do NOT push (controller handles integration).

- [ ] **Step 5: Controller posts evidence on issue #6**

---

## Out of scope (later plans)

- Balance/adjustment atomicity, one-balance ledger, outbox contract (check 4; #9/#27).
- Deletion/redaction cascade behavior for attempt data (check 5; #10) — structural cascades to accounts already exist.
- Answer/deadline engine logic, heartbeat/loss detection, outage classification, tie-break round mechanics (#8/#23/#24).
- Scoring value tables (points per difficulty stay settled rules in the decision record, not DB rows).
- Migration of existing data — all tables are new; no data backfill.
