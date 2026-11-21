# Forgot-my-login Recovery Messages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A signed-out player can leave the owner one free-text message from the sign-in screen; the owner reads it in Owner tools and marks it resolved (issue #251).

**Architecture:** A new table `recovery_messages` with its own rule module (`backend/auth/recovery_messages.py`), kept apart from `recovery_requests` because a message names no account. A public, rate-limited `POST /api/auth/recovery-messages` on its own small router (so no database work runs before the limiter), two owner routes beside the existing `/api/ranked/owner/recoveries`, a form in the sign-in panel (`src/auth.js`) and a list screen in Owner tools (`src/app.js`). Restoring access is untouched: still `recovery.open_request` → `recovery.hand_over`.

**Tech Stack:** FastAPI, psycopg + Alembic (raw SQL through `backend.db.migrate`), stdlib `unittest` against a real PostgreSQL scratch database, vanilla ES modules, `node --test`.

**Spec:** `docs/superpowers/specs/2026-11-21-forgot-login-recovery-messages-design.md`

## Global Constraints

- Message body: trimmed, 1–500 characters. Empty or longer → 422.
- Rate limits: 3 per hour per client key, 50 per day in total, in memory per app instance; ceiling of 100 unresolved messages in the database. All three → 429.
- The public endpoint answers 201 with an **empty body** and looks up no account. The network address is not stored.
- Owner routes: 401 signed out, 403 not the owner, **no** recent-reauth (428) gate.
- No email, phone or third-party call. No change to `backend/auth/recovery.py`.
- UI copy in English and Spanish only. Never Portuguese.
- `src/auth.js` must stay import-free (`tests/auth-client.test.mjs` loads it from a data URL).
- Backend tests run only with the scratch database set; without it they skip silently and prove nothing:
  `SORT_TESTER_TEST_DATABASE_URL="postgresql://localhost:5432/sort_tester_unittest_scratch" ./backend/.venv/bin/python3 -m unittest <module> -v`
  (below this prefix is written as `DBTEST`). There is no pytest in that venv.
- Frontend tests: `node --test tests/<file>.test.mjs`.
- Every commit message ends with `Co-Authored-By: Claude Fable 5.2 <noreply@anthropic.com>`.
- Work on branch `feat/forgot-login-251`; the PR targets `codex/ranked-mode`. The owner merges.

## File Structure

| File | Responsibility |
| --- | --- |
| Create `backend/migrations/versions/0038_recovery_messages.py` | The table |
| Create `backend/auth/recovery_messages.py` | The rule: leave, list, resolve |
| Create `backend/routers/recovery_messages.py` | Public POST, limiter first |
| Modify `backend/main.py` | Second limiter on `application.state`, include the router |
| Modify `backend/routers/ranked.py` | Two owner routes |
| Modify `src/auth.js` | "Forgot my login?" form on the sign-in panel |
| Modify `src/app.js`, `src/i18n.js` | Owner tools entry and list screen, ES strings |
| Create `backend/tests/test_db_recovery_messages_schema.py`, `test_auth_recovery_messages.py`, `test_recovery_messages_router.py`, `test_ranked_recovery_messages_router.py` | Backend tests |
| Create `tests/forgot-login.test.mjs`, `tests/recovery-messages-screen.test.mjs` | Frontend tests |

---

### Task 1: The `recovery_messages` table

**Files:**
- Create: `backend/migrations/versions/0038_recovery_messages.py`
- Test: `backend/tests/test_db_recovery_messages_schema.py`

**Interfaces:**
- Produces: table `recovery_messages(id uuid pk, body text, created_at timestamptz, resolved_at timestamptz null, resolved_by uuid null → accounts(id) ON DELETE SET NULL)`.

- [ ] **Step 1: Write the failing test**

```python
"""recovery_messages: what the table itself refuses (issue #251)."""
import unittest

import psycopg

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessagesSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)

    def _insert(self, body):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO recovery_messages (body) VALUES (%s)"
            " RETURNING id, created_at, resolved_at, resolved_by",
            (body,),
        )

    def test_a_message_starts_open(self):
        row = self._insert("locked out")
        self.assertIsNotNone(row["created_at"])
        self.assertIsNone(row["resolved_at"])
        self.assertIsNone(row["resolved_by"])

    def test_empty_and_overlong_bodies_are_refused(self):
        for body in ("", "x" * 501):
            with self.assertRaises(psycopg.errors.CheckViolation):
                self._insert(body)
            self.conn.rollback()
        self._insert("x" * 500)

    def test_resolved_by_needs_resolved_at(self):
        owner = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES ('the_owner', 'the_owner', 'OWN001', true) RETURNING id",
        )["id"]
        message = self._insert("locked out")["id"]
        with self.assertRaises(psycopg.errors.CheckViolation):
            migrate.execute(
                self.conn,
                "UPDATE recovery_messages SET resolved_by = %s WHERE id = %s",
                (owner, message),
            )

    def test_deleting_the_resolver_keeps_the_message(self):
        owner = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES ('the_owner', 'the_owner', 'OWN001', true) RETURNING id",
        )["id"]
        message = self._insert("locked out")["id"]
        migrate.execute(
            self.conn,
            "UPDATE recovery_messages SET resolved_at = now(), resolved_by = %s"
            " WHERE id = %s",
            (owner, message),
        )
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (owner,))
        row = migrate.fetch_one(
            self.conn,
            "SELECT resolved_at, resolved_by FROM recovery_messages WHERE id = %s",
            (message,),
        )
        self.assertIsNotNone(row["resolved_at"])
        self.assertIsNone(row["resolved_by"])

    def test_downgrade_removes_the_table(self):
        self.conn.close()
        self.assertTrue(migrate.table_exists(self.conninfo, "recovery_messages"))
        migrate.downgrade_all(self.conninfo)
        self.assertFalse(migrate.table_exists(self.conninfo, "recovery_messages"))
```

- [ ] **Step 2: Run it and watch it fail**

Run: `DBTEST backend.tests.test_db_recovery_messages_schema`
Expected: errors with `relation "recovery_messages" does not exist`. If it reports `skipped`, the environment variable is missing — fix that first.

- [ ] **Step 3: Write the migration**

