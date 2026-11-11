# PostgreSQL Balance and Outbox Schema Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Model issue #6's fourth acceptance check — a single balance ledger per account (raw performance, applied adjustment, before/after points/rank snapshots) and a durable outbox extension contract — as migrations 0008 and 0009 with constraint-proving tests.

**Architecture:** Schema-only continuation of the 0001–0007 chain. The database stores one balance row per account and an immutable history row per settlement; the engine (later issues) owns the cap/promotion math and the transaction that updates balance + history atomically. The outbox is a generic, feature-independent table with a unique message key, payload, destination/consent versions, attempt counter, and worker lease — no FKs to later feature tables.

**Tech Stack:** PostgreSQL 18, psycopg 3.3.8, Alembic 1.20.1, Python 3.14 venv — unchanged pins.

**Spec:** `docs/superpowers/specs/2026-11-07-ranked-decision-record.md` (Decision 1 one capped balance and Challenger; Decision 4 promotion/demotion scoring) and `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md` (Q8 terminal-but-settlement-pending / account admission lock; Q11 durable outbox with logical message key, destination version, consent version, attempt counter, bounded worker lease). Issue #6 acceptance check 4: "Keep raw performance, applied adjustment and before/after balance/rank atomic; one balance only. Add durable outbox extension contract without cyclic later-feature dependencies."

## Global Constraints

- Pins unchanged; credentials/DSNs out of git; harness hard-guarded to `sort_tester_unittest_scratch`; rollback isolation (rollback before close); no head-revision pinning; explicit module list for suite (re-derive from `ls backend/tests`).
- One balance row per account only (`balances.account_id` PK). No separate seasonal balance; the decision record rejects overflow/separate balances.
- Balance history preserves raw score and applied adjustment separately, plus points/rank snapshots before and after — it is not a second balance.
- Settlement-to-balance update must be atomic: the schema supports the engine transaction; tests simulate commit visibility and rollback no-trace.
- Outbox has no foreign keys to `emails`, `accounts`, or any later feature table; payload is generic JSONB so email/launch-reminder/whatever workers can use it without cyclic schema dependencies.
- Badge values are the five approved badges: `Iron`, `Bronze`, `Silver`, `Gold`, `Challenger`. The DB stores the snapshot; the engine computes the badge from points.
- Database-dependent tests skip cleanly without `SORT_TESTER_TEST_DATABASE_URL`. Existing 139 tests keep passing; JS suite unchanged (386).

## Review Focus

- Two balance rows for one account → must violate the PK. → pinned by Task 1.
- Two history rows for one settlement → must violate the unique constraint. → pinned by Task 1.
- A balance update without a matching history row (or vice versa) after a commit must not happen; rollback must leave no trace. → pinned by Task 2.
- A second settlement for the same account must update the balance and create a second history row, not overwrite the first. → pinned by Task 2.
- Outbox duplicate message keys → must violate uniqueness. → pinned by Task 3.
- Outbox worker lease/attempt-count semantics must be updatable without touching payload. → pinned by Task 3.

---

### Task 1: Balance ledger (migration 0008)

**Files:**
- Create: `backend/migrations/versions/0008_balance_ledger.py`
- Test: `backend/tests/test_db_balance_ledger_schema.py`

**Interfaces:**
- Consumes: identity chain (`accounts.id`) and settlements chain (`settlements.attempt_id` PK).
- Produces:
  - `balances(account_id uuid PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE, current_points smallint NOT NULL DEFAULT 0, updated_at timestamptz NOT NULL DEFAULT now())`.
  - `balance_history(id uuid PK DEFAULT gen_random_uuid(), account_id uuid NOT NULL REFERENCES accounts(id) ON DELETE CASCADE, settlement_id uuid NOT NULL UNIQUE REFERENCES settlements(attempt_id) ON DELETE CASCADE, raw_score smallint NOT NULL, adjustment smallint NOT NULL, points_before smallint NOT NULL, points_after smallint NOT NULL, badge_before varchar(16) NOT NULL CHECK (badge_before IN ('Iron','Bronze','Silver','Gold','Challenger')), badge_after varchar(16) NOT NULL CHECK (badge_after IN ('Iron','Bronze','Silver','Gold','Challenger')), recorded_at timestamptz NOT NULL DEFAULT now())`.

- [ ] **Step 1: Write the failing test**

Concrete tests (rollback isolation; helper functions `_make_account`, `_make_season`, `_make_assignment`, `_make_attempt`, `_make_settlement` create prerequisite rows). The implementer may adapt helper patterns from existing schema test modules:

