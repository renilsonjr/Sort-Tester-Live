# PostgreSQL Tooling Foundations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Choose, pin and test the PostgreSQL server major, Linux-compatible driver and migration tooling, with a probe migration proving clean migrate/rollback and persistence across restart — the first acceptance check of issue #6, without building the ranked schema.

**Architecture:** A `backend/db/` package exposes the engine/connection contract; Alembic owns schema migrations under `backend/migrations/`; a single environment variable (`SORT_TESTER_DATABASE_URL`) carries all credentials, never the repository. One trivial probe migration exercises the full migrate → restart → rollback cycle so later schema tasks inherit a tested pipeline.

**Tech Stack:** PostgreSQL 18, `psycopg[binary]==3.3.8` (cp314 wheels exist for manylinux x86_64, Windows amd64, macOS), `alembic==1.20.1` (pure Python), Python 3.14 venv.

**Spec:** `docs/superpowers/specs/2026-11-07-ranked-security-operations-design.md` (Q12 hosting/operations: "Select a supported PostgreSQL major and compatible Windows driver/migration tools in #6… Validate migration/rollback and backup restore before real user data") and issue #6 acceptance check 1: "Choose supported PostgreSQL, a compatible Linux driver and migration tools… pin/test during implementation. Keep credentials/database private, separate dev/test/pilot."

## Global Constraints

- Python 3.14.10 target; all new pins must have cp314 wheels or be pure Python.
- No production database is provisioned. No employee data, no fictional-data staging change. This plan touches no Azure resources.
- Credentials live only in environment variables; nothing connection-related enters git (no hostnames, no passwords, no DSNs beyond placeholder docs).
- Dev, test and pilot stay separate: tests use a dedicated scratch database name, never the dev database.
- Windows compatibility retained as applicable: only wheels/pure-Python deps; no POSIX-only paths or commands in `backend/`.
- Existing 83 backend tests and 386 JS tests must keep passing untouched.
- New database-dependent tests are skipped with a clear message when `SORT_TESTER_TEST_DATABASE_URL` is unset, so CI and Windows environments without a server still pass.

## Review Focus

- Missing or malformed `SORT_TESTER_TEST_DATABASE_URL` (e.g. no scheme, non-postgres scheme): the harness must fail/skip with an explicit message naming the variable, never a raw traceback mid-test. → pinned by Task 4's malformed-URL test.
- A test URL accidentally pointing at the dev or pilot database: the harness refuses any URL whose database name is not the reserved test database name `sort_tester_unittest_scratch`. → pinned by Task 4.
- Stale scratch database from an interrupted previous run: the harness drops and recreates the scratch database at setup, so a leftover state cannot leak between runs. → pinned by Task 4.
- A second migration run over an already-migrated database: Alembic's version table must make re-runs no-ops, not duplicate objects or errors. → pinned by Task 4.
- Rerun after a real restart of the server process: committed probe rows must still be there (persistence, not in-memory). → pinned by Task 3.

---

### Task 1: Pin the database dependencies

**Files:**
- Modify: `backend/requirements.txt` (append pins; update header comment)
- Test: `backend/tests/test_db_tooling_pins.py` (new)

**Interfaces:**
- Consumes: nothing.
- Produces: `psycopg[binary]==3.3.8` and `alembic==1.20.1` importable in the venv; later tasks rely on `import psycopg` and `import alembic` succeeding.

- [ ] **Step 1: Write the failing test**

```python
"""Pin the reviewed PostgreSQL tooling versions."""
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
REQ = (ROOT / "backend" / "requirements.txt").read_text(encoding="utf-8")


class DatabaseToolingPinTests(unittest.TestCase):
    def test_driver_and_migration_tool_pinned(self):
        self.assertIn("psycopg[binary]==3.3.8", REQ)
        self.assertIn("alembic==1.20.1", REQ)

    def test_no_posix_only_or_source_only_dependencies_added(self):
        # The two added lines must be wheel-installable on Linux and Windows.
        self.assertNotIn("psycopg[c]", REQ)  # source build would need libpq headers
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_tooling_pins -v`
Expected: FAIL on `test_driver_and_migration_tool_pinned`.