```python
"""Messages a locked-out player leaves for the owner (issue #251).

Revision ID: 0038
Revises: 0037
Create Date: 2026-11-21

A player who lost their login ID cannot sign in, so they cannot open a
support ticket, and there is deliberately no email. This is the one thing
they can do from the sign-in screen: leave a message the owner reads.

It is not `recovery_requests`. That table records the owner standing in
front of an account they have identified, so it requires the account and
the owner. A message comes from nobody in particular: it names no account,
none is guessed from its text, and it proves nothing about who wrote it.
Restoring access still goes through `recovery_requests`, in person.

The row keeps the text, when it arrived, and when and by whom it was
marked resolved. It does not keep the network address it came from.
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0038"
down_revision: Union[str, Sequence[str], None] = "0037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE recovery_messages (
            id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
            body text NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now(),
            resolved_at timestamptz,
            resolved_by uuid REFERENCES accounts(id) ON DELETE SET NULL,
            CONSTRAINT recovery_messages_body_length CHECK (
                char_length(body) BETWEEN 1 AND 500
            ),
            CONSTRAINT recovery_messages_resolved_pair CHECK (
                resolved_by IS NULL OR resolved_at IS NOT NULL
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX recovery_messages_created_idx"
        " ON recovery_messages (created_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS recovery_messages")
```

- [ ] **Step 4: Run it and watch it pass**

Run: `DBTEST backend.tests.test_db_recovery_messages_schema`
Expected: `Ran 5 tests`, `OK`, no `skipped`.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0038_recovery_messages.py backend/tests/test_db_recovery_messages_schema.py
git commit -m "feat(#251): recovery_messages table"
```

---

### Task 2: The rule module

**Files:**
- Create: `backend/auth/recovery_messages.py`
- Test: `backend/tests/test_auth_recovery_messages.py`

**Interfaces:**
- Consumes: the table from Task 1; `backend.db.migrate.fetch_one / fetch_all / execute`; a clock object with `.now()`.
- Produces:
  - `MAX_LENGTH = 500`, `MAX_UNRESOLVED = 100`
  - `class MessageRefused(Exception)` with `.reason: str` — bad body
  - `class InboxFull(Exception)` — unresolved ceiling reached
  - `class NotOwner(Exception)`
  - `leave_message(conn, body: str, *, clock) -> None`
  - `list_messages(conn, owner_account_id: UUID, limit: int = 50) -> list[dict]` — keys `id, body, created_at, resolved_at`; open first, then newest first
  - `resolve(conn, owner_account_id: UUID, message_id: UUID, *, clock) -> bool` — `False` when the id does not exist; resolving twice keeps the first date and returns `True`

- [ ] **Step 1: Write the failing test**

```python
"""Recovery messages: the rule (issue #251).

A message is a note to the owner and nothing more. These tests hold the
bounds on it and who may read it.
"""
import unittest
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from backend.auth import recovery_messages
from backend.db import migrate, settings

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.clock = FakeClock(T0)
        self.owner = self._account("the_owner", "OWN001", owner=True)
        self.player = self._account("dock_owl", "DCK002")
        self.conn.commit()

    def _account(self, name, tag, *, owner=False):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag, is_owner)"
            " VALUES (%s, %s, %s, %s) RETURNING id",
            (name, name.lower(), tag, owner),
        )["id"]

    def _leave(self, body="I lost my login ID"):
        recovery_messages.leave_message(self.conn, body, clock=self.clock)

    def _bodies(self):
        return [m["body"] for m in recovery_messages.list_messages(self.conn, self.owner)]

    # --- leaving one ---

    def test_a_message_is_stored_trimmed(self):
        self._leave("  I am Sam from the night sort  \n")
        self.assertEqual(self._bodies(), ["I am Sam from the night sort"])

    def test_empty_and_overlong_messages_are_refused(self):
        for body in ("", "   \n ", "x" * 501, None):
            with self.assertRaises(recovery_messages.MessageRefused):
                self._leave(body)
        self._leave("x" * 500)
        self.assertEqual(len(self._bodies()), 1)

    def test_the_inbox_has_a_ceiling_of_unresolved_messages(self):
        migrate.execute(
            self.conn,
            "INSERT INTO recovery_messages (body)"
            " SELECT 'filler' FROM generate_series(1, %s)",
            (recovery_messages.MAX_UNRESOLVED,),
        )
        with self.assertRaises(recovery_messages.InboxFull):
            self._leave()
        # resolving one makes room again
        one = recovery_messages.list_messages(self.conn, self.owner, limit=1)[0]["id"]
        recovery_messages.resolve(self.conn, self.owner, one, clock=self.clock)
        self._leave("room again")

    def test_a_message_naming_an_account_touches_no_account(self):
        before = migrate.fetch_all(self.conn, "SELECT * FROM accounts ORDER BY id")
        self._leave("I am dock_owl #DCK002")
        self._leave("I am nobody_here #ZZZ999")
        after = migrate.fetch_all(self.conn, "SELECT * FROM accounts ORDER BY id")
        self.assertEqual(before, after)

    # --- reading and resolving ---

    def test_only_the_owner_may_list_or_resolve(self):
        self._leave()
        with self.assertRaises(recovery_messages.NotOwner):
            recovery_messages.list_messages(self.conn, self.player)
        with self.assertRaises(recovery_messages.NotOwner):
            recovery_messages.resolve(self.conn, self.player, uuid4(), clock=self.clock)

    def test_open_messages_come_first_then_newest(self):
        self._leave("oldest")
        self.clock.moment = T0 + timedelta(minutes=1)
        self._leave("middle")
        self.clock.moment = T0 + timedelta(minutes=2)
        self._leave("newest")
        middle = next(
            m["id"] for m in recovery_messages.list_messages(self.conn, self.owner)
            if m["body"] == "middle"
        )
        recovery_messages.resolve(self.conn, self.owner, middle, clock=self.clock)
        self.assertEqual(self._bodies(), ["newest", "oldest", "middle"])

    def test_resolving_records_when_and_is_idempotent(self):
        self._leave()
        message = recovery_messages.list_messages(self.conn, self.owner)[0]["id"]
        self.clock.moment = T0 + timedelta(hours=1)
        self.assertTrue(recovery_messages.resolve(self.conn, self.owner, message, clock=self.clock))
        self.clock.moment = T0 + timedelta(hours=5)
        self.assertTrue(recovery_messages.resolve(self.conn, self.owner, message, clock=self.clock))
        row = recovery_messages.list_messages(self.conn, self.owner)[0]
        self.assertEqual(row["resolved_at"], T0 + timedelta(hours=1))

    def test_resolving_an_unknown_message_reports_it(self):
        self.assertFalse(
            recovery_messages.resolve(self.conn, self.owner, uuid4(), clock=self.clock)
        )
