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
| 2026-11-23 | **0.1.0** | `0b294fe` | `79799130…` | 0039 | `v010` | **Release 0.1.0**, tagged `v0.1.0`. Plus resolved recovery messages deleted after 30 days (#364) and a finishing pass (#343, #348, #349) |
| 2026-11-23 | 0.1.0-dev | `db3a914` | — | 0039 | — | Documentation only (#362): the real digests and why this table is the only way back. Never deployed on its own |
| 2026-11-23 | 0.1.0-dev | `fd017f3` | `9ddea543…` | 0039 | `polish1` | The five desktop screens that had none, the sidebar and shell fixes, the polish pass, and this version record (#273, #274, #341, #342, #344, #360) |
| 2026-11-23 | — | `26e0611` | `c201053c…` | 0039 | `limits1` | Quiz Code check limits and dependency updates |
| 2026-11-23 | — | `8fcb263` | `032b58de…` | 0039 | `desk1` | Desktop shell: sidebar, wider column, Home and leaderboard in two columns, keyboard in the Ranked quiz (#273) |
| 2026-11-23 | — | `675d9c8` | `3e029ae1…` | 0039 | `icons2` | The chosen profile icon drawn large enough to see (#272) |
| 2026-11-23 | — | `7f8b4f3` | `e975f5da…` | 0039 | `icons1` | Promotion ends at the first miss, the way back after leaving a match, sign out other devices, owner deletes an account, profile icons (#268–#272) |
| 2026-11-23 | — | `6b4a966` | `dd585b08…` | 0038 | `quiz1` | — |

Rows before `quiz1` were not recorded at the time.

**Everything from `icons1` down is on migration 0039**, so any of those five
images can serve the database as it stands today. `quiz1` is 0038: it predates
the `accounts.avatar` column, so treat it as out of reach without a restore.

## Why this table is the only way back

**Azure keeps no old revisions.** Checked on 2026-11-23: the app is in
`Single` revision mode with no retention set, and `az containerapp revision
list` returned **one** row — the active one. Every earlier revision was
removed. So "roll back to the previous revision" is not a thing that can be
done here: the revision is gone, and only the **image in the registry**
survives.

That makes this table the rollback path, not a convenience. A row missing
from it is a version you cannot return to without digging.

### Recovering a digest that was never written down

The publish workflow prints it, and GitHub keeps the log:

```sh
gh run list --workflow "App image publish" --limit 10 --json databaseId,headSha,createdAt,conclusion
gh run view <id> --log | grep -oE "imageSha256=[0-9a-f]{64}"
```

That is how `limits1`'s digest was recovered on 2026-11-23, after it had
already been deleted from Azure. The workflow log outlives the revision, so
it — not a note taken at deploy time — is the record to trust.

## Cutting a release

**`v0.1.0` was cut on 2026-11-23**, once #273 closed, and is live as revision
`v010`. The string on `main` is now `0.1.1-dev`: the next change is a patch
until something says otherwise, and `main` must never claim to be a release
that has already shipped.

The steps, for next time:

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