```python
@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class BalanceLedgerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        migrate.recreate_scratch_database(settings.admin_url(), settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.conn.close)

    def test_one_balance_per_account(self):
        account_id = self._make_account()
        self._make_balance(account_id, current_points=0)
        with self.assertRaises(migrate.IntegrityError):
            self._make_balance(account_id, current_points=100)

    def test_history_unique_per_settlement(self):
        settlement_id = self._make_settlement()
        self._make_history(settlement_id, raw_score=100, adjustment=-10,
                           points_before=500, points_after=590,
                           badge_before='Bronze', badge_after='Bronze')
        with self.assertRaises(migrate.IntegrityError):
            self._make_history(settlement_id, raw_score=0, adjustment=0,
                               points_before=0, points_after=0,
                               badge_before='Iron', badge_after='Iron')

    def test_history_preserves_raw_adjustment_before_after(self):
        row = self._make_history(raw_score=100, adjustment=-10,
                                 points_before=500, points_after=590,
                                 badge_before='Bronze', badge_after='Bronze')
        fetched = migrate.fetch_one(
            self.conn, "SELECT * FROM balance_history WHERE id = %s", (row['id'],)
        )
        self.assertEqual(fetched['raw_score'], 100)
        self.assertEqual(fetched['adjustment'], -10)
        self.assertEqual(fetched['points_before'], 500)
        self.assertEqual(fetched['points_after'], 590)
        self.assertEqual(fetched['badge_before'], 'Bronze')
        self.assertEqual(fetched['badge_after'], 'Bronze')

    def test_cascade_deletes_balance_and_history(self):
        account_id = self._make_account()
        self._make_balance(account_id, current_points=0)
        settlement_id = self._make_settlement(account_id=account_id)
        self._make_history(settlement_id)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM balances WHERE account_id = %s", (account_id,))
        )
        self.assertIsNone(
            migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `SORT_TESTER_TEST_DATABASE_URL=… backend/.venv/bin/python -m unittest backend.tests.test_db_balance_ledger_schema -v`
Expected: FAIL/ERROR — relations do not exist.

- [ ] **Step 3: Implement `0008_balance_ledger.py`**

Schema per Interfaces block; `down_revision = "0007"`; downgrade drops `balance_history` then `balances`.

- [ ] **Step 4: Run test to verify it passes**

Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0008_balance_ledger.py backend/tests/test_db_balance_ledger_schema.py
git commit -m "feat(db): balance ledger with one row per account and immutable history"
```

### Task 2: Atomicity simulation tests

**Files:**
- Create: `backend/tests/test_db_balance_atomicity.py`

**Interfaces:**
- Consumes: Task 1 tables and helpers.
- Produces: three tests proving commit visibility, rollback no-trace, and multi-settlement accumulation.

- [ ] **Step 1: Write the failing test**

Use a dedicated connection for the transaction under test (commit or rollback explicitly), then verify with `self.conn`:

```python
@unittest.skipUnless(settings.environment_has_test_url(), "...")
class BalanceAtomicityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        migrate.recreate_scratch_database(settings.admin_url(), settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.conn.close)
        self._counter = 0

    def _unique_tag(self):
        self._counter += 1
        return f"BAT{self._counter:03d}"

    def test_committed_update_visible(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=0)
        settlement_id = self._make_settlement(account_id)
        tx = migrate.connect(self.conninfo)
        try:
            migrate.execute(tx, """
                UPDATE balances SET current_points = 590, updated_at = now()
                WHERE account_id = %s
            """, (account_id,))
            migrate.execute(tx, """
                INSERT INTO balance_history
                (account_id, settlement_id, raw_score, adjustment, points_before, points_after, badge_before, badge_after)
                VALUES (%s, %s, 100, -10, 500, 590, 'Bronze', 'Bronze')
            """, (account_id, settlement_id))
            tx.commit()
        finally:
            tx.close()
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 590)
        hist = migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        self.assertIsNotNone(hist)

    def test_rollback_leaves_no_trace(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=100)
        settlement_id = self._make_settlement(account_id)
        tx = migrate.connect(self.conninfo)
        try:
            migrate.execute(tx, "UPDATE balances SET current_points = 999 WHERE account_id = %s", (account_id,))
            migrate.execute(tx, """
                INSERT INTO balance_history
                (account_id, settlement_id, raw_score, adjustment, points_before, points_after, badge_before, badge_after)
                VALUES (%s, %s, 0, 0, 100, 999, 'Iron', 'Iron')
            """, (account_id, settlement_id))
            tx.rollback()
        finally:
            tx.close()
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 100)
        hist = migrate.fetch_one(self.conn, "SELECT 1 FROM balance_history WHERE settlement_id = %s", (settlement_id,))
        self.assertIsNone(hist)

    def test_multiple_settlements_accumulate(self):
        account_id = self._make_account(tag=self._unique_tag())
        self._make_balance(account_id, current_points=0)
        s1 = self._make_settlement(account_id)
        self._apply_settlement(account_id, s1, raw_score=100, adjustment=0, points_before=0, points_after=100)
        s2 = self._make_settlement(account_id)
        self._apply_settlement(account_id, s2, raw_score=50, adjustment=0, points_before=100, points_after=150)
        count = migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM balance_history WHERE account_id = %s", (account_id,))
        self.assertEqual(count['n'], 2)
        bal = migrate.fetch_one(self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,))
        self.assertEqual(bal['current_points'], 150)
```