```

- [ ] **Step 2: Run it and watch it fail**

Run: `DBTEST backend.tests.test_auth_recovery_messages`
Expected: `ImportError: cannot import name 'recovery_messages'`.

- [ ] **Step 3: Write the module**

```python
"""Messages a locked-out player leaves for the owner (issue #251).

Somebody who lost their login ID cannot sign in, and there is no email.
From the sign-in screen they may leave one free-text message. This module
is the whole rule for that message:

* **It is a note, not a recovery.** Leaving one looks up no account, opens
  no recovery request and issues nothing. Access is restored only by the
  owner, in person, through ``backend/auth/recovery.py``.
* **It proves nothing.** Anybody can type anything, including somebody
  else's name. The owner reads it as a reason to go and find a person.
* **It is bounded.** At most ``MAX_LENGTH`` characters, and at most
  ``MAX_UNRESOLVED`` unread at once, so the table cannot be filled from
  outside however many addresses the messages come from.
* **Only the owner reads it.**
"""
from uuid import UUID

from backend.db import migrate

MAX_LENGTH = 500
MAX_UNRESOLVED = 100


class MessageRefused(Exception):
    """The text itself is not acceptable. ``reason`` may be shown."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class InboxFull(Exception):
    """Too many unresolved messages are already waiting."""


class NotOwner(Exception):
    """Somebody other than the owner asked to read or resolve."""


def _require_owner(conn, owner_account_id: UUID) -> None:
    row = migrate.fetch_one(
        conn,
        "SELECT id FROM accounts"
        " WHERE id = %s AND is_owner = true AND deleted_at IS NULL",
        (owner_account_id,),
    )
    if row is None:
        raise NotOwner()


def leave_message(conn, body: str, *, clock) -> None:
    """Store one message. Returns nothing: there is nothing to tell the sender."""
    cleaned = (body or "").strip()
    if not cleaned:
        raise MessageRefused("Write a message first.")
    if len(cleaned) > MAX_LENGTH:
        raise MessageRefused(f"A message can be at most {MAX_LENGTH} characters.")
    # The ceiling and the insert are one statement, so a full inbox stores
    # nothing rather than being checked and then overrun.
    row = migrate.fetch_one(
        conn,
        "INSERT INTO recovery_messages (body, created_at)"
        " SELECT %s, %s"
        " WHERE (SELECT count(*) FROM recovery_messages WHERE resolved_at IS NULL) < %s"
        " RETURNING id",
        (cleaned, clock.now(), MAX_UNRESOLVED),
    )
    if row is None:
        raise InboxFull()


def list_messages(conn, owner_account_id: UUID, limit: int = 50) -> list[dict]:
    """The owner's inbox: unresolved first, then newest first."""
    _require_owner(conn, owner_account_id)
    rows = migrate.fetch_all(
        conn,
        "SELECT id, body, created_at, resolved_at FROM recovery_messages"
        " ORDER BY (resolved_at IS NOT NULL), created_at DESC LIMIT %s",
        (limit,),
    )
    return [dict(row) for row in rows]


def resolve(conn, owner_account_id: UUID, message_id: UUID, *, clock) -> bool:
    """Mark one message resolved. False when there is no such message.

    Resolving twice keeps the first date: the second press changes nothing.
    """
    _require_owner(conn, owner_account_id)
    migrate.execute(
        conn,
        "UPDATE recovery_messages SET resolved_at = %s, resolved_by = %s"
        " WHERE id = %s AND resolved_at IS NULL",
        (clock.now(), owner_account_id, message_id),
    )
    return migrate.fetch_one(
        conn, "SELECT id FROM recovery_messages WHERE id = %s", (message_id,)
    ) is not None
```

- [ ] **Step 4: Run it and watch it pass**

Run: `DBTEST backend.tests.test_auth_recovery_messages`
Expected: `Ran 8 tests`, `OK`, no `skipped`.

- [ ] **Step 5: Commit**

```bash
git add backend/auth/recovery_messages.py backend/tests/test_auth_recovery_messages.py
git commit -m "feat(#251): rule for recovery messages"
```

---

### Task 3: The public endpoint

**Files:**
- Create: `backend/routers/recovery_messages.py`
- Modify: `backend/main.py` (the import line `from backend.routers import auth, ranked`; the line `application.state.registration_limiter = RegistrationLimiter()`; the line `application.include_router(auth.router)`)
- Test: `backend/tests/test_recovery_messages_router.py`

**Interfaces:**
- Consumes: `recovery_messages.leave_message`, `MessageRefused`, `InboxFull` (Task 2); `backend.auth.rate_limit.RegistrationLimiter(per_client, per_client_window, total, total_window)` with `.is_allowed(key)` / `.record(key)`; `backend.auth.rate_limit._client_key(request)`.
- Produces: `POST /api/auth/recovery-messages` body `{"message": str}` → 201 empty body / 422 / 429; `application.state.recovery_message_limiter`.

The route lives on its own router, not `auth.router`, because `auth.router` runs a database sweep (`_purge_pending_deletions`) as a dependency before every handler, and this anonymous route must check its limiter before touching the database.

- [ ] **Step 1: Write the failing test**

```python
"""Leaving a recovery message over HTTP (issue #251).

The rule is tested in test_auth_recovery_messages.py. Here: anybody may
call it, it says nothing back, and it cannot be used to flood the table.
"""
import unittest

from fastapi.testclient import TestClient

from backend.auth.rate_limit import RegistrationLimiter
from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

