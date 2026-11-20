# Deletion list — design

Date: 2026-11-20. Issue: #13 (Fatia B). Owner-approved in conversation on
2026-11-20. Related: `infra/azure/restore-runbook.md`, Decision 14 in
`2026-11-07-ranked-decision-record.md`.

## Problem

A point-in-time restore rewinds the database. The staging rehearsal showed an
account deleted 64 seconds after the restore point coming back, active. The
owner accepted the 7-day backup window on condition that every restore
re-applies the deletions made after the restore point. That needs a record the
restore cannot rewind, so it cannot live in the database.

## Owner decisions

1. **Where:** Azure Blob Storage. Logs cannot honour 7 days (30-day minimum
   retention); a second database is out of proportion.
2. **Contents:** account id and deletion time. Nothing else. This is an
   approved, minimal exception to Decision 14.
3. **Lifetime:** 7 days, enforced by a storage lifecycle rule, not by app
   code. The rule runs about once a day, so a note may live up to about 8
   days. Accepted.
4. **When the note cannot be written:** the deletion is refused. The player
   sees "try again shortly" and nothing changes. The app says "deleted" only
   when the deletion is restore-proof.

## Design

### One module

`backend/auth/deletion_list.py` is the only code that talks to Blob Storage.

- `record(account_id, deleted_at)` writes one blob. Name: the account id.
  Body: the deletion time in ISO 8601 with timezone. Raises
  `DeletionListUnavailable` unless the service answers 201.
- `forget(account_id)` removes a note whose deletion did not happen. Best
  effort; never raises; a note it could not remove is logged at ERROR with
  the account id, because a restore would otherwise delete a live account.
- Only a UUID can become a blob name.

### Authentication

The app's existing user-assigned managed identity, asking for a token for
`https://storage.azure.com`. No account key, no SAS. `entra_token` now serves
more than one resource, each with its own cached token. Standard library
only, so the container's dependency set does not grow.

### Order inside a deletion

`request_deletion` is the single code path that deletes an account.

1. Lock the account row; refuse the owner or a wrong login ID (unchanged).
2. `record(...)`. On failure: roll back, raise `DeletionListUnavailable`; the
   route answers 503.
3. Mark deleted, revoke sessions and credentials, drop unfinished attempts,
   keep the season marker, commit (unchanged).
4. If step 3 fails: roll back, `forget(...)`, re-raise.

The row lock is held during the storage call, bounded by a 5-second timeout.

### Configuration

`SORT_TESTER_DELETION_LIST_URL`:

| Value | Meaning |
|---|---|
| unset / empty | Off. Development and tests. |
| `https://<account>.blob.core.windows.net/<container>` | On. |
| `disabled` | Off on purpose, for a hosted environment with fictional data only. |

Startup check (`check_policy`): in managed-identity mode an **empty** value
stops the app from starting. A forgotten setting would otherwise switch the
list off silently until the day of a restore. A malformed value stops startup
in every mode; a URL with a query string is refused so a SAS token never ends
up in configuration, and the value is never echoed in the error.

`disabled` was added during implementation: the staging app already runs in
managed-identity mode, so without an explicit opt-out the next image deploy
would not start until the storage account exists.

## Residual risks

- **Crash between note and commit.** If the process dies after step 2 and
  before the commit, a note exists for an account that was not deleted, and
  `forget` never runs. A restore would then delete that account. The player
  did request deletion with a valid login ID seconds earlier, so the harm is
  bounded, but the runbook should cross-check a note against the live
  database when one is available.
- **Lock held during a network call.** Up to 5 seconds per deletion on one
  account row. Acceptable at pilot scale.
- **Mocks are not proof.** The tests use a fake transport. #84 showed that
  green mocks can hide a hosting mismatch. The feature is unverified until a
  real deletion writes a real blob on staging.

## Not in this change

Each needs separate owner approval:

- Storage account (Bicep): no public network access, shared-key access off,
  lifecycle rule deleting blobs 7 days after creation, a role assignment that
  lets the app identity write and delete blobs in this one container only.
- Enabling on staging and proving it: delete a test account, see the note,
  rehearse the restore reading the real list.
- Runbook step 4 reading the list with one command.
- Player-facing wording about the 7-day completion delay.