- [ ] **Step 2: Run to verify it fails** — FAIL.
- [ ] **Step 3: Implement helpers** (copy/adapt from previous modules; ensure unique tags/seasons/assignments/attempts per call; `_make_settlement` can create the attempt in `finalized` state to avoid the active-attempt lock).
- [ ] **Step 4: Run to verify it passes** — PASS (3 tests).
- [ ] **Step 5: Commit**

```bash
git add backend/tests/test_db_balance_atomicity.py
git commit -m "test(db): balance update commit/rollback and multi-settlement accumulation"
```

### Task 3: Outbox (migration 0009)

**Files:**
- Create: `backend/migrations/versions/0009_outbox.py`
- Test: `backend/tests/test_db_outbox_schema.py`

**Interfaces:**
- Consumes: identity tooling harness.
- Produces:
  - `outbox(id uuid PK DEFAULT gen_random_uuid(), message_key varchar(128) NOT NULL UNIQUE, payload jsonb NOT NULL, recipient_destination_version varchar(64) NOT NULL, consent_version varchar(64) NULL, attempt_count smallint NOT NULL DEFAULT 0 CHECK (attempt_count >= 0), worker_lease_until timestamptz NULL, created_at timestamptz NOT NULL DEFAULT now())`.
  - No foreign keys to any feature table. A migration comment states this is intentional to avoid cyclic later-feature dependencies.

- [ ] **Step 1: Write the failing test**

```python
import json
import unittest

from backend.db import migrate, settings


@unittest.skipUnless(settings.environment_has_test_url(), "...")
class OutboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.conninfo = settings.test_database_url()
        migrate.recreate_scratch_database(settings.admin_url(), settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.conninfo)

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.rollback)
        self.addCleanup(self.conn.close)

    def test_message_key_unique(self):
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k1', '{}'::jsonb, 'v1')
        """)
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, """
                INSERT INTO outbox (message_key, payload, recipient_destination_version)
                VALUES ('k1', '{}'::jsonb, 'v1')
            """)

    def test_payload_jsonb(self):
        payload = {"to": "a@example.com", "subject": "launch"}
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k2', %s::jsonb, 'v1')
        """, (json.dumps(payload),))
        row = migrate.fetch_one(self.conn, "SELECT payload FROM outbox WHERE message_key = 'k2'")
        self.assertEqual(row['payload'], payload)

    def test_attempt_count_and_lease_update(self):
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k3', '{}'::jsonb, 'v1')
        """)
        migrate.execute(self.conn, """
            UPDATE outbox
            SET attempt_count = 1, worker_lease_until = now() + interval '5 minutes'
            WHERE message_key = 'k3'
        """)
        row = migrate.fetch_one(self.conn, "SELECT attempt_count, worker_lease_until FROM outbox WHERE message_key = 'k3'")
        self.assertEqual(row['attempt_count'], 1)
        self.assertIsNotNone(row['worker_lease_until'])

    def test_no_feature_dependencies(self):
        row = migrate.fetch_one(self.conn, """
            SELECT COUNT(*) AS n FROM information_schema.table_constraints
            WHERE table_name = 'outbox' AND constraint_type = 'FOREIGN KEY'
        """)
        self.assertEqual(row['n'], 0)
```

- [ ] **Step 2: Run to verify it fails** — FAIL.
- [ ] **Step 3: Implement `0009_outbox.py`** — schema per Interfaces; `down_revision = "0008"`; downgrade drops `outbox`.
- [ ] **Step 4: Run to verify it passes** — PASS (4 tests).
- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0009_outbox.py backend/tests/test_db_outbox_schema.py
git commit -m "feat(db): durable outbox extension contract"
```

### Task 4: Regression, docs, and issue evidence

**Files:**
- Modify: `backend/README.md`
- Test: none new

**Interfaces:**
- Consumes: Tasks 1–3.
- Produces: verified regression evidence on issue #6.

- [ ] **Step 1: Run full backend suite with live server**

Explicit module list (18 modules now). Record EXACT observed count (139 + 11 = 150 expected; assert observed).

- [ ] **Step 2: Run without env var and malformed value**

Expect clean skips, no tracebacks. Record observed numbers.

- [ ] **Step 3: Run JS suite**

Expect 386 pass, 0 fail.

- [ ] **Step 4: Update README**

Extend migration chain to 0008–0009 with one-sentence constraint summary. No DSNs.

- [ ] **Step 5: Commit**

```bash
git add backend/README.md
git commit -m "docs(db): record balance ledger and outbox schema"
```

- [ ] **Step 6: Controller posts evidence on issue #6**

---

## Out of scope

- Cap/promotion arithmetic and badge computation (engine, #4/#9).
- The engine transaction that actually updates balance + history together (#8/#23).
- Outbox worker/dispatcher and email/provider adapters (#27).
- Deletion/redaction of balance/history (check 5).
- Any application code.