URL = "/api/auth/recovery-messages"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessageRouterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.app = create_app()
        self.anon = TestClient(self.app, headers=BROWSER)

    def _stored(self):
        self.conn.rollback()
        return [
            row["body"] for row in migrate.fetch_all(
                self.conn, "SELECT body FROM recovery_messages ORDER BY created_at"
            )
        ]

    def test_a_signed_out_visitor_can_leave_a_message(self):
        answer = self.anon.post(URL, json={"message": "  I lost my login ID  "})
        self.assertEqual(answer.status_code, 201, answer.text)
        self.assertEqual(answer.content, b"")
        self.assertEqual(self._stored(), ["I lost my login ID"])

    def test_the_answer_is_the_same_whether_or_not_an_account_is_named(self):
        self.anon.post("/api/auth/register", json={"username": "dock_owl"})
        real = self.anon.post(URL, json={"message": "I am dock_owl"})
        fake = self.anon.post(URL, json={"message": "I am nobody_here"})
        self.assertEqual((real.status_code, real.content), (fake.status_code, fake.content))
        self.assertEqual(real.headers.get("content-length"), fake.headers.get("content-length"))

    def test_empty_and_overlong_messages_are_refused(self):
        for body in ({"message": "   "}, {"message": "x" * 501}, {}):
            self.assertEqual(self.anon.post(URL, json=body).status_code, 422)
        self.assertEqual(self._stored(), [])

    def test_the_fourth_message_in_an_hour_from_one_address_is_refused(self):
        for n in range(3):
            self.assertEqual(self.anon.post(URL, json={"message": f"m{n}"}).status_code, 201)
        fourth = self.anon.post(URL, json={"message": "m3"})
        self.assertEqual(fourth.status_code, 429)
        self.assertEqual(len(self._stored()), 3)

    def test_refused_messages_do_not_use_up_the_allowance(self):
        for _ in range(5):
            self.anon.post(URL, json={"message": ""})
        self.assertEqual(self.anon.post(URL, json={"message": "real"}).status_code, 201)

    def test_the_daily_total_is_capped(self):
        self.app.state.recovery_message_limiter = RegistrationLimiter(
            per_client=100, per_client_window=3600.0, total=2, total_window=86400.0
        )
        self.assertEqual(self.anon.post(URL, json={"message": "a"}).status_code, 201)
        self.assertEqual(self.anon.post(URL, json={"message": "b"}).status_code, 201)
        self.assertEqual(self.anon.post(URL, json={"message": "c"}).status_code, 429)

    def test_a_full_inbox_refuses_and_stores_nothing(self):
        migrate.execute(
            self.conn,
            "INSERT INTO recovery_messages (body) SELECT 'filler' FROM generate_series(1, 100)",
        )
        self.conn.commit()
        self.assertEqual(self.anon.post(URL, json={"message": "one more"}).status_code, 429)
        self.assertNotIn("one more", self._stored())

    def test_a_write_without_an_origin_is_refused_like_any_other(self):
        bare = TestClient(self.app)
        self.assertEqual(bare.post(URL, json={"message": "hi"}).status_code, 403)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `DBTEST backend.tests.test_recovery_messages_router`
Expected: failures with 404 (and 405) where 201/422/429 are expected.

If `test_a_write_without_an_origin_is_refused_like_any_other` expects the wrong code, read `backend/origin_guard.py` for the status it actually returns and use that number; the point of the test is only that the guard applies.

- [ ] **Step 3: Write the router**

`backend/routers/recovery_messages.py`:

```python
"""The one thing a locked-out player can do: leave the owner a message (#251).

Kept off ``auth.router`` on purpose. That router sweeps pending deletions
before every handler, which is database work; this route is anonymous, so
its limiter is checked before the database is touched at all.
"""
from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.auth import recovery_messages
from backend.auth.rate_limit import _client_key
from backend.db import pool, settings
from backend.ranked.clock import system_clock

router = APIRouter(prefix="/api/auth", tags=["auth"])

_CLOCK = system_clock()

TOO_MANY = "Too many messages; find the owner in person."


class RecoveryMessageRequest(BaseModel):
    # A ceiling on what is parsed at all. The real rule (500 after
    # trimming) lives in backend/auth/recovery_messages.py.
    message: str = Field(max_length=4000)


@router.post("/recovery-messages", status_code=status.HTTP_201_CREATED)
def leave_recovery_message(request: Request, payload: RecoveryMessageRequest):
    limiter = request.app.state.recovery_message_limiter
    client = _client_key(request)
    if not limiter.is_allowed(client):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY)
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
    with pool.checkout() as conn:
        try:
            recovery_messages.leave_message(conn, payload.message, clock=_CLOCK)
        except recovery_messages.MessageRefused as error:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=error.reason
            ) from None
        except recovery_messages.InboxFull:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=TOO_MANY
            ) from None
        conn.commit()
    # Only a stored message counts, as with sign-ups.
    limiter.record(client)
    # Nothing in the body: no id, no echo, the same bytes for every message.
    return Response(status_code=status.HTTP_201_CREATED)
```

In `backend/main.py`:

```python
from backend.routers import auth, ranked, recovery_messages as recovery_messages_router
```

directly under `application.state.registration_limiter = RegistrationLimiter()`:

```python
    # recovery messages from the sign-in screen (#251, owner caps: 3/hour
    # per address, 50/day in total); the same sliding-window rule
    application.state.recovery_message_limiter = RegistrationLimiter(
        per_client=3, per_client_window=3600.0, total=50, total_window=86400.0
    )
```

directly under `application.include_router(auth.router)`:

```python
    application.include_router(recovery_messages_router.router)
```

- [ ] **Step 4: Run it and watch it pass**

Run: `DBTEST backend.tests.test_recovery_messages_router`
Expected: `Ran 8 tests`, `OK`, no `skipped`.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/recovery_messages.py backend/main.py backend/tests/test_recovery_messages_router.py
git commit -m "feat(#251): public endpoint to leave a recovery message"
```

---

### Task 4: The owner routes

**Files:**
- Modify: `backend/routers/ranked.py` (import line `from backend.auth import eligibility, reauth, recovery`; new routes directly after `hand_over_recovery`, before `@router.get("/owner/selections")`)
- Test: `backend/tests/test_ranked_recovery_messages_router.py`

**Interfaces:**
- Consumes: `recovery_messages.list_messages`, `resolve`, `NotOwner` (Task 2); in `ranked.py`: `_current_account`, `get_db`, `_require_owner(account)`, `_utc(moment)`, `_CLOCK`.
- Produces:
  - `GET /api/ranked/owner/recovery-messages` → `{"messages": [{"id", "body", "created_at", "resolved_at"|null}], "open": int}`
  - `POST /api/ranked/owner/recovery-messages/{message_id}/resolve` → 204; 404 unknown or malformed id

- [ ] **Step 1: Write the failing test**

```python
"""The owner's recovery-message inbox over HTTP (issue #251)."""
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

