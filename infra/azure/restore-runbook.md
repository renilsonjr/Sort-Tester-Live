# Database restore runbook — issue #13, Fatia B

Status: rehearsed on fictional-data Azure staging on 2026-11-19/20 up to and
including "re-apply deletions". Repointing the app at a restored server is
**not rehearsed**. The deletion list this runbook depends on is **not built
yet**. Not approved for a pilot with employee data until both exist.
Related: [[db-runtime-role]], [[shared-resource-locks]],
[[../../docs/superpowers/specs/2026-11-07-ranked-decision-record]].

## Why a restore is dangerous here

A point-in-time restore brings the database back as it was at the chosen
moment. Any account a player deleted **after** that moment comes back, active
and able to log in. The rehearsal showed this: an account deleted 64 seconds
after the restore point was present again with `deleted_at` empty.

The owner accepted the 7-day backup window on one condition: **every restore
re-applies the deletions that happened after the restore point before the
restored database serves anyone.** A restore that skips step 4 breaks a
promise made to players (Decision 14).

## What was measured

| Measure | Result |
|---|---|
| Restore duration, run 1 | 9 min 06 s |
| Restore duration, run 2 | 10 min 10 s |
| Restore-point lag accepted by Azure | 98 s |

Near-empty staging database. Time to repoint the app is not included and the
duration will grow with data. The proposed targets (≤15 min data loss, ≤1 h
restore) are still unapproved.

## Before you start

- Only the owner runs these commands, from a private Azure Cloud Shell.
- Decide the restore point in UTC. Write it down; step 4 needs it.
- Pick a **new** server name. A deleted server's name stays reserved for a
  while; reusing it fails with `Specified server name is already used`.
- The restored server costs money while it exists.
- Never restore over, or delete, the source server. It carries a
  `CanNotDelete` lock; leave it.

## Step 1 — restore into a new server

```sh
RG=<resource-group>; SRC=<source-server>; T=<new-server-name>
RESTORE_POINT="<YYYY-MM-DDTHH:MM:SSZ>"
echo "START $(date -u +%H:%M:%S) UTC"
az postgres flexible-server restore -g $RG -n $T --source-server $SRC --restore-time "$RESTORE_POINT" -o none
az postgres flexible-server show -g $RG -n $T --query "{name:name, state:state, public:network.publicNetworkAccess}" -o table
echo "END $(date -u +%H:%M:%S) UTC"
```

The command is silent for about ten minutes. Expected: `Ready`, public access
`Disabled`. The restored server has **no private endpoint**; nothing can reach
it yet, including the app.

## Step 2 — open the restored server to the operator only

```sh
az postgres flexible-server update -g $RG -n $T --public-access Enabled -o none
MYIP="$(curl -s https://ifconfig.me)"
az postgres flexible-server firewall-rule create -g $RG -s $T --name operator-temp --start-ip-address "$MYIP" --end-ip-address "$MYIP" -o none
export PGHOST=$T.postgres.database.azure.com PGPORT=5432 PGDATABASE=sort_tester_app PGUSER='<entra-admin-upn>' PGSSLMODE=verify-full PGSSLROOTCERT=system
export PGPASSWORD="$(az account get-access-token --resource https://ossrdbms-aad.database.windows.net --query accessToken -o tsv)"
```

One IP, one rule. The Entra administrator of the source server can log in to
the restored one; no database password is needed. The token lasts about an
hour; re-run the last line if the connection is refused later.

## Step 3 — confirm what came back

```sh
psql -X -v ON_ERROR_STOP=1 -c "SELECT now() AS restored_now, (SELECT max(created_at) FROM accounts) AS newest_account, (SELECT count(*) FROM accounts) AS accounts, (SELECT count(*) FROM accounts WHERE deleted_at IS NOT NULL) AS pending_purge;"
```

`newest_account` must be at or before the restore point. If it is later, stop:
this is not the restore you asked for.

## Step 4 — re-apply deletions (mandatory)

