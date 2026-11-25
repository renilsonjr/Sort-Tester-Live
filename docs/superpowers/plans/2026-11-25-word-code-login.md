# Username + Word Code Login Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sign-in asks for **username + Quiz Code**, and new Quiz Codes are one simple English word plus two digits (for example `banana-48`) instead of 16 random characters. Username and tag stay tied to the account as today; only the access key changes.

**Why:** the owner wants a code people can remember. Saving it on phones also needs a username + secret pair: phone password managers did not offer to save a code-only login (owner test, 2026-11-25).

**Owner decisions (2026-11-25):** word + **2** digits; **English words only**, also in the Spanish UI. Login becomes username + code.

**Architecture:** the login request carries `username` and `login_id`. The server finds the account by `username_lower`, reads its one active credential and runs one Argon2 verification. It no longer looks up a credential by a hash of the code. The rate limiter keys on the account (username), not on the code. Old 16-character codes keep working, now entered together with the username. New codes are issued at sign-up and on recovery/owner reissue.

**Tech Stack:** FastAPI, psycopg + Alembic (raw SQL through `backend.db.migrate`), stdlib `unittest` against a real PostgreSQL scratch database, vanilla ES modules, `node --test`.

**Spec to update first:** `docs/superpowers/specs/2026-11-07-ranked-decision-record.md`, Decision 14, "Login credential (v2)": the login page then accepts **username + login ID**, not the login ID alone.

## Security notes (read before building)

- **Size of the guess space.** About 2,000 words × 100 two-digit endings ≈ 200,000 codes. Today's code has 32^16 ≈ 10^24 combinations. The new code is only safe **because the username is required and guesses at one account are limited**. Everything below protects that.
- **Rate limit per account, not per code.** Today the login limiter key is `client|lookup_key(code)` (`backend/auth/rate_limit.py`, `_login_rate_key`). With word codes that key gives every new guess a fresh bucket, so it never blocks guessing. The new key must be `client|username_lower`.
- **Per-account cap across all addresses.** A per-client key alone can be dodged by guessing from many addresses. Add a second, per-account counter (all clients). When it trips, that account's sign-in is paused for a while. Trade-off: someone who knows a username can pause that player's sign-in (the audit H-2 concern). **Open decision for the owner:** the numbers (proposed: 30 failures per day per account → 1-hour pause).
- **No code-derived lookup key for new codes.** `lookup_key` is an unsalted SHA-256 of the code. For a 200,000-code space anyone who reads the table could reverse it by trying every code. New credentials store a **random** `lookup_key` (`secrets.token_hex(16)`), which satisfies the existing `NOT NULL UNIQUE` without a migration. Login stops using `lookup_key`.
- **Same answer and timing for every failure.** Unknown username, wrong code and malformed input all give the same 401, and all run one Argon2 verification (dummy verifier when there is no account). This already exists in `check_login_candidates`; keep it.
- **Codes need not be unique.** Two accounts may both get `banana-48`. The username decides which account.

## Global Constraints

- Code format: `<word>-<dd>`, word lowercase a–z, 3–8 letters, from a curated English list in the repo (simple, common, nothing offensive, no names or brands). Two digits `00`–`99`. Chosen with `secrets`.
- Input normalization accepts both formats: trims spaces, is case-insensitive, and treats `banana48`, `Banana-48` and `banana 48` as the same code. The old 16-character Crockford format keeps its rules.
- UI copy in English and Spanish only. Never Portuguese. The words themselves are English in both languages.
- Real player accounts are live at sortquiz.app: no test logins, wipes or restores there. Test against the local scratch database only.
- Backend tests run only with the scratch database set; without it they skip silently and prove nothing:
  `SORT_TESTER_TEST_DATABASE_URL="postgresql://localhost:5432/sort_tester_unittest_scratch" ./backend/.venv/bin/python3 -m unittest <module> -v`
- Frontend tests: `node --test tests/<file>.test.mjs`. `src/auth.js` must stay import-free.
- Branch from `origin/main`; PRs target `main`. The owner merges. Publish only from `main`.

## Tasks

### Task 1: Update the spec (Decision 14)

- [ ] Change the "Login credential (v2)" bullet: login asks for username + login ID; new login IDs are one English word + two digits; old 16-character IDs stay valid until reissued.
- [ ] Record the security notes above (account-keyed limit, per-account cap, no code-derived lookup key).
- [ ] Owner reviews this before Task 2 starts.

### Task 2: Word list and code generator

**Files:** `backend/auth/wordlist.py` (new), `backend/auth/credentials.py`, `backend/auth/settings.py`, tests.

- [ ] Curate the English word list (target about 2,000 words; more words means more safety). Test: no duplicates, all lowercase a–z, 3–8 letters, list size at or above the agreed minimum.
- [ ] `generate_login_id` returns `<word>-<dd>` using `secrets.choice` and `secrets.randbelow(100)`. Test: format, and that many draws spread across words and digits.
- [ ] `normalize_login_id` accepts both formats and rejects anything else with `ValueError`. Tests for both shapes, mixed case, spaces and dashes.

### Task 3: Login by username + code

**Files:** `backend/auth/service.py`, `backend/routers/auth.py`, `backend/auth/rate_limit.py`, DB tests.

- [ ] `LoginRequest` gets `username`. Find the account by `username_lower` (and `deleted_at IS NULL`), read its active credential, then verify with Argon2. The dummy verification stays on every failure path.
- [ ] Limiter key becomes `client|username_lower`. Add the per-account cap from the security notes.
- [ ] New credentials (sign-up, `issue_new_login_id`, owner reissue) store a random `lookup_key`.
- [ ] DB tests: a new account signs in with username + new code; an old 16-character account signs in with username + old code; wrong username, wrong code, deleted account and revoked credential all give the same 401; the per-client limit blocks guesses at one account even when each guess is a different code; the per-account cap trips across clients.
- [ ] Reauth (`backend/auth/reauth.py`) and deletion (`backend/auth/deletion.py`) already know the account; check that they accept both code formats.

### Task 4: Login screen and sign-up screen

**Files:** `src/auth.js`, `index.html`, `src/i18n.js` if needed, tests.

- [ ] Login form: username field (`autocomplete="username"`) above the Quiz Code field (`autocomplete="current-password"`), keeping the Show/Hide button from PR #467.
- [ ] Sign-up result screen shows the new code; the Continue step submits a form holding username + code (`autocomplete="new-password"`) so the browser can offer to save it at creation.
- [ ] Error text stays generic ("Invalid username or Quiz Code"). English and Spanish.
- [ ] Update tests in `tests/auth-gate.test.mjs`, `tests/forgot-login.test.mjs` and others that post `login_id` alone.

### Task 5: Help text and manual

- [ ] Update wording that says "log in with your Quiz Code only" (screens, the how-to-play manual, `tests/quiz-code-wording.test.mjs`).

### Task 6: Release

- [ ] Run the full backend suite against the scratch database, and the frontend suite.
- [ ] Owner merges to `main`, publishes, then deploys the digest.
- [ ] Tell players: from now on, sign in with **username + Quiz Code**. Their current code still works.
- [ ] Afterwards, check on a phone that the browser offers to save.

## Open decisions for the owner

1. Per-account cap numbers (proposed: 30 failures/day → 1-hour pause).
2. Minimum word-list size (proposed: 2,000).
3. Whether to give existing players a new word code on request through the owner reissue, or only to new accounts.