LIST = "/api/ranked/owner/recovery-messages"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerRecoveryMessageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        # Deliberately no /api/auth/reauthenticate call: these routes must
        # work on an ordinary owner session.
        self.owner = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.owner, "the_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'",
        )
        self.conn.commit()
        self.player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.player, "dock_owl")
        self.anon = TestClient(create_app(), headers=BROWSER)

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login = client.post("/api/auth/login", json={"login_id": reg.json()["login_id"]})
        self.assertEqual(login.status_code, 200, login.text)

    def _leave(self, text):
        answer = self.anon.post("/api/auth/recovery-messages", json={"message": text})
        self.assertEqual(answer.status_code, 201, answer.text)

    def _resolve(self, client, message_id):
        return client.post(f"{LIST}/{message_id}/resolve")

    def test_a_signed_out_visitor_is_refused(self):
        self.assertEqual(self.anon.get(LIST).status_code, 401)
        self.assertEqual(self._resolve(self.anon, uuid4()).status_code, 401)

    def test_a_player_is_refused(self):
        self.assertEqual(self.player.get(LIST).status_code, 403)
        self.assertEqual(self._resolve(self.player, uuid4()).status_code, 403)

    def test_the_owner_reads_messages_without_reauthenticating(self):
        self._leave("first")
        self._leave("<b>second</b>")
        answer = self.owner.get(LIST)
        self.assertEqual(answer.status_code, 200, answer.text)
        body = answer.json()
        self.assertEqual(body["open"], 2)
        self.assertEqual(
            sorted(m["body"] for m in body["messages"]), ["<b>second</b>", "first"]
        )
        for message in body["messages"]:
            self.assertEqual(set(message), {"id", "body", "created_at", "resolved_at"})
            self.assertIsNone(message["resolved_at"])

    def test_resolving_marks_it_and_is_idempotent(self):
        self._leave("help")
        message_id = self.owner.get(LIST).json()["messages"][0]["id"]
        self.assertEqual(self._resolve(self.owner, message_id).status_code, 204)
        self.assertEqual(self._resolve(self.owner, message_id).status_code, 204)
        body = self.owner.get(LIST).json()
        self.assertEqual(body["open"], 0)
        self.assertIsNotNone(body["messages"][0]["resolved_at"])

    def test_an_unknown_or_malformed_id_is_not_found(self):
        self.assertEqual(self._resolve(self.owner, uuid4()).status_code, 404)
        self.assertEqual(self._resolve(self.owner, "not-a-uuid").status_code, 404)
```

- [ ] **Step 2: Run it and watch it fail**

Run: `DBTEST backend.tests.test_ranked_recovery_messages_router`
Expected: failures with 404 where 401/403/200/204 are expected.

- [ ] **Step 3: Add the routes**

In `backend/routers/ranked.py`, change the import:

```python
from backend.auth import eligibility, reauth, recovery, recovery_messages
```

and add after `hand_over_recovery`:

```python
# Recovery messages (#251): what a locked-out player typed on the sign-in
# screen. The rule lives in backend/auth/recovery_messages.py. No recent
# reauthentication here, unlike the recovery itself: reading a message and
# marking it resolved reveal no secret and grant nobody access.
@router.get("/owner/recovery-messages")
def list_recovery_messages(
    account: dict = Depends(_current_account), conn=Depends(get_db)
):
    _require_owner(account)
    try:
        rows = recovery_messages.list_messages(conn, account["id"])
    except recovery_messages.NotOwner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        ) from None
    return {
        "open": sum(1 for row in rows if row["resolved_at"] is None),
        "messages": [
            {
                "id": str(row["id"]),
                "body": row["body"],
                "created_at": _utc(row["created_at"]),
                "resolved_at": None if row["resolved_at"] is None
                else _utc(row["resolved_at"]),
            }
            for row in rows
        ],
    }


@router.post(
    "/owner/recovery-messages/{message_id}/resolve",
    status_code=status.HTTP_204_NO_CONTENT,
)
def resolve_recovery_message(
    message_id: str,
    account: dict = Depends(_current_account),
    conn=Depends(get_db),
):
    _require_owner(account)
    try:
        found = recovery_messages.resolve(
            conn, account["id"], UUID(message_id), clock=_CLOCK
        )
    except ValueError:
        found = False
    except recovery_messages.NotOwner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden"
        ) from None
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    conn.commit()
    return None
```

- [ ] **Step 4: Run it and watch it pass**

Run: `DBTEST backend.tests.test_ranked_recovery_messages_router`
Expected: `Ran 5 tests`, `OK`, no `skipped`.

- [ ] **Step 5: Commit**

```bash
git add backend/routers/ranked.py backend/tests/test_ranked_recovery_messages_router.py
git commit -m "feat(#251): owner routes to read and resolve recovery messages"
```

---

### Task 5: The form on the sign-in screen

**Files:**
- Modify: `src/auth.js`
- Test: `tests/forgot-login.test.mjs`

**Interfaces:**
- Consumes: `POST /api/auth/recovery-messages` (Task 3); inside `createAuthPanel`: `form`, `choices`, `closeForm(trigger)`, `showMessage(text, isError)`; module-level `api(method, path, body)` which returns `{ ok, status, data }` (status 0 when the server is unreachable).
- Produces: `export async function leaveRecoveryMessage(message)`; elements `#auth-forgot-btn`, `#forgot-message`, `#forgot-count`, `#forgot-send`, `#forgot-cancel`.

The rest of this panel is English-only today and stays that way (out of scope). The new strings are bilingual through a small table inside `auth.js`, read from the same storage key `src/i18n.js` uses (`sortTest.language.v1`), because `auth.js` may not import anything.

- [ ] **Step 1: Write the failing test**

