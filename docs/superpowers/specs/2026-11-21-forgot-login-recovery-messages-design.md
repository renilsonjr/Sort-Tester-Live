# "Forgot my login" — recovery messages to the owner (issue #251)

Design approved by the owner on 2026-11-21. Fictional-data staging. This is an
app feature; it does not touch infrastructure and does not approve or satisfy
any gate of the pilot (#13).

## Problem

A player who has lost their login ID cannot sign in, so they cannot use
anything that needs a session (support tickets, #26). Recovery (#11,
`backend/auth/recovery.py`) is opened by the owner, in person, for an account
the owner has already identified. There is no way for the player to tell the
owner, from inside the app, "I am locked out". By design there is no email.

The login ID cannot be read back by anyone: only its Argon2id hash and a lookup
key are stored (`backend/auth/credentials.py`). Recovery issues a *new* ID,
shown once. Nothing here changes that.

## Decisions (owner, 2026-11-21)

1. The button **stores a message for the owner**. It is not self-service
   recovery and not only an instruction screen.
2. The message is **one free-text field**. No username, tag or other structured
   field is asked for.
3. A handled message is **marked resolved and kept** (date and who), not
   deleted.
4. Caps: **500 characters**, **3 messages per hour per network address**.
5. The owner reads the messages inside the existing **Owner tools** screen.

## What is built

### 1. Sign-in screen (player, signed out)

- A "Forgot my login?" link on the sign-in screen opens a small form: one
  textarea (500 characters, counter shown) and a send button.
- After a successful send the form is replaced by one fixed sentence: the
  message was received, and access is recovered by the owner in person.
- The answer is the **same for every accepted message**. The form never says
  whether any account matches what was typed: nothing is looked up at all.
- A 429 shows a fixed "too many messages, find the owner in person" sentence;
  an unreachable server shows the app's usual could-not-send sentence.
- Copy in **English and Spanish** through `src/i18n.js`. No Portuguese.

### 2. Public endpoint

`POST /api/auth/recovery-messages`, body `{ "message": string }`, no session.

- Trimmed; empty after trimming or longer than 500 characters → 422.
- Success → 201 with an empty body. No id, no echo.
- Rate limits, checked before any database work, in memory per application
  instance like the sign-up limiter:
  - 3 per hour per client key (`_client_key`, the same address rule the
    sign-up limiter uses);
  - 50 per day in total;
  - both → 429.
  Reuses `RegistrationLimiter` with these numbers as a second instance on
  `application.state` (`recovery_message_limiter`). It is the same
  sliding-window rule; no new limiter class.
- A ceiling of **100 unresolved messages**: at the ceiling the endpoint answers
  429 and stores nothing, so the table cannot be flooded across restarts or
  from many addresses.
- The existing origin guard applies to it like any other write.

Known consequence, accepted: players at the workplace share one network
address, so the fourth locked-out player within an hour is told to find the
owner in person. That is the fallback anyway.

### 3. Storage

New table `recovery_messages`, migration `0038`:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | uuid, primary key | `gen_random_uuid()` |
| `body` | text, not null | CHECK: 1–500 characters |
| `created_at` | timestamptz, not null | default `now()` |
| `resolved_at` | timestamptz | null while open |
| `resolved_by` | uuid → `accounts(id)` | `ON DELETE SET NULL` |

CHECK: `resolved_by` may be set only when `resolved_at` is set. Index on
`created_at DESC`.

It is deliberately **not** `recovery_requests`. That table records the owner
standing in front of an identified account (`account_id` and `opened_by` are
required). A message comes from nobody in particular: there is no account to
reference and none is guessed. The network address is **not stored**.

### 4. Rule module

`backend/auth/recovery_messages.py`, same shape as `recovery.py` (the rule
lives in the module, the router only carries it over HTTP):

- `leave_message(conn, body, *, clock)` — validates, enforces the unresolved
  ceiling, inserts.
- `list_messages(conn, owner_account_id, limit=50)` — owner only; open ones
  first, then newest first.
- `resolve(conn, owner_account_id, message_id, *, clock)` — owner only; sets
  `resolved_at`/`resolved_by`; resolving twice is a no-op, not an error.

### 5. Owner side

- `GET /api/ranked/owner/recovery-messages` and
  `POST /api/ranked/owner/recovery-messages/{id}/resolve`, beside the existing
  `/owner/recoveries` routes.
- Owner session required (403 otherwise). **No recent-reauth (428) gate**:
  reading a message and marking it resolved reveal no secret and grant no
  access, unlike opening or handing over a recovery.
- In **Owner tools**, a new entry "Recovery messages" with a count of open
  ones. The screen lists each message as plain text (escaped, never rendered
  as HTML), its date, and a "Mark as resolved" button; resolved ones are shown
  dimmed with their date. A line at the top says what to do next: find the
  person, then use Access recovery.

## What does not change

- Restoring access is still `open_request` → `hand_over`: owner, in person,
  trusted roster link older than the request, new login ID shown once.
- No email, phone or third-party service. No outbound call of any kind.
- A message proves nothing about who wrote it. The owner screen says so.

## Error handling

| Case | Answer |
| --- | --- |
| Empty / over 500 characters | 422 |
| Per-address or daily cap, or 100 unresolved | 429 |
| Not signed in on an owner route | 401 |
| Signed in, not the owner | 403 |
| Unknown message id on resolve | 404 |

## Testing

Backend (`backend/tests/`, run through `backend.ci_tests`, real PostgreSQL):

- message stored; trimmed; empty and 501-character bodies refused; 500 accepted;
- response body carries nothing; no account lookup happens (a message naming an
  existing and a non-existing username get identical answers);
- fourth message in an hour from one key → 429; other key still accepted;
  daily cap; unresolved ceiling;
- list and resolve refused for a signed-out caller and a non-owner; work for the
  owner without reauth; resolve is idempotent; unknown id → 404;
- deleting the resolving account leaves the message with `resolved_by` null;
- migration up and down.

Frontend (`tests/*.test.mjs`): the link opens the form; send posts the trimmed
text; success, 429 and unreachable-server states show their fixed sentences;
the owner list escapes message text; every new string has EN and ES.

## Limits and follow-ups

- Limiter counts are in memory and per instance, like the sign-up limiter:
  they reset on restart. The unresolved ceiling in the database is the
  restart-proof bound.
- Free text can contain a person's name and it is kept after resolving (owner
  decision 3). Whether resolved messages should expire must be **reviewed
  before the pilot (#13)**, together with the deletion-list rules: a message is
  not linked to an account, so deleting an account does not remove a message
  that names it.
- No reply channel to the player, by design.