Take from the deletion list every entry whose deletion time is **after the
restore point**. For each one, run the block below with its account id and
deletion time. It repeats what `backend/auth/deletion.py` does, minus the
login-ID check, which the player already passed.

```sh
psql -X -v ON_ERROR_STOP=1 -v acct='<account-id>' -v at='<deletion-time-utc>' <<'SQL'
BEGIN;
UPDATE accounts SET deleted_at = :'at' WHERE id = :'acct' AND deleted_at IS NULL AND NOT is_owner;
UPDATE sessions SET revoked_at = :'at' WHERE account_id = :'acct' AND revoked_at IS NULL;
UPDATE login_credentials SET revoked_at = :'at' WHERE account_id = :'acct' AND revoked_at IS NULL;
DELETE FROM attempts WHERE account_id = :'acct' AND state <> 'finalized';
INSERT INTO season_markers (roster_reference, season, ineligible)
  SELECT pl.roster_reference, s.id::text, true
  FROM participant_links pl, (SELECT id FROM seasons ORDER BY opened_at DESC LIMIT 1) s
  WHERE pl.account_id = :'acct'
  ON CONFLICT (roster_reference, season) DO UPDATE SET ineligible = true;
COMMIT;
SQL
```

The first `UPDATE` must report `UPDATE 1`. `UPDATE 0` means the account is not
in the restored data (created after the restore point) or was already marked;
check which before moving on.

Then purge once, and verify:

```sh
psql -X -v ON_ERROR_STOP=1 <<'SQL'
DELETE FROM accounts WHERE deleted_at IS NOT NULL RETURNING id AS purged;
SELECT count(*) AS pending_purge_left FROM accounts WHERE deleted_at IS NOT NULL;
SQL
```

Every id from the list must appear under `purged`, and `pending_purge_left`
must be `0`. Extra ids are accounts that were already pending at the restore
point; purging them is correct.

Limits of this step, stated plainly:

- The `season_markers` insert was **not** exercised in the rehearsal (the test
  account had no participant link). It also uses the newest season in the
  restored data, which is wrong if a season changed between the deletion and
  the restore point. Check by hand if a season boundary falls in that gap.
- If an account both registered and deleted after the restore point, there is
  nothing to re-apply; it does not exist in the restored data.

## Step 5 — only then, let the app use it

Not rehearsed. Before the restored database serves players it needs, at
least: a private endpoint, public access back to `Disabled`, the firewall rule
removed, the app's managed-identity role present (roles are restored with the
server; verify with a login from the app), and the app's
`SORT_TESTER_DATABASE_URL` pointed at the new host. Write and rehearse this
before the pilot.

## Step 6 — clean up

For a rehearsal, or once the restored server is no longer needed:

```sh
unset PGPASSWORD
az postgres flexible-server delete -g $RG -n $T --yes
az postgres flexible-server list -g $RG --query "[].{name:name, state:state, public:network.publicNetworkAccess}" -o table
```

`delete` prints nothing on success, and also nothing if the server never
existed. **Always run the `list` and read it**: only the expected servers,
each `Ready` with public access `Disabled`.

## The deletion list (not built yet)

Step 4 depends on a list that lives **outside the database**, because a
restore rewinds everything inside it. Owner decision on #13:

- Contents: account id and deletion time, nothing else.
- Kept for 7 days (the backup retention), then removed.
- Backup retention stays at 7 days; raising it requires revisiting this.
- A deletion is only "completed" for the player after those 7 days.
- This is an approved, minimal exception to Decision 14.

Until it exists, a real restore cannot honour deletions, and this runbook is a
rehearsal procedure only.

## Still open

- Deletion list: design, build, test.
- Step 5 rehearsal and end-to-end recovery time.
- Run the whole runbook on the separate pilot environment.
- Geo-redundant backup (only settable when a server is created).
- Owner approval of the data-loss and restore-time targets.
- Player-facing wording about the 7-day completion delay.
