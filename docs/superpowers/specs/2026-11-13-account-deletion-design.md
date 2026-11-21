# Auth follow-ups — self-service account deletion (Issue #47, slice 3)

Third slice of #47. A player deletes their own account. Rules come from the
security/operations design (deletion, Q10) and the decision record
(Decision 14): recent login-ID reauthentication, an explicit acknowledgment,
no undo once accepted, sessions revoked, the active attempt ended without a
fabricated score, the account inaccessible and deletion pending until purge
finishes, a full wipe of account-owned data, other players' records preserved,
and only a minimal season-ineligibility marker kept.

## Part A — the request and acceptance

`POST /api/auth/account/delete` with `{"login_id", "acknowledge"}`.

| Situation | Answer |
|---|---|
| No session | 401 |
| `acknowledge` not true | 422, nothing changes |
| Login rate limit already reached for the address | 429 |
| Login ID wrong for this account | 403, nothing changes; counted as a failed login |
| The owner account | 409: the sole owner cannot be deleted |
| Accepted | 202 `{"status": "accepted"}`, session cookie cleared |

Typing the login ID in the delete request itself is the reauthentication: it
is checked at that moment, which is stricter than "within five minutes".
SameSite=Lax session cookies already stop a cross-site POST from carrying the
session.

`backend/auth/deletion.py`: `request_deletion(conn, account_id, login_id, *,
clock)`. In one transaction, with the account row locked:

1. Refuse the owner (`OwnerAccountError`) and a wrong login ID
   (`WrongLoginIdError`), changing nothing.
2. Set `accounts.deleted_at`: the account is inaccessible and pending purge.
3. Revoke every session and login credential of the account.
4. Delete the account's attempts that are not finalized. The active attempt
   ends without preserving a score; no Quit penalty is fabricated and no other
   player's points change.
5. If the account has a participant link, save a season marker: its roster
   reference, the current season's id and `ineligible = true`.

`get_account_by_session` also ignores accounts with `deleted_at` set.

## Part B — the purge

`purge_deleted_accounts(conn) -> int` deletes every account with `deleted_at`
set; the database cascades remove its credentials, sessions, emails,
participant link, balance, attempts, answers, settlements, balance history,
connection events and flags. Shared question versions and other players'
records stay. Season markers have no account key and stay. Auth and ranked
requests run it first, like the other sweeps.

## Not claimed

Deletion is never reported as completed: backups and outside providers do not
exist yet, and the rules allow "completed" only after verified primary,
provider and backup erasure (#13, #41). Prize withdrawal and marker expiry at
prize finalization are #12. Cancelling queued email is #27; there is none.

## Testing (TDD, live scratch PostgreSQL)

- Part A: 401; 422 without acknowledgment; 403 for a wrong login ID with the
  account still usable; 409 for the owner; on acceptance the session no
  longer works, the old login ID no longer logs in, the running attempt is
  gone and another player's attempt is untouched; a marker with a participant
  link and none without.
- Part B: after the purge nothing of the account remains in any table, the
  marker remains, another player's attempts, settlements and balance remain,
  and shared question versions remain.
