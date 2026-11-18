# Managed-identity PostgreSQL authentication — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the hosted app authenticate to PostgreSQL with a short-lived Entra token instead of a password, behind an off-by-default flag, so no code change alters the running app until a separately-approved deployment.

**Architecture:** A `SORT_TESTER_DB_AUTH` flag selects `password` (today's path, default) or `managed_identity`. In managed-identity mode the pool supplies a fresh Entra token as the connection password for each physical connection it opens, via `psycopg_pool`'s per-connection callable `kwargs`; the token comes from an `azure-identity` wrapper whose own cache handles reuse and refresh. Token/connect failure surfaces as a clean HTTP 503 through one FastAPI exception handler, with no secret logged.

**Tech Stack:** Python 3.14, FastAPI, psycopg 3.3.8, psycopg-pool 3.3.3, azure-identity. Tests: `unittest` (`backend.ci_tests` / `backend/tests`).

**Spec:** `docs/superpowers/specs/2026-11-18-managed-identity-postgres-design.md`.

## Global Constraints

- **No deployment, no Azure change.** This plan ships code, tests and a written (not applied) runbook only. No Bicep edit, no grant change, no `passwordAuth` change, no removal of the vault password reference.
- **`password` is the default mode.** Merging this must change nothing about the running app or local development. No new env var is required in `password` mode.
- **The token value is never logged**, in success, failure or error paths.
- **Pinned dependencies.** `psycopg-pool==3.3.3`, `psycopg==3.3.8`. Add `azure-identity` pinned by exact version to `backend/requirements-runtime.txt` **and** `backend/requirements.txt`.
- **Preserve the pool contract:** `MAX_SIZE = 8`, `STATEMENT_TIMEOUT_MS = 5000` in the DSN options, `check=ConnectionPool.check_connection`, `row_factory=dict_row`, explicit transactions (`checkout()` never commits; rolls back on return).
- **TLS unchanged:** both modes pass through `_require_verified_tls`; `managed_identity` DSNs carry no password.
- **Migrations/tests bypass the pool** via `migrate.connect` — do not route them through the token path.
- Confirmed mechanism (psycopg_pool 3.3.3, verified in the repo venv): `KwargsParam = Union[dict, Callable[[], dict]]`; `ConnectionPool._connect` calls `_resolve_kwargs()` on every physical connect, then `connection_class.connect(conninfo, **kwargs)`. A callable `kwargs` is therefore resolved per connection.

---

### Task 1: Mode selector in settings

**Files:**
- Modify: `backend/db/settings.py`
- Test: `backend/tests/test_db_settings.py` (create if absent; otherwise add to the existing settings test module)

**Interfaces:**
- Produces: `settings.DB_AUTH_ENV_VAR = "SORT_TESTER_DB_AUTH"`; `settings.DB_IDENTITY_CLIENT_ID_ENV_VAR = "SORT_TESTER_DB_IDENTITY_CLIENT_ID"`; `settings.db_auth_mode() -> str` returning `"password"` or `"managed_identity"`; raises `DatabaseConfigError` on any other value. `settings.PASSWORD_MODE = "password"`, `settings.MANAGED_IDENTITY_MODE = "managed_identity"`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_db_settings.py
import os
import unittest
from contextlib import contextmanager

from backend.db import settings


@contextmanager
def _env(**values):
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class DbAuthModeTests(unittest.TestCase):
    def test_defaults_to_password_when_unset(self):
        with _env(SORT_TESTER_DB_AUTH=None):
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_blank_is_password(self):
        with _env(SORT_TESTER_DB_AUTH="   "):
            self.assertEqual(settings.db_auth_mode(), settings.PASSWORD_MODE)

    def test_managed_identity_is_accepted(self):
        with _env(SORT_TESTER_DB_AUTH="managed_identity"):
            self.assertEqual(settings.db_auth_mode(), settings.MANAGED_IDENTITY_MODE)

    def test_unknown_mode_raises(self):
        with _env(SORT_TESTER_DB_AUTH="kerberos"):
            with self.assertRaises(settings.DatabaseConfigError):
                settings.db_auth_mode()
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: FAIL — `AttributeError: module 'backend.db.settings' has no attribute 'db_auth_mode'`.

- [ ] **Step 3: Implement the selector**

Add near the top of `backend/db/settings.py` (after the existing env-var constants):

```python
DB_AUTH_ENV_VAR = "SORT_TESTER_DB_AUTH"
DB_IDENTITY_CLIENT_ID_ENV_VAR = "SORT_TESTER_DB_IDENTITY_CLIENT_ID"
PASSWORD_MODE = "password"
MANAGED_IDENTITY_MODE = "managed_identity"
_DB_AUTH_MODES = (PASSWORD_MODE, MANAGED_IDENTITY_MODE)


def db_auth_mode() -> str:
    """Which runtime authentication mode the app uses.

    Defaults to password so dev and CI need no new variable. An unknown
    value stops startup rather than guessing.
    """
    raw = os.environ.get(DB_AUTH_ENV_VAR, "").strip()
    if not raw:
        return PASSWORD_MODE
    if raw not in _DB_AUTH_MODES:
        raise DatabaseConfigError(
            f"{DB_AUTH_ENV_VAR} must be one of {', '.join(_DB_AUTH_MODES)}; "
            f"got {raw!r}."
        )
    return raw
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_settings -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add backend/db/settings.py backend/tests/test_db_settings.py
git commit -m "feat: SORT_TESTER_DB_AUTH mode selector, password default (#84)"
```

---

### Task 2: Entra token provider

**Files:**
- Create: `backend/db/entra_token.py`
- Create test: `backend/tests/test_entra_token.py`
- Modify: `backend/requirements-runtime.txt`, `backend/requirements.txt` (add `azure-identity`)

**Interfaces:**
- Produces: `entra_token.DB_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"`; `entra_token.db_access_token() -> str`; `entra_token.set_credential(credential_or_none)` test seam; a credential object exposes `get_token(*scopes) -> object` whose `.token` is the string (matches `azure-identity`'s `AccessToken`). `entra_token.TokenUnavailable(Exception)` raised when acquisition fails.

- [ ] **Step 1: Add the dependency**

Find the current `azure-identity` release and pin it. Add to `backend/requirements-runtime.txt` after the psycopg lines:

```
azure-identity==<latest-stable>
```

Add the identical pin to `backend/requirements.txt`. Then install into the venv:

```bash
backend/.venv/bin/pip install "azure-identity==<latest-stable>"
```

(Replace `<latest-stable>` with the resolved version; record it identically in both files.)

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_entra_token.py
import logging
import unittest

from backend.db import entra_token


class FakeToken:
    def __init__(self, token):
        self.token = token


class FakeCredential:
    def __init__(self, tokens=None, error=None):
        self._tokens = list(tokens or ["tok-1"])
        self._error = error
        self.calls = 0

    def get_token(self, *scopes):
        self.calls += 1
        if self._error is not None:
            raise self._error
        value = self._tokens.pop(0) if len(self._tokens) > 1 else self._tokens[0]
        return FakeToken(value)


class EntraTokenTests(unittest.TestCase):
    def tearDown(self):
        entra_token.set_credential(None)

    def test_returns_the_token_string(self):
        entra_token.set_credential(FakeCredential(["tok-abc"]))
        self.assertEqual(entra_token.db_access_token(), "tok-abc")

    def test_requests_the_postgres_scope(self):
        cred = FakeCredential(["tok-abc"])
        captured = {}
        orig = cred.get_token
        def spy(*scopes):
            captured["scopes"] = scopes
            return orig(*scopes)
        cred.get_token = spy
        entra_token.set_credential(cred)
        entra_token.db_access_token()
        self.assertEqual(captured["scopes"], (entra_token.DB_TOKEN_SCOPE,))

    def test_failure_raises_tokenunavailable_not_the_raw_error(self):
        entra_token.set_credential(FakeCredential(error=RuntimeError("imds down")))
        with self.assertRaises(entra_token.TokenUnavailable):
            entra_token.db_access_token()

    def test_token_value_is_never_logged(self):
        entra_token.set_credential(FakeCredential(["super-secret-token"]))
        with self.assertLogs(level=logging.DEBUG) as captured:
            logging.getLogger("backend.db.entra_token").debug("probe")  # ensure the logger exists
            entra_token.db_access_token()
        self.assertFalse(
            any("super-secret-token" in line for line in captured.output),
            "the token value must never appear in logs",
        )

    def test_failure_does_not_log_any_token(self):
        entra_token.set_credential(FakeCredential(error=RuntimeError("boom")))
        with self.assertLogs(level=logging.DEBUG) as captured:
            try:
                entra_token.db_access_token()
            except entra_token.TokenUnavailable:
                pass
        self.assertFalse(any("tok" in line.lower() and "token" not in line.lower()
                             for line in captured.output))
```

- [ ] **Step 3: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_entra_token -v`
Expected: FAIL — module `backend.db.entra_token` does not exist.

- [ ] **Step 4: Implement the provider**

```python
# backend/db/entra_token.py
"""An Entra access token used as the PostgreSQL connection password (#84).

Managed-identity mode replaces the database password with a short-lived
Entra token. azure-identity's credential caches the token and refreshes it
near expiry on its own, so this module does not keep a cache of its own; it
asks for the token per physical connection and lets the SDK decide whether
that means a network call. The token value is never logged.
"""
import logging
import os

from backend.db import settings

logger = logging.getLogger(__name__)

DB_TOKEN_SCOPE = "https://ossrdbms-aad.database.windows.net/.default"

_credential = None  # set lazily, or injected by tests via set_credential


class TokenUnavailable(Exception):
    """Raised when no Entra token could be obtained."""


def set_credential(credential) -> None:
    """Inject a credential (tests) or reset to lazy default with None."""
    global _credential
    _credential = credential


def _build_credential():
    # Imported lazily so password-mode environments need not install
    # azure-identity to import this module indirectly.
    from azure.identity import ManagedIdentityCredential

    client_id = os.environ.get(settings.DB_IDENTITY_CLIENT_ID_ENV_VAR, "").strip()
    if not client_id:
        raise TokenUnavailable(
            f"{settings.DB_IDENTITY_CLIENT_ID_ENV_VAR} is not set; "
            "managed-identity mode needs the user-assigned identity's client id."
        )
    return ManagedIdentityCredential(client_id=client_id)


def _current_credential():
    global _credential
    if _credential is None:
        _credential = _build_credential()
    return _credential


def db_access_token() -> str:
    """Return a fresh Entra token for the PostgreSQL scope.

    Never logs the token. On any failure raises TokenUnavailable with no
    token material in the message.
    """
    try:
        access = _current_credential().get_token(DB_TOKEN_SCOPE)
        return access.token
    except TokenUnavailable:
        raise
    except Exception as error:  # noqa: BLE001 - deliberately broad; no token in the message
        logger.warning("Entra token acquisition failed: %s", type(error).__name__)
        raise TokenUnavailable("could not obtain an Entra token for the database") from error
```

- [ ] **Step 5: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_entra_token -v`
Expected: PASS (5 tests).

- [ ] **Step 6: Commit**

```bash
git add backend/db/entra_token.py backend/tests/test_entra_token.py backend/requirements-runtime.txt backend/requirements.txt
git commit -m "feat: Entra token provider for database auth, never logged (#84)"
```

---

### Task 3: Pool builds the token path

**Files:**
- Modify: `backend/db/pool.py`
- Modify: `backend/routers/auth.py:28-39` (the `_db_connection` / `init_pool` call)
- Modify: `backend/routers/ranked.py:55-64` (the `_db_connection` / `init_pool` call)
- Test: `backend/tests/test_pool_managed_identity.py` (create)

**Interfaces:**
- Consumes: `settings.db_auth_mode()`, `settings.MANAGED_IDENTITY_MODE`, `entra_token.db_access_token`.
- Produces: `pool.init_pool(conninfo: str, *, auth_mode: str = settings.PASSWORD_MODE, token_provider=entra_token.db_access_token) -> None`. In managed-identity mode the pool is built with a callable `kwargs` returning `{"row_factory": dict_row, "password": token_provider()}`; in password mode `kwargs` stays the static `{"row_factory": dict_row}`. No other pool parameter changes.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_pool_managed_identity.py
import unittest
from unittest import mock

from backend.db import pool, settings


class ManagedIdentityPoolTests(unittest.TestCase):
    def tearDown(self):
        pool.close_pool()

    def test_managed_identity_builds_a_callable_kwargs_that_injects_the_token(self):
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return f"token-{calls['n']}"

        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app@host/db?sslmode=verify-full",
                auth_mode=settings.MANAGED_IDENTITY_MODE,
                token_provider=provider,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]

        self.assertTrue(callable(built_kwargs), "managed-identity kwargs must be a callable")
        first = built_kwargs()
        second = built_kwargs()
        self.assertEqual(first["password"], "token-1")
        self.assertEqual(second["password"], "token-2")
        self.assertIn("row_factory", first)

    def test_password_mode_keeps_static_kwargs(self):
        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app:pw@host/db?sslmode=verify-full",
                auth_mode=settings.PASSWORD_MODE,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]
        self.assertFalse(callable(built_kwargs))
        self.assertNotIn("password", built_kwargs)
```

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_pool_managed_identity -v`
Expected: FAIL — `init_pool()` got an unexpected keyword argument `auth_mode`.

- [ ] **Step 3: Implement in `pool.py`**

Add the imports at the top:

```python
from backend.db import entra_token, settings as db_settings
```

Replace `init_pool` with:

```python
def init_pool(
    conninfo: str,
    *,
    auth_mode: str = db_settings.PASSWORD_MODE,
    token_provider=entra_token.db_access_token,
) -> None:
    """Build the pool if there is not one already.

    Idempotent on purpose: called at startup and defensively from
    `checkout`. In managed-identity mode the connection password is a fresh
    Entra token resolved per physical connection via a callable kwargs; the
    conninfo carries no password. Password mode is unchanged.
    """
    global _pool
    if _pool is not None:
        return
    if auth_mode == db_settings.MANAGED_IDENTITY_MODE:
        def _kwargs():
            return {"row_factory": dict_row, "password": token_provider()}
        pool_kwargs = _kwargs
    else:
        pool_kwargs = {"row_factory": dict_row}
    _pool = ConnectionPool(
        conninfo=_conninfo_with_timeout(conninfo),
        min_size=1,
        max_size=MAX_SIZE,
        kwargs=pool_kwargs,
        check=ConnectionPool.check_connection,
        open=True,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_pool_managed_identity -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Wire both routers to pass the mode**

In `backend/routers/auth.py`, change the `init_pool` call inside `_db_connection`:

```python
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
```

Make the identical change in `backend/routers/ranked.py`'s `_db_connection`.

- [ ] **Step 6: Run the full backend suite**

Run: `backend/.venv/bin/python -m backend.ci_tests`
Expected: all green, 0 skips (password mode unchanged; the new tests pass with mocked pools).

- [ ] **Step 7: Commit**

```bash
git add backend/db/pool.py backend/routers/auth.py backend/routers/ranked.py backend/tests/test_pool_managed_identity.py
git commit -m "feat: pool injects a per-connection Entra token in managed-identity mode (#84)"
```

---

### Task 4: Token/connection failure returns a clean 503

**Files:**
- Modify: `backend/main.py:32-41` (register an exception handler inside `create_app`)
- Test: `backend/tests/test_db_unavailable_503.py` (create)

**Interfaces:**
- Consumes: `entra_token.TokenUnavailable`, `psycopg_pool.PoolTimeout`.
- Produces: a FastAPI exception handler mapping those two exception types to HTTP 503 with body `{"detail": "database temporarily unavailable"}` and no token/DSN in the response or log. Serves every route; the routers are unchanged.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_db_unavailable_503.py
import unittest
from unittest import mock

from fastapi.testclient import TestClient
from psycopg_pool import PoolTimeout

from backend.db import entra_token
from backend.main import create_app


class DbUnavailable503Tests(unittest.TestCase):
    def _client(self):
        return TestClient(create_app(), raise_server_exceptions=False)

    def test_pool_timeout_becomes_503(self):
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=PoolTimeout("no conn")):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.json()["detail"], "database temporarily unavailable")

    def test_token_unavailable_becomes_503_without_secret(self):
        err = entra_token.TokenUnavailable("could not obtain an Entra token for the database")
        with mock.patch("backend.routers.ranked.pool.checkout", side_effect=err):
            response = self._client().get("/api/ranked/season/notice")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("token", response.text.lower())
```

(If `/api/ranked/season/notice` is not the public read path, use the route confirmed in `backend/routers/ranked.py`; it is `get_readonly_db`-backed and needs no auth.)

- [ ] **Step 2: Run to verify it fails**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_unavailable_503 -v`
Expected: FAIL — the exception surfaces as 500, not 503.

- [ ] **Step 3: Implement the handler in `create_app`**

Add imports to `backend/main.py`:

```python
from fastapi import Request, status
from fastapi.responses import JSONResponse
from psycopg_pool import PoolTimeout

from backend.db.entra_token import TokenUnavailable
```

Inside `create_app`, after the routers are included:

```python
    @application.exception_handler(TokenUnavailable)
    @application.exception_handler(PoolTimeout)
    def _database_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
        # No token or DSN is read from the exception, so nothing secret can
        # reach the client or the log. A request that needs a *new*
        # connection while none can be made gets this; healthy pooled
        # connections keep serving.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database temporarily unavailable"},
        )
```

- [ ] **Step 4: Run to verify it passes**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_db_unavailable_503 -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full suite**

Run: `backend/.venv/bin/python -m backend.ci_tests`
Expected: all green, 0 skips.

- [ ] **Step 6: Commit**

```bash
git add backend/main.py backend/tests/test_db_unavailable_503.py
git commit -m "feat: map pool/token unavailability to a clean 503, no secret logged (#84)"
```

---

### Task 5: Runbook — Entra role, connection and tested rollback (written, not applied)

**Files:**
- Modify: `infra/azure/db-runtime-role.md` (add a managed-identity section) and/or `infra/azure/container-apps-app.md` §9 (rotation/credentials)
- Test: `backend/tests/test_docs_hygiene.py` must stay green with the new prose (no real resource names, no placeholder DSNs).

**Interfaces:** none (documentation). This task applies nothing in Azure.

- [ ] **Step 1: Write the role/grants mapping (SQL, reviewed not applied)**

In `infra/azure/db-runtime-role.md`, add a section "Managed-identity mode (#84) — procedure, not yet applied" containing the exact SQL to map the **existing** user-assigned managed identity to a PostgreSQL Entra role, with runtime-only grants mirroring `sort_app` (SELECT/INSERT/UPDATE/DELETE on the app tables, USAGE on sequences, **no** superuser, **no** CREATE, **no** DDL, **no** migration authority). Mark that the mapping and grants must be verified against the live server as a checklist item, and that existing registry/vault access is not database access. Do not include any real server, vault, resource-group or identity name — use the placeholders the other docs use, which `test_docs_hygiene` tolerates.

- [ ] **Step 2: Write the connection and the environment**

Document that managed-identity mode sets `SORT_TESTER_DB_AUTH=managed_identity` and `SORT_TESTER_DB_IDENTITY_CLIENT_ID=<identity client id>`, that the DSN carries **no password**, the user is the Entra role, `sslmode=verify-full` where the image's CA bundle is confirmed (Task 7 dependency) else `require`, and that the token is fetched per physical connection by the app.

- [ ] **Step 3: Write the tested rollback**

Document the rollback to password mode: set `SORT_TESTER_DB_AUTH=password` (or unset), confirm the Key Vault password reference still resolves, and apply on a **new revision** — a restart does not re-read the secret (cross-reference §9b). State that the rollback must be exercised before the forward cutover is trusted.

- [ ] **Step 4: Write the ordered, approval-gated deploy/verification**

List, as steps gated on separate owner approval and run by nobody as part of this work: deploy with the flag; verify hosted identity login, reconnect and token refresh; verify admin/migration still work through their intended Entra path; and only then (separately, with approval) remove the runtime password reference and consider server-wide `passwordAuth`. No step is executed here.

- [ ] **Step 5: Run docs hygiene**

Run: `backend/.venv/bin/python -m unittest backend.tests.test_docs_hygiene -v`
Expected: PASS (new prose carries no real names and no placeholder DSNs).

- [ ] **Step 6: Commit**

```bash
git add infra/azure/db-runtime-role.md infra/azure/container-apps-app.md
git commit -m "docs: managed-identity role, connection and rollback runbook, not applied (#84)"
```

---

## Self-Review

**1. Spec coverage**

- Mode selection (spec §1) → Task 1. ✅
- Token provider + no-logging + test seam (spec §2) → Task 2. ✅
- Per-physical-connection token in the pool, contract preserved (spec §3) → Task 3. ✅
- Clean 503, single tested place, healthy connections unaffected (spec §4) → Task 4. ✅
- Local dev stays password (spec §5) → Task 1 default + Task 3 password branch unchanged; the full suite runs in password mode in Tasks 3/4. ✅
- Tests: reuse, refresh, failure, no-token-in-logs, mode validation, password untouched (spec §6) → Tasks 1–4 (reuse/refresh are exercised via the per-call provider in Task 3's callable test and the SDK-cache note; the failure + no-log guards are Task 2/4). ✅
- Runbook: role/grants, connection, rollback, ordered deploy (spec §7) → Task 5. ✅
- Dependency `azure-identity` pinned in both requirements files (spec Dependencies) → Task 2 Step 1. ✅

**2. Placeholder scan:** `<latest-stable>` in Task 2 and `<identity client id>` / placeholder names in Task 5 are deliberate fill-ins the implementer resolves against the live package/doc conventions, not skipped work; every code step carries real code. No "TBD"/"add error handling"/"write tests for the above".

**3. Type consistency:** `db_auth_mode()`, `PASSWORD_MODE`, `MANAGED_IDENTITY_MODE`, `DB_IDENTITY_CLIENT_ID_ENV_VAR` (Task 1) are the names used in Tasks 2–3. `db_access_token()` and `TokenUnavailable` (Task 2) are the names used in Tasks 3–4. `init_pool(conninfo, *, auth_mode, token_provider)` (Task 3) matches the router calls. Consistent.

## Notes and open implementation detail

- **Reuse/refresh evidence (spec §6.1–6.2):** azure-identity's own cache makes "reuse within lifetime" and "refresh near expiry" the SDK's behaviour, not ours. Task 3's callable test proves the pool asks the provider per physical connect; Task 2's tests prove the provider returns/raises correctly. A direct SDK-cache timing test is not meaningful against a fake and is explicitly left to the SDK — note this in the test file's docstring rather than faking expiry semantics.
- **Pool acquisition timeout:** the default pool `timeout` is 30s and `reconnect_timeout` 300s (bounded background retry, not a tight spin). If a faster 503 is wanted in managed-identity mode, a shorter pool `timeout` can be added in Task 3 — left out here to avoid changing password-mode behaviour; raise it with the owner if the 503 latency matters before the pilot.