```javascript
// "Forgot my login?" on the sign-in screen (issue #251). The form leaves the
// owner a message and nothing else: it must never say whether an account
// exists, and it must say the same fixed sentence for every accepted message.
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [auth], cleanup } = await loadAppModules(['src/auth.js']);
after(cleanup);
const source = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');

function fakeElement() {
  const children = new Map();
  const listeners = {};
  return {
    hidden: false, value: '', textContent: '', className: '', disabled: false,
    focus() {},
    set innerHTML(_markup) { children.clear(); },
    get innerHTML() { return ''; },
    querySelector(selector) {
      if (!children.has(selector)) children.set(selector, fakeElement());
      return children.get(selector);
    },
    addEventListener(type, handler) { listeners[type] = handler; },
    async fire(type) { await listeners[type]?.(); },
  };
}

async function openForm(fetchFn, language = null) {
  const calls = [];
  // Newer Node versions define localStorage as an accessor on globalThis, so
  // it is replaced by descriptor rather than by assignment.
  const originalFetch = globalThis.fetch;
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return fetchFn(); };
  Object.defineProperty(globalThis, 'localStorage', {
    value: { getItem: () => language }, configurable: true, writable: true,
  });
  const panel = fakeElement();
  auth.createAuthPanel(panel, () => {}, () => {});
  await panel.querySelector('#auth-forgot-btn').fire('click');
  const form = panel.querySelector('#auth-form');
  const restore = () => {
    globalThis.fetch = originalFetch;
    if (originalStorage) Object.defineProperty(globalThis, 'localStorage', originalStorage);
    else delete globalThis.localStorage;
  };
  return { panel, form, calls, restore };
}

const created = () => ({ ok: true, status: 201, headers: { get: () => null } });
const refused = (status) => () => ({ ok: false, status, headers: { get: () => null } });

test('the link opens the form in place of the entry choices', async () => {
  const { panel, form, restore } = await openForm(created);
  try {
    assert.equal(panel.querySelector('#auth-choices').hidden, true);
    assert.equal(form.hidden, false);
  } finally { restore(); }
});

test('sending posts the trimmed text and nothing else', async () => {
  const { form, calls, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = '  I am Sam, night sort  ';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/api/auth/recovery-messages');
    assert.equal(calls[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body), { message: 'I am Sam, night sort' });
  } finally { restore(); }
});

test('an empty message is not sent', async () => {
  const { panel, form, calls, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = '   ';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(calls.length, 0);
    assert.match(panel.querySelector('#auth-message').textContent, /Write a message/);
  } finally { restore(); }
});

test('success closes the form and says the owner recovers access in person', async () => {
  const { panel, form, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = 'help';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(form.hidden, true);
    assert.equal(panel.querySelector('#auth-choices').hidden, false);
    assert.match(panel.querySelector('#auth-message').textContent, /in person/);
  } finally { restore(); }
});

test('too many messages and a dead server each get their own sentence', async () => {
  for (const [fetchFn, expected] of [
    [refused(429), /Too many messages/],
    [() => { throw new Error('offline'); }, /Could not reach the server/],
    [refused(422), /could not be sent/],
  ]) {
    const { panel, form, restore } = await openForm(fetchFn);
    try {
      form.querySelector('#forgot-message').value = 'help';
      await form.querySelector('#forgot-send').fire('click');
      assert.match(panel.querySelector('#auth-message').textContent, expected);
      assert.equal(form.hidden, false, 'the text is kept so it can be sent again');
    } finally { restore(); }
  }
});

test('the new sentences are in Spanish when Spanish is chosen', async () => {
  const { panel, form, restore } = await openForm(created, 'es');
  try {
    form.querySelector('#forgot-message').value = 'ayuda';
    await form.querySelector('#forgot-send').fire('click');
    assert.match(panel.querySelector('#auth-message').textContent, /en persona/);
  } finally { restore(); }
});

test('every new English sentence has a Spanish one, and none is Portuguese', () => {
  const table = source.slice(source.indexOf('const FORGOT_ES'), source.indexOf('function forgotText'));
  const pairs = [...table.matchAll(/^\s*'((?:[^'\\]|\\.)+)':\s*\n?\s*'((?:[^'\\]|\\.)+)',?$/gm)];
  assert.ok(pairs.length >= 9, `expected the whole table, found ${pairs.length}`);
  for (const [, english, spanish] of pairs) assert.notEqual(english, spanish);
  assert.doesNotMatch(table, /\b(você|não|responsável|pessoalmente|esqueci)\b/i);
});

test('the form never reports on an account', () => {
  const body = source.slice(source.indexOf("'#auth-forgot-btn'"), source.indexOf("'#auth-guest-btn'"));
  assert.doesNotMatch(body, /result\.data/);
  assert.doesNotMatch(body, /username|#\$\{/);
  assert.match(body, /maxlength="500"/);
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `node --test tests/forgot-login.test.mjs`
Expected: failures — no request is made, `FORGOT_ES` is not found.

- [ ] **Step 3: Write the form**

In `src/auth.js`, after `fetchMe`:

```javascript
export async function leaveRecoveryMessage(message) {
  return api('POST', '/auth/recovery-messages', { message });
}

// The rest of this panel is English only. These are the sentences added with
// the recovery message (#251), in both of the app's languages. The table
// lives here, not in i18n.js, because this file is loaded on its own and
// imports nothing; the storage key is the one i18n.js keeps the choice in.
const FORGOT_ES = {
  'Forgot my login?':
    '¿Olvidaste tu acceso?',
  'Message for the owner':
    'Mensaje para el responsable',
  'Say who you are and what happened. The owner reads this and recovers your access in person. Nothing is recovered from this screen.':
    'Di quién eres y qué pasó. El responsable lee esto y recupera tu acceso en persona. Desde esta pantalla no se recupera nada.',
  'Send message':
    'Enviar mensaje',
  'Cancel':
    'Cancelar',
  'Write a message first.':
    'Escribe un mensaje primero.',
  'Message received. The owner recovers access in person: find them at work.':
    'Mensaje recibido. El responsable recupera el acceso en persona: búscalo en el trabajo.',
  'Too many messages for now. Find the owner in person.':
    'Demasiados mensajes por ahora. Busca al responsable en persona.',
  'Could not reach the server. Nothing was sent; try again in a moment.':
    'No se pudo contactar con el servidor. No se envió nada; inténtalo de nuevo en un momento.',
  'The message could not be sent. Find the owner in person.':
    'No se pudo enviar el mensaje. Busca al responsable en persona.',
};

function forgotText(source) {
  let spanish = false;
  try {
    spanish = globalThis.localStorage?.getItem('sortTest.language.v1') === 'es';
  } catch { /* no storage: English */ }
  return spanish ? FORGOT_ES[source] ?? source : source;
}
```

In the panel markup, directly under the `auth-register-btn` button:

```javascript
        <button id="auth-forgot-btn" class="auth-link" type="button">${forgotText('Forgot my login?')}</button>
