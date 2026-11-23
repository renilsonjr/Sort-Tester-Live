# Releases — what is running, and what you can go back to

Issue [#274](https://github.com/renilsonjr/sortquiz/issues/274). Deploy steps
live in [[rollout-runbook]]; this is the record of what each deploy actually
put there, which is what a rollback needs.

## What a version is here

A version is **three things that have to agree**, not a name:

| | Where |
|---|---|
| the string | `backend/version.py`, served by `/health` and shown at the foot of Profile → Settings |
| the commit | a git tag `v<version>` |
| the thing that runs | the image digest published from that commit |

If the three disagree, the number on screen is a guess. That is why the app
**asks `/health`** for the version instead of drawing one of its own: what a
player reads is what is serving them.

## The limit a rollback has

**Code goes back in a minute. The database does not.**

A migration that has already changed the tables does not undo itself, so a
rollback is only safe to a version that works with the **current** schema.
That is why every row below records its migration. Reading across the
`Migration` column tells you how far back you may go:

* same migration number → the older image can serve the current database;
* a lower migration number → **do not swap back**. Fix forward, or restore
  the database ([[restore-runbook]]), which also undoes everything players
  did since the restore point.

## How to read a rollback out of this table

1. Find the row that is live now.
2. Walk **up** while the `Migration` column stays the same.
3. The last such row is the oldest image you may safely go back to.
4. Deploy its digest the ordinary way ([[rollout-runbook]] §2).

The app runs in **single-revision mode**, so a rollback is a deploy of the
older digest — not a traffic split. `az containerapp ingress traffic set` is
refused outright on this app.

## The record

Newest first. `Version` is what `backend/version.py` held at that commit.

| Date | Version | Commit | Image digest | Migration | Revision | What went in |
|---|---|---|---|---|---|---|
| 2026-11-23 | 0.1.0-dev | `8fcb263` | `032b58de…` | 0039 | `desk1` | Desktop layout: sidebar, wider column, Home and leaderboard in two columns, keyboard in the Ranked quiz (#273) |
| 2026-11-23 | — | `675d9c8` | `3e029ae1…` | 0039 | `icons2` | The chosen profile icon drawn large enough to see (#272) |
| 2026-11-23 | — | `7f8b4f3` | `e975f5da…` | 0039 | `icons1` | Promotion ends at the first miss, the way back after leaving a match, sign out other devices, owner deletes an account, profile icons (#268–#272) |
| 2026-11-21 | — | `1194383` | `d241bd9e…` | 0038 | `forgot1` | Forgot-my-login recovery messages (#251) |
| — | — | — | `dd585b08…` | 0038 | `quiz1` | — |

Rows before `forgot1` were not recorded at the time; `quiz1`'s digest is kept
because it was the rollback target on 2026-11-23.

**Everything from `icons1` down is on migration 0039**, so any of those three
images can serve the database as it stands today. Going back to `forgot1` or
`quiz1` would put code that predates the `accounts.avatar` column in front of
a database that has it — which is harmless for a *dropped* column but not for
one the newer code writes, so treat 0038 as out of reach without a restore.

## Cutting a release

The owner decided on 2026-11-23 that **`v0.1.0` waits for issue #273 to
finish** — five screens still have no desktop layout. Until then the string
stays `0.1.0-dev`, which is the honest answer to "what is this?".

When the time comes:

1. Drop the `-dev` suffix in `backend/version.py`, in its own pull request.
2. Merge it, and let CI pass on `main`.
3. Tag that commit: `git tag -a v0.1.0 -m "Sort Quiz 0.1.0" && git push origin v0.1.0`.
4. Publish the image **from `main`** (the `publish` environment accepts no
   other branch) and deploy it.
5. Add the row here, and write the release notes on the tag from the issues
   it closed.
6. Bump the string to the next `-dev` so `main` never claims to be a release
   that has already shipped.

## What the numbers mean

The owner's rule (#274):

* **patch**, `0.1.0 → 0.1.1` — a fix. Nothing new to learn, nothing moved.
* **minor**, `0.1 → 0.2` — something new, or a screen that works differently.
* **major**, `0.x → 1.0` — reserved for when the app is past its pilot.

A migration does not force a bump of its own; it is recorded in the table
because it bounds the rollback, not because it changes the number.