- [ ] **Step 3: Install and pin**

Run: `backend/.venv/bin/python -m pip install "psycopg[binary]==3.3.8" "alembic==1.20.1"`, then append exactly those two lines to `backend/requirements.txt` and refresh the generated freeze comment block to match the new full freeze (`python -m pip freeze`), preserving exact `==` pins throughout. Confirm `backend/.venv/bin/python -m pip check` passes.

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_tooling_pins -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/requirements.txt backend/tests/test_db_tooling_pins.py
git commit -m "feat(db): pin psycopg 3.3.8 and alembic 1.20.1"
```

### Task 2: Connection settings module

**Files:**
- Create: `backend/db/__init__.py` (empty)
- Create: `backend/db/settings.py`
- Test: `backend/tests/test_db_settings.py` (new)

**Interfaces:**
- Consumes: Task 1 pins (`import psycopg`).
- Produces: `backend.db.settings.test_database_url()` — reads the environment, returns a `psycopg conninfo`-acceptable string; raises `DatabaseConfigError(message)` (a new exception class in the same module) when unset or malformed. `backend.db.settings.SCRATCH_DB_NAME = "sort_tester_unittest_scratch"`.

- [ ] **Step 1: Write the failing tests**

```python
"""Connection-settings contract for the tooling foundation."""
import os
import unittest
from unittest import mock


from backend.db import settings


class TestDatabaseUrlTests(unittest.TestCase):
    def test_missing_variable_raises_naming_it(self):
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(settings.ENV_VAR, None)
            with self.assertRaises(settings.DatabaseConfigError) as ctx:
                settings.test_database_url()
        self.assertIn(settings.ENV_VAR, str(ctx.exception))

    def test_non_postgres_scheme_rejected(self):
        with mock.patch.dict(
            os.environ, {settings.ENV_VAR: "mysql://u:p@localhost/db"}
        ):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.test_database_url()

    def test_scratch_database_name_enforced(self):
        with mock.patch.dict(
            os.environ,
            {
                settings.ENV_VAR: "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch"
            },
        ):
            self.assertEqual(
                settings.test_database_url(),
                "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch",
            )

    def test_foreign_database_name_rejected(self):
        with mock.patch.dict(
            os.environ, {settings.ENV_VAR: "postgresql://u:p@localhost:5432/sort_tester_dev"}
        ):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.test_database_url()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: FAIL — `ModuleNotFoundError: backend.db`.

- [ ] **Step 3: Implement `backend/db/settings.py`**

`ENV_VAR = "SORT_TESTER_TEST_DATABASE_URL"`; `SCRATCH_DB_NAME = "sort_tester_unittest_scratch"`; `DatabaseConfigError(Exception)`; `test_database_url() -> str` reads the variable, strips whitespace, requires the URL to start with `postgresql://` and to end with `/{SCRATCH_DB_NAME}` (ignoring an empty query string), raising `DatabaseConfigError` with a message naming `ENV_VAR` and `SCRATCH_DB_NAME` otherwise. No default URL, no file reads, no secrets in code.

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/ backend/tests/test_db_settings.py
git commit -m "feat(db): env-only test database settings with scratch-db guard"
```

### Task 3: Alembic scaffold and probe migration

**Files:**
- Create: `backend/migrations/env.py`, `backend/migrations/versions/0001_tooling_probe.py`, `backend/migrations/script.py.mako` (standard Alembic template), `backend/migrations.ini`
- Create: `backend/db/migrate.py`
- Test: `backend/tests/test_db_migration.py` (new)

**Interfaces:**
- Consumes: Task 2 (`settings.test_database_url`, `settings.SCRATCH_DB_NAME`).
- Produces: `backend.db.migrate.upgrade_to_head(conninfo: str) -> None`, `backend.db.migrate.downgrade_all(conninfo: str) -> None`, `backend.db.migrate.current_revision(conninfo: str) -> str | None`. `alembic_version` table plus the `tooling_probe` table (columns: `id integer PRIMARY KEY`, `note text NOT NULL`) as the sole objects in revision `0001`.

- [ ] **Step 1: Write the failing test**

```python
"""Migration pipeline contract: clean migrate, restart persistence, rollback."""
import unittest