```

Directly before `container.querySelector('#auth-guest-btn').addEventListener(`:

```javascript
  // A locked-out player cannot sign in, so this is the one thing they can
  // do here: leave the owner a message (#251). It recovers nothing and
  // looks nothing up, so every accepted message gets the same sentence.
  container.querySelector('#auth-forgot-btn').addEventListener('click', () => {
    choices.hidden = true;
    showMessage('');
    form.hidden = false;
    form.innerHTML = `
      <label class="field">
        <span>${forgotText('Message for the owner')}</span>
        <textarea id="forgot-message" class="glass-input" rows="4" maxlength="500"></textarea>
      </label>
      <p class="auth-note"><span id="forgot-count">0</span>/500</p>
      <p class="auth-note">${forgotText('Say who you are and what happened. The owner reads this and recovers your access in person. Nothing is recovered from this screen.')}</p>
      <button id="forgot-send" class="primary">${forgotText('Send message')}</button>
      <button id="forgot-cancel" class="ghost">${forgotText('Cancel')}</button>
    `;
    const box = form.querySelector('#forgot-message');
    const send = form.querySelector('#forgot-send');
    box.focus();
    box.addEventListener('input', () => {
      form.querySelector('#forgot-count').textContent = String(box.value.length);
    });
    send.addEventListener('click', async () => {
      const text = box.value.trim();
      if (!text) {
        showMessage(forgotText('Write a message first.'), true);
        return;
      }
      send.disabled = true;
      const result = await leaveRecoveryMessage(text);
      send.disabled = false;
      if (result.ok) {
        closeForm('#auth-forgot-btn');
        showMessage(forgotText('Message received. The owner recovers access in person: find them at work.'));
      } else if (result.status === 429) {
        showMessage(forgotText('Too many messages for now. Find the owner in person.'), true);
      } else if (result.status === 0) {
        showMessage(forgotText('Could not reach the server. Nothing was sent; try again in a moment.'), true);
      } else {
        showMessage(forgotText('The message could not be sent. Find the owner in person.'), true);
      }
    });
    form.querySelector('#forgot-cancel').addEventListener('click', () => closeForm('#auth-forgot-btn'));
  });
```

- [ ] **Step 4: Run the new test and the existing panel tests**

Run: `node --test tests/forgot-login.test.mjs tests/auth-client.test.mjs tests/auth-gate.test.mjs tests/security.test.mjs`
Expected: all pass. If `security.test.mjs` flags the new `innerHTML` assignment, read its rule: the markup above interpolates only fixed strings from `FORGOT_ES`, never user input; adjust the code to satisfy the rule rather than loosening the test.

- [ ] **Step 5: Commit**

```bash
git add src/auth.js tests/forgot-login.test.mjs
git commit -m "feat(#251): forgot-my-login message form on the sign-in screen"
```

---

### Task 6: The owner's screen

**Files:**
- Modify: `src/app.js` (`showOwnerTools`; new functions after `fillRecoveries`), `src/i18n.js` (the `ES` table)
- Test: `tests/recovery-messages-screen.test.mjs`

**Interfaces:**
- Consumes: `GET /api/ranked/owner/recovery-messages`, `POST …/{id}/resolve` (Task 4); in `app.js`: `labPage(html, tab, rerender)`, `esc(value)`, `t(source)`, `api(path)` (JSON or `null`), `apiSend(method, path, body)` (`{ ok, reason }`), `stopTick()`, `clock`, `showOwnerTools`, `showRecovery`.
- Produces: `showRecoveryMessages(message = null, bad = false)`, `fillRecoveryMessages(panel)`.

- [ ] **Step 1: Write the failing test**

```javascript
// The owner's recovery-message inbox (issue #251). A message is typed by
// somebody who is not signed in, so the screen treats it as untrusted text
// and says plainly that it proves nothing.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('Owner tools reaches the inbox and says when something is waiting', () => {
  const tools = fn('function showOwnerTools');
  assert.match(tools, /id="owner-messages"/);
  assert.match(tools, /addEventListener\('click', \(\) => showRecoveryMessages\(\)\)/);
  assert.match(tools, /\/ranked\/owner\/recovery-messages/);
  assert.match(tools, /owner-messages-count/);
});

test('message text is escaped, never rendered as markup', () => {
  const list = fn('async function fillRecoveryMessages');
  assert.match(list, /esc\(row\.body\)/);
  assert.doesNotMatch(list, /\$\{row\.body\}/);
});

test('the screen says a message proves nothing and where recovery happens', () => {
  const screen = fn('function showRecoveryMessages');
  assert.match(screen, /proves nothing about who wrote it/);
  assert.match(screen, /Access recovery/);
  assert.match(screen, /showRecovery\(\)/);
});

test('resolving is one guarded-free call and reloads the list', () => {
  const list = fn('async function fillRecoveryMessages');
  assert.match(list, /apiSend\('POST', `\/ranked\/owner\/recovery-messages\/\$\{.+\}\/resolve`\)/);
  assert.doesNotMatch(list, /apiSendOwner/);
  assert.match(list, /fillRecoveryMessages\(panel\)/);
});

test('the list shows text and dates, and nothing about any account', () => {
  const list = fn('async function fillRecoveryMessages');
  for (const forbidden of [/row\.username/, /row\.tag/, /row\.points/, /login_id/]) {
    assert.doesNotMatch(list, forbidden);
  }
  assert.match(list, /row\.created_at/);
  assert.match(list, /row\.resolved_at/);
});

test('a server that cannot be reached says nothing has been changed', () => {
  assert.match(fn('async function fillRecoveryMessages'), /Nothing has been changed/);
});

