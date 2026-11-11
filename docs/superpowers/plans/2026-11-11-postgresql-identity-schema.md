# PostgreSQL Identity Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model the identity layer of issue #6's second acceptance check — accounts (stable UUID, case-insensitive unique username, permanent unique tag), optional private verified emails with launch-reminder consent, owner-only participant links, and the minimal season-ineligibility marker — as migration `0002` with constraint-proving tests.

**Architecture:** Schema-only work in the pipeline proven by `0001_tooling_probe` (psycopg + Alembic). No ORM, no API, no auth: those are issues #7/#10. Each table lands as its own revision so a reviewer can approve table-by-table. All behavior evidence is database constraints exercised through the test harness built in the tooling plan.

**Tech Stack:** PostgreSQL 18, psycopg 3.3.8, Alembic 1.20.1, Python 3.14 venv — unchanged pins.

**Spec:** `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` (Decision 14 — identity/recovery/deletion/privacy; Q5 — prize eligibility marker) and `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md` (Q10 defaults — username/tag/email/marker paragraphs). Issue #6 acceptance check 2: "Model stable IDs, normalized unique usernames, permanent tags, verified-email/consent contracts, owner-scoped participant links and minimal eligibility marker boundaries."

## Global Constraints

- Pins unchanged: `psycopg[binary]==3.3.8`, `alembic==1.20.1`; Python 3.14 venv.
- Credentials/DSNs stay out of git; the test harness remains hard-guarded to `sort_tester_unittest_scratch`.
- Username: 3–24 ASCII letters, digits or underscore (proposal format); case-insensitive uniqueness; internal UUID primary key; six-character uppercase alphanumeric tag, unique, permanent across rename. Tag generation is NOT in this plan (application-layer concern, #7); the migration supplies uniqueness only.
- Email: optional, private, never on profiles/leaderboards; uniqueness is per normalized address (lowercase only — dots/+aliases are distinct, never equated); only one active verified recovery email per account and per address; old verified address stays until a new one is verified; email verification never grants consent.
- Reminder consent (Decision 15): separate field, initially unchecked; delivery requires verified email AND active opt-in; withdrawal removes consent; consent does not carry into future seasons (season scoping column).
- Participant link: owner-only trusted roster reference established before any request; unique per account; erased when the account is deleted (FK cascade).
- Season marker (Q10/Q5): exactly four fields — owner-recognizable private roster reference, season reference, ineligible state, expiry at global prize finalization (nullable, cleared by deletion of the row at finalization — no tombstone). NO account FK: the marker must survive account deletion. No username/email/tag/score/credential columns.
- Deletion boundary respected structurally: account-owned rows (emails, links, consent) cascade on account delete; the marker does not.
- Database-dependent tests skip cleanly without `SORT_TESTER_TEST_DATABASE_URL` (harness pattern from the tooling plan).
- The full suite (105 backend tests baseline) keeps passing; JS suite untouched (386).

## Review Focus

- Case-insensitive username collisions: `Alice_1` and `alice_1` must violate the unique constraint (normalize via a lowercase column, not a per-connection `citext` dependency). → pinned by Task 1.
- Alias-equivalence leaks: `a.b@x.com`, `ab@x.com`, and `a+b@x.com` are three distinct addresses (no dot/plus folding). → pinned by Task 2.
- Consent without verified email must be structurally rejectable: the consent fields require the referenced email row to be in a verified state — modeled so a NOT-verified row cannot carry active consent (CHECK on state). → pinned by Task 2.
- Marker survival: deleting an account must NOT delete its season marker rows (no FK), while deleting it MUST remove emails/links/consent (cascade). → pinned by Task 3.
- Marker minimality: the marker table must contain no column that can hold a username/email/tag/credential — enforced by the migration contract test asserting the exact column set. → pinned by Task 3.

---

### Task 1: Accounts table (migration 0002)

**Files:**
- Create: `backend/migrations/versions/0002_accounts.py`
- Test: `backend/tests/test_db_accounts_schema.py` (new)

**Interfaces:**
- Consumes: Task-1-of-tooling-plan harness (`backend.db.migrate`, `backend.db.settings`).
- Produces: table `accounts` — `id uuid PRIMARY KEY DEFAULT gen_random_uuid()`, `username varchar(24) NOT NULL` (check: `^[A-Za-z0-9_]{3,24}$` via a CHECK constraint), `username_lower varchar(24) NOT NULL UNIQUE`, `tag varchar(6) NOT NULL UNIQUE` (check `^[A-Z0-9]{6}$`), `created_at timestamptz NOT NULL DEFAULT now()`, `deleted_at timestamptz NULL` (NULL = live; no tombstone rows — deletion is physical later, this column only stages the pending window; if the owner prefers pure physical deletion it stays NULL always and is removed in the deletion task). Downgrade drops the table. Also adds to `backend/db/migrate.py`: `connect(conninfo)` (psycopg connection), `execute(conn, sql, params=None)` (execute WITHOUT committing — tests rely on rollback isolation; migration/DDL paths manage their own transactions), `fetch_one(conn, sql, params=None)` (dict row or None), `IntegrityError = psycopg.errors.IntegrityError` re-export.

- [ ] **Step 1: Write the failing test**

```python
"""Accounts schema contract: stable id, CI username, permanent tag."""
import re
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AccountsSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        cls.admin = settings.admin_url()
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        # rollback at teardown keeps tests isolated (no committed rows leak between tests)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.conn.close)

    def test_case_insensitive_username_collision_rejected(self):
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('Alice_1', 'alice_1', 'AAAAAA')")
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('ALICE_1', 'ALICE_1', 'BBBBBB')")

    def test_username_format_check(self):
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('ab', 'ab', 'CCCCCC')")  # too short
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('bad-name!', 'badname!!', 'DDDDDD')")  # bad chars

    def test_tag_format_and_uniqueness(self):
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_a', 'user_a', 'abc123')")  # lowercase tag
        migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_a', 'user_a', 'ABC123')")
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_b', 'user_b', 'ABC123')")

    def test_default_uuid_and_timestamps(self):
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES ('user_c', 'user_c', 'DEF456') RETURNING id, created_at, deleted_at",
        )
        self.assertIsNotNone(row["id"])
        self.assertIsNone(row["deleted_at"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SORT_TESTER_TEST_DATABASE_URL=… backend/.venv/bin/python -m unittest backend.tests.test_db_accounts_schema -v`
Expected: FAIL/ERROR — `migrate.connect`/`migrate.execute`/`migrate.fetch_one`/`migrate.IntegrityError` do not exist yet (or the relation does not exist).

- [ ] **Step 3: Implement**

Add to `backend/db/migrate.py`: `connect(conninfo)` (psycopg connection), `execute(conn, sql, params=None)` (executes WITHOUT committing — isolation comes from the tests' rollback cleanup), `fetch_one(conn, sql, params=None)` (dict row or None), `IntegrityError = psycopg.errors.IntegrityError` re-export. Create `0002_accounts.py` implementing the schema in the Interfaces block, with a matching downgrade. Revision chain: `0001` → `0002` (down_revision set).

- [ ] **Step 4: Run test to verify it passes**

Run: the focused test command.
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/migrate.py backend/migrations/versions/0002_accounts.py backend/tests/test_db_accounts_schema.py
git commit -m "feat(db): accounts table with CI username and permanent tag"
```

### Task 2: Emails and reminder consent (migration 0003)

**Files:**
- Create: `backend/migrations/versions/0003_emails.py`
- Test: `backend/tests/test_db_emails_schema.py` (new)

**Interfaces:**
- Consumes: Task 1 (`accounts.id`, `migrate.connect/execute/fetch_one`, harness).
- Produces: table `emails` — `id uuid PK DEFAULT gen_random_uuid()`, `account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE`, `address varchar(254) NOT NULL`, `address_normalized varchar(254) NOT NULL` (lowercase; CHECK that it equals lower(address)), `state varchar(16) NOT NULL CHECK (state IN ('pending','verified','retired'))`, `reminder_opt_in boolean NOT NULL DEFAULT false`, `reminder_opt_in_at timestamptz NULL`, `consent_season varchar(64) NULL` (NULL = not season-scoped yet; consent never auto-carries), verified timestamps `verified_at timestamptz NULL`. Uniqueness: one `pending`+`verified` (i.e. non-retired) row per `address_normalized` — partial unique index `WHERE state <> 'retired'`; one non-retired row per `account_id` — partial unique index. Consent gate: CHECK `(reminder_opt_in = false OR (state = 'verified' AND reminder_opt_in_at IS NOT NULL))`. Downgrade drops the table.

- [ ] **Step 1: Write the failing test**

```python
"""Emails schema contract: per-address uniqueness without alias folding, consent gate."""
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class EmailsSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        migrate.recreate_scratch_database(settings.admin_url(), settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        self.account_id = self._make_account("email_user")

    def _make_account(self, name):
        conn = migrate.connect(self.conninfo)
        try:
            row = migrate.fetch_one(
                conn,
                "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
                (name, name, "AAAAAA"),
            )
            return row["id"]
        finally:
            conn.close()

    def _insert_email(self, account_id, address, normalized, state, opt_in=False):
        return migrate.execute(
            self.conn,  # set in test body; see Step 1 wiring note below
            "INSERT INTO emails (account_id, address, address_normalized, state, reminder_opt_in) VALUES (%s, %s, %s, %s, %s)",
            (account_id, address, normalized, state, opt_in),
        )

    # tests (each opens its own connection in setUp via migrate.connect and rolls back):
    # test_alias_addresses_are_distinct: 'a.b@x.com', 'ab@x.com', 'a+b@x.com' all insert for the SAME account? No —
    #   one non-retired row per account, so insert two accounts and one address each; then insert a.b@X.COM on a third
    #   account and assert it collides on address_normalized with a.b@x.com (case folded) but NOT with ab@x.com.
    # test_one_active_email_per_account: second non-retired email for the same account raises IntegrityError.
    # test_retired_address_reusable: after setting state='retired', the same normalized address can be re-verified on another account.
    # test_consent_requires_verified: opt_in=true on a pending row raises IntegrityError (CHECK); opt_in=true on verified passes.
```

Wiring note for the implementer: the snippet above is the contract sketch, not final code — write the four tests concretely, each with its own connection and rollback-based isolation (`self.conn = migrate.connect(...)` in `setUp`, `self.addCleanup(self.conn.rollback)`; the harness executes inside that transaction so no committed state leaks between tests). All inserts in this file use rollback isolation; only schema changes are committed by the migration.

- [ ] **Step 2: Run test to verify it fails**

Run: focused command. Expected: FAIL — the `emails` relation does not exist.

- [ ] **Step 3: Implement `0003_emails.py`**

Schema per the Interfaces block. The two partial unique indexes and the consent CHECK carry the whole contract — no triggers. Downgrade drops indexes with the table.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0003_emails.py backend/tests/test_db_emails_schema.py
git commit -m "feat(db): emails table with alias-preserving uniqueness and consent gate"
```

### Task 3: Participant links and season marker (migration 0004)

**Files:**
- Create: `backend/migrations/versions/0004_links_and_marker.py`
- Test: `backend/tests/test_db_links_marker_schema.py` (new)

**Interfaces:**
- Consumes: Tasks 1–2 (`accounts.id`, harness).
- Produces: table `participant_links` — `account_id uuid NOT NULL UNIQUE REFERENCES accounts(id) ON DELETE CASCADE`, `roster_reference varchar(128) NOT NULL` (the owner-recognizable private roster reference; opaque to the schema), `established_at timestamptz NOT NULL DEFAULT now()`. Table `season_markers` — `id uuid PK DEFAULT gen_random_uuid()`, `roster_reference varchar(128) NOT NULL`, `season varchar(64) NOT NULL`, `ineligible boolean NOT NULL`, `UNIQUE (roster_reference, season)`. NO account FK on `season_markers`. Exactly these columns on `season_markers` — the contract test asserts the full column set (`id`, `roster_reference`, `season`, `ineligible`) and nothing else. Downgrade drops both tables.

- [ ] **Step 1: Write the failing tests**

Concrete tests to write (same harness and rollback-isolation pattern as Task 2):
- `test_link_is_one_per_account_and_owner_only`: one link per account (second insert violates the unique); a second account can hold a different link.
- `test_link_cascades_with_account`: delete the account row; the link row is gone.
- `test_marker_survives_account_deletion`: insert an account, a link, and a marker sharing the same `roster_reference`; delete the account; the marker row must still exist (this is the Q10 structural boundary).
- `test_marker_column_set_is_minimal`: query `information_schema.columns` for `season_markers`; the returned column names must equal exactly `["id", "roster_reference", "season", "ineligible"]` (order-insensitive) — no username/email/tag/credential-capable column exists.
- `test_marker_unique_per_reference_and_season`: second marker with the same (roster_reference, season) raises IntegrityError; a different season is allowed.

- [ ] **Step 2: Run test to verify it fails**

Expected: FAIL — relations do not exist.

- [ ] **Step 3: Implement `0004_links_and_marker.py`**

Schema per the Interfaces block. `season_markers` has deliberately NO foreign key — write a one-line migration comment stating that this is the Q10 deletion-survival requirement, so a future reader does not "fix" it.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0004_links_and_marker.py backend/tests/test_db_links_marker_schema.py
git commit -m "feat(db): participant links and minimal season-ineligibility marker"
```

### Task 4: Full regression, docs record, and issue evidence

**Files:**
- Modify: `backend/README.md` (one short paragraph under the existing Database tooling section: the migration chain now covers accounts/emails/links/marker and the constraint model summary — no DSNs, no columns documented with real data examples)
- Test: none new

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: verified regression evidence recorded on issue #6.

- [ ] **Step 1: Run the full backend suite with the live server**

Run: `SORT_TESTER_TEST_DATABASE_URL=… backend/.venv/bin/python -m unittest discover -s backend/tests`
Expected: PASS — assert the exact observed count (105 previous + 13 new = 118 expected; record the observed number) before claiming it.

- [ ] **Step 2: Run the suite without the env var**

Expected: all database tests skip cleanly (12 skip lines), controlled, no tracebacks. Also run the malformed-URL regression from the tooling plan and record the controlled-skip output.

- [ ] **Step 3: Run the JavaScript suite**

Run: `node --test tests/*.test.mjs` — expect 386 pass, 0 fail (unchanged).

- [ ] **Step 4: Update README and commit**

One short paragraph; commit message: `docs(db): record identity schema in the migration chain`. Do NOT push (controller/owner handles integration).

- [ ] **Step 5: Post evidence on issue #6** (controller task, not the implementer's)

Comment recording: migration chain 0001–0004 with the constraint evidence per table (CI username, tag uniqueness, alias-preserving email uniqueness, consent gate, link cascade, marker survival and minimality), regression counts, and what remains open on checks 3–6.

---

## Out of scope (later plans on #6)

- Attempts/answers/settlement keys, balance atomicity, outbox (checks 3–4, issues #4/#8/#9/#12).
- Deletion/redaction behavior and purge-safe backup contract (check 5, #10/#7/#13) — this plan only fixes the structural FK/no-FK boundary.
- Tag generation, username validation endpoints, auth/sessions/MFA (#7/#10), any application code.
- Migration 0002's `deleted_at` column usage: deletion behavior itself belongs to check 5; the column is inert until then.