from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ToolingProbeMigrationTests(unittest.TestCase):
    conninfo = None

    @classmethod
    def setUpClass(cls):
        cls.admin = settings.admin_url()  # same server, connects to the default db
        migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
        cls.conninfo = settings.test_database_url()

    def test_clean_migrate_creates_probe_table(self):
        migrate.upgrade_to_head(self.conninfo)
        self.assertIsNotNone(migrate.current_revision(self.conninfo))
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_rerun_is_idempotent(self):
        migrate.upgrade_to_head(self.conninfo)  # second call, same head
        self.assertTrue(migrate.table_exists(self.conninfo, "tooling_probe"))

    def test_downgrade_removes_probe_table(self):
        migrate.downgrade_all(self.conninfo)
        self.assertIsNone(migrate.current_revision(self.conninfo))
        self.assertFalse(migrate.table_exists(self.conninfo, "tooling_probe"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_migration -v`
Expected: FAIL — `ImportError: backend.db.migrate` (or the skip when the env var is unset; if skipped, set the variable against the local server and re-run to see the real failure).

- [ ] **Step 3: Implement the scaffold and `backend/db/migrate.py`**

Use Alembic's standard template files; `env.py` reads the URL from the environment via `settings.test_database_url()` (never hardcodes one). `0001_tooling_probe.py` creates `tooling_probe` (`id integer PRIMARY KEY`, `note text NOT NULL`) with a matching downgrade. `migrate.py` drives Alembic's command API programmatically (`command.upgrade`, `command.downgrade`) with a `psycopg` connection; `recreate_scratch_database` issues `DROP DATABASE IF EXISTS … WITH (FORCE)` then `CREATE DATABASE` on the admin connection; `table_exists` queries `information_schema.tables`; `current_revision` reads `alembic_version` and returns `None` when absent. Also implement the two settings helpers the test imports: `settings.environment_has_test_url() -> bool` (presence only, no validation) and `settings.admin_url() -> str` (same URL with the database component replaced by the server's maintenance database).

- [ ] **Step 4: Run test to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_migration -v`
Expected: PASS (3 tests) against a local PostgreSQL server.

- [ ] **Step 5: Persistence across a real restart**

With the scratch database migrated and one row inserted, restart the PostgreSQL server (or stop/start the service per the OS), then run: `backend/.venv/bin/python -m unittest backend.tests.test_db_migration -v` after re-pointing the env var (fresh scratch) **plus** an ad-hoc check: reconnect and confirm the previously inserted row still exists before `recreate_scratch_database` runs again — run the check manually first with `psycopg` in a one-liner, record the output, then re-run the suite. Expected: row survives the restart.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations backend/migrations.ini backend/db/migrate.py backend/tests/test_db_migration.py
git commit -m "feat(db): alembic scaffold with probe migration and restart-persistence test"
```

### Task 4: Malformed-URL and stale-state harness behavior

**Files:**
- Modify: `backend/db/migrate.py` (hardening only)
- Test: `backend/tests/test_db_harness_guard.py` (new)

**Interfaces:**
- Consumes: Task 3 (`migrate.recreate_scratch_database`).
- Produces: `recreate_scratch_database` refuses any conninfo whose target database is not `SCRATCH_DB_NAME` (raises `settings.DatabaseConfigError`), and succeeds on a pre-existing stale scratch database.

- [ ] **Step 1: Write the failing tests**

```python
"""Guard rails around the scratch-database harness."""
import unittest


from backend.db import migrate, settings


class RecreateGuardTests(unittest.TestCase):
    def test_recreate_refuses_non_scratch_database(self):
        with self.assertRaises(settings.DatabaseConfigError):
            migrate.recreate_scratch_database(
                "postgresql://u:p@localhost:5432/sort_tester_dev",
                "sort_tester_dev",
            )

    def test_recreate_refuses_blank_name(self):
        with self.assertRaises(settings.DatabaseConfigError):
            migrate.recreate_scratch_database(
                "postgresql://u:p@localhost:5432/sort_tester_unittest_scratch", ""
            )
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_harness_guard -v`
Expected: FAIL — `recreate_scratch_database` currently accepts any name (or connects blindly).

- [ ] **Step 3: Implement the guards**

In `recreate_scratch_database(conninfo, name)`: raise `settings.DatabaseConfigError` unless `name == settings.SCRATCH_DB_NAME` and the URL's database component equals `name`. `DROP DATABASE IF EXISTS … WITH (FORCE)` then `CREATE DATABASE` unchanged. No network I/O is needed for either guard (validate before connecting).

- [ ] **Step 4: Run tests to verify they pass**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_harness_guard backend.tests.test_db_migration -v`
Expected: PASS (2 + 3 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/migrate.py backend/tests/test_db_harness_guard.py
git commit -m "feat(db): refuse non-scratch databases in test harness"
```

### Task 5: Full regression, docs record, and issue evidence

**Files:**
- Modify: `backend/README.md` (short "Database tooling" section: env var, server versions tested, how to run the migration tests)
- Modify: `docs/superpowers/plans/2026-11-11-postgresql-tooling-foundations.md` is this file (no change)
- Test: none new

**Interfaces:**
- Consumes: Tasks 1–4.
- Produces: verified regression evidence recorded in this plan's checkbox section below and on issue #6.

- [ ] **Step 1: Run the full backend suite**

Run: `backend/.venv/bin/python -m unittest discover -s backend/tests`
Expected: PASS — 83 previous + 11 new tests (Task 1: 2, Task 2: 4, Task 3: 3, Task 4: 2; Task 3's tests skip with a clear message wherever `SORT_TESTER_TEST_DATABASE_URL` is unset) — assert the exact total observed before claiming it.

- [ ] **Step 2: Run the JavaScript suite**

Run: `node --test tests/*.test.mjs`
Expected: 386 pass, 0 fail (unchanged).

- [ ] **Step 3: Record versions actually tested**

Append to `backend/README.md`: server version (`SELECT version();` output first line, e.g. PostgreSQL 16.x on macOS dev — the Linux host run records its own), driver `psycopg 3.3.8`, migration tool `alembic 1.20.1`, and the exact commands to run the database tests locally on Linux and Windows (set `SORT_TESTER_TEST_DATABASE_URL` to a `…/sort_tester_unittest_scratch` URL). No server hostnames or credentials.

- [ ] **Step 4: Commit and push**

```bash
git add backend/README.md
git commit -m "docs(db): record tested database tooling and local setup"
git push origin codex/ranked-mode
```

- [ ] **Step 5: Post evidence on issue #6**

Comment listing: pinned versions with wheel availability (cp314 manylinux/Windows/macOS), migration test results, restart-persistence evidence, and what remains open (schema modeling checks 2–5, Linux-host server install/version evidence, pilot/dev separation at the server level).

---

## Out of scope (later plans on #6)

- All ranked schema modeling (checks 2–5): IDs/tags/eligibility, attempt/answer/settlement keys, balance atomicity, outbox contract, deletion/redaction, cutover/restore.
- Password hashing, sessions, MFA, email adapter (issues #7, #10, #27).
- Any production/pilot server provisioning or Azure work.