test('every new owner-screen sentence has a Spanish translation', () => {
  for (const sentence of [
    'Recovery messages',
    'Left on the sign-in screen by people who are locked out.',
    'A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.',
    'Open Access recovery',
    'Mark as resolved',
    'No messages.',
    'resolved',
    'received',
    'Could not load the messages. Nothing has been changed.',
    '1 message waiting.',
    'messages waiting.',
  ]) {
    assert.ok(i18n.includes(`'${sentence}':`), `no Spanish for: ${sentence}`);
  }
});
```

- [ ] **Step 2: Run it and watch it fail**

Run: `node --test tests/recovery-messages-screen.test.mjs`
Expected: failures — `owner-messages` and `fillRecoveryMessages` are missing.

- [ ] **Step 3: Write the screen**

In `showOwnerTools`, add this button directly after the `owner-recovery` button:

```javascript
      <button id="owner-messages" class="lab-choice" type="button">
        <span class="lab-choice-icon">✉</span>
        <span><strong>${esc(t('Recovery messages'))}</strong><small id="owner-messages-count">${esc(t('Left on the sign-in screen by people who are locked out.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
```

and, directly after the `owner-recovery` click listener:

```javascript
  view.querySelector('#owner-messages').addEventListener('click', () => showRecoveryMessages());
  api('/ranked/owner/recovery-messages').then((body) => {
    const n = body?.open ?? 0;
    if (n > 0) {
      view.querySelector('#owner-messages-count').textContent =
        n === 1 ? t('1 message waiting.') : `${n} ${t('messages waiting.')}`;
    }
  });
```

After the `fillRecoveries` function:

```javascript
// Recovery messages (#251). What a locked-out player typed on the sign-in
// screen. Anybody can type anything there, including somebody else's name,
// so this screen shows the text as text and says what it is worth: a reason
// to go and find a person. Recovering access is still the other screen.
function showRecoveryMessages(message = null, bad = false) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Recovery messages'))}</h1>
      ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
      <aside class="lab-disclaimer">${esc(t('A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.'))}</aside>
      <button id="msg-recovery" class="ghost">${esc(t('Open Access recovery'))}</button>
      <div id="msg-list"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="msg-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showRecoveryMessages(message, bad));
  view.querySelector('#msg-back').addEventListener('click', showOwnerTools);
  view.querySelector('#msg-recovery').addEventListener('click', () => showRecovery());
  fillRecoveryMessages(view.querySelector('#msg-list'));
  return view;
}

async function fillRecoveryMessages(panel) {
  const body = await api('/ranked/owner/recovery-messages');
  if (!body) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load the messages. Nothing has been changed.'))}</p>`;
    return;
  }
  const rows = body.messages ?? [];
  if (rows.length === 0) {
    panel.innerHTML = `<p class="lab-intro">${esc(t('No messages.'))}</p>`;
    return;
  }
  panel.innerHTML = `<ul class="approved">${rows.map((row) => `
    <li${row.resolved_at ? ' style="opacity:.6"' : ''}>
      <span class="approved-who">
        <b style="white-space:pre-wrap">${esc(row.body)}</b>
        <small>${esc(row.resolved_at
          ? `${t('received')} ${new Date(row.created_at).toLocaleString()} · ${t('resolved')} ${new Date(row.resolved_at).toLocaleDateString()}`
          : `${t('received')} ${new Date(row.created_at).toLocaleString()}`)}</small>
      </span>
      ${row.resolved_at ? '' : `<button class="ghost" data-resolve="${esc(row.id)}">${esc(t('Mark as resolved'))}</button>`}
    </li>`).join('')}</ul>`;
  panel.querySelectorAll('[data-resolve]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      const result = await apiSend('POST', `/ranked/owner/recovery-messages/${button.dataset.resolve}/resolve`);
      if (!result.ok) {
        button.disabled = false;
        button.textContent = result.reason || t('That did not work. Nothing has been changed.');
        return;
      }
      fillRecoveryMessages(panel);
    });
  });
}
```

In `src/i18n.js`, add to the `ES` table (before its closing `};`):

```javascript
  // The owner's recovery-message inbox (#251)
  'Recovery messages': 'Mensajes de recuperación',
  'Left on the sign-in screen by people who are locked out.': 'Dejados en la pantalla de acceso por personas que no pueden entrar.',
  'A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.': 'Un mensaje no prueba quién lo escribió. Busca a la persona, compruébala en persona y luego usa Recuperación de acceso.',
  'Open Access recovery': 'Abrir Recuperación de acceso',
  'Mark as resolved': 'Marcar como resuelto',
  'No messages.': 'No hay mensajes.',
  'resolved': 'resuelto',
  'received': 'recibido',
  'Could not load the messages. Nothing has been changed.': 'No se pudieron cargar los mensajes. No se ha cambiado nada.',
  '1 message waiting.': '1 mensaje en espera.',
  'messages waiting.': 'mensajes en espera.',
```

- [ ] **Step 4: Run every frontend test**

Run: `node --test tests/*.test.mjs`
Expected: all pass, including the existing `recovery-screen`, `owner-screen` and `security` tests. If `owner-screen.test.mjs` counts the Owner tools entries, update that count to include the new one.

- [ ] **Step 5: Commit**

```bash
git add src/app.js src/i18n.js tests/recovery-messages-screen.test.mjs
git commit -m "feat(#251): owner inbox for recovery messages"
```

---

### Task 7: Whole-suite verification and the pull request

**Files:** none new.

- [ ] **Step 1: Run the full backend suite with the database**

Run: `SORT_TESTER_TEST_DATABASE_URL="postgresql://localhost:5432/sort_tester_unittest_scratch" ./backend/.venv/bin/python3 -m backend.ci_tests`
Expected: the final JSON line has `"failures": 0, "errors": 0, "skipped": 0, "successful": true`. Any skip is a failure of this step.

- [ ] **Step 2: Run the full frontend suite**

Run: `node --test tests/*.test.mjs`
Expected: `fail 0`.

- [ ] **Step 3: See it work in a browser**

Start the app against the scratch database (the repository's `.claude/launch.json` entry, or the command in `backend/README.md`). Then, in order:
1. On the sign-in screen press "Forgot my login?", send a message, read the received sentence.
2. Send three more: the fourth is refused with the too-many sentence.
3. Register an account, make it the owner in the scratch database (`UPDATE accounts SET is_owner = true WHERE username_lower = '<name>'`), sign in, open Profile → Owner tools: the Recovery messages row shows the count.
4. Open it, mark one resolved, see it dim and the count drop.
5. Send a message containing `<img src=x onerror=alert(1)>` and confirm it is shown as text.
6. Switch the app to Spanish and repeat step 1.

Record what was seen, including anything that could not be exercised.

- [ ] **Step 4: Push and open the pull request**

```bash
git push -u origin feat/forgot-login-251
gh pr create --repo renilsonjr/Sort-Tester-Live --base codex/ranked-mode --head feat/forgot-login-251 \
  --title "feat(#251): forgot-my-login recovery messages" --body-file <(cat <<'EOF'
Closes #251.

A signed-out player can leave the owner one free-text message from the sign-in screen. The owner reads it in Owner tools and marks it resolved. **It recovers nothing**: access is still restored in person through Access recovery.

- New table `recovery_messages` (migration 0038): text, date, resolved date/by. No account, no network address.
- `POST /api/auth/recovery-messages`: public, 201 with an empty body, looks up no account. 500 characters; 3/hour per address, 50/day, 100 unresolved → 429.
- Owner: `GET /api/ranked/owner/recovery-messages`, `POST …/{id}/resolve`. Owner session, no reauth gate.
- Sign-in form and owner inbox, English and Spanish.

**Runs a migration on deploy (0038).**

Tests: <paste the ci_tests JSON line and the node --test summary>.
Seen in the browser: <paste the Step 3 record>.

To review before the pilot (#13): resolved messages are kept and may name a person; a message is not linked to an account, so deleting an account does not remove it.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)
```

Report the PR number and say plainly that it needs the owner's merge. Do not tick the checkboxes of #251 before it is merged.
