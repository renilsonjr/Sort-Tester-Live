# Database restore runbook — issue #13, Fatia B

Status: rehearsed on fictional-data Azure staging on 2026-11-19/20 up to and
including "re-apply deletions". On 2026-11-20 a third restore was re-applied
from the **real deletion list**: the command in step 4 named the one account
deleted after the restore point, and that id and time alone were enough to
erase it again. The same day a fourth restore was served by the staging app
(step 5) and then rolled back. The steps have **not** been run together as one
recovery, and never on the pilot environment. Not approved for a pilot with
employee data until the items under "Still open" are done.
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
| Restore duration, run 4 | 7 min 08 s |
| Restore-point lag accepted by Azure | 98 s |
| Run 4: restore start to app confirmed on the restored data | 20 min 06 s |

Near-empty staging database. A third restore (2026-11-20, real-list rehearsal)
succeeded but its end time was not captured. The 20 minutes include the
operator pasting each command by hand and **exclude** steps 2 to 4, which run
4 skipped. Durations will grow with data. The proposed targets (≤15 min data loss, ≤1 h
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

First read the deletion list. The storage account has no public network
access, so the list is read from inside the app's container, which sits in
the private network and already holds the identity allowed to read it:

```sh
az containerapp exec -g $RG -n <container-app> \
  --command "python -m backend.auth.deletion_list_cli --after $RESTORE_POINT"
```

It prints one line per accepted deletion at or after the restore point,
oldest first: the account id, a tab, the deletion time. It only reads; it
does not touch the database, so it works while the database is down.

Read the last lines, not only the list:

- `N of M readable notes are at or after ...` — the count you must re-apply.
- `error: ...` and no list — the list could **not** be read. This is not an
  empty list. Stop and use the emergency procedure below.
- `WARNING: ... malformed note(s)` — some notes could not be understood.
  Each may be a deletion. Do not let the restored database serve anyone
  until every one of them has been looked at by hand.

For each line printed, run the block below with its account id and deletion
time. It repeats what `backend/auth/deletion.py` does, minus the
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

- Revoking a live session was **not** exercised in the real-list rehearsal
  (the test account had no active session at the restore point).
- The `season_markers` insert was **not** exercised in the rehearsal (the test
  account had no participant link). It also uses the newest season in the
  restored data, which is wrong if a season changed between the deletion and
  the restore point. Check by hand if a season boundary falls in that gap.
- If an account both registered and deleted after the restore point, there is
  nothing to re-apply; it does not exist in the restored data.

## Step 5 — only then, let the app use it

Rehearsed on staging on 2026-11-20 (run 4), without steps 2 to 4 before it.

**5a. Close what step 2 opened.** Not rehearsed together with the rest of
this step. Remove the operator firewall rule, set public access back to
`Disabled`, and read both back before going on:

```sh
unset PGPASSWORD
az postgres flexible-server firewall-rule delete -g $RG -s $T --name operator-temp --yes
az postgres flexible-server update -g $RG -n $T --public-access Disabled -o none
az postgres flexible-server firewall-rule list -g $RG -s $T -o table
az postgres flexible-server show -g $RG -n $T --query "network.publicNetworkAccess" -o tsv
```

**5b. Give the restored server a private endpoint and a private name.** The
existing endpoint and DNS record of the source server are not touched.

```sh
VNET=<vnet>; PE=pe-$T
LOC=$(az network vnet show -g $RG -n $VNET --query location -o tsv)
SID=$(az postgres flexible-server show -g $RG -n $T --query id -o tsv)
az network private-endpoint create -g $RG -n $PE -l $LOC --vnet-name $VNET --subnet snet-data \
  --private-connection-resource-id $SID --group-id postgresqlServer --connection-name postgres -o none
az network private-endpoint show -g $RG -n $PE --query "{state:provisioningState, link:privateLinkServiceConnections[0].privateLinkServiceConnectionState.status, ip:customDnsConfigs[0].ipAddresses[0]}" -o table
az network private-endpoint dns-zone-group create -g $RG --endpoint-name $PE -n default \
  --private-dns-zone privatelink.postgres.database.azure.com --zone-name postgres -o none
az network private-dns record-set a list -g $RG -z privatelink.postgres.database.azure.com --query "[].{name:name, ip:aRecords[0].ipv4Address}" -o table
```

Expected: `Succeeded`, `Approved`, an address in the data subnet; then one
DNS record per server, the new one carrying that address. Add the resource
group's required tags with `--tags` on the `create`.

**5c. Point a new app revision at the restored server.** The block reads the
current connection string, swaps only the host name, shows both, and stops
if the current value is not what it expects. The string holds no password in
managed-identity mode.

```sh
APP=<container-app>; SRC=<source-server>
CUR=$(az containerapp show -g $RG -n $APP --query "properties.template.containers[0].env[?name=='SORT_TESTER_DATABASE_URL'].value | [0]" -o tsv)
NEW=${CUR/$SRC/$T}
echo "BEFORE $CUR"; echo "AFTER  $NEW"
if [ -z "$CUR" ] || [ "$CUR" = "$NEW" ]; then echo "STOP: unexpected current value, nothing changed"; else
az containerapp update -g $RG -n $APP --revision-suffix <suffix> --set-env-vars "SORT_TESTER_DATABASE_URL=$NEW" -o none
az containerapp revision list -g $RG -n $APP --query "[].{rev:name, active:properties.active, health:properties.healthState, traffic:properties.trafficWeight}" -o table
fi
```

**5d. Prove which database the app is serving.** A `200` from a health or
notice route right after the update proves nothing: the old revision can
still be answering. Use data that differs between the two databases. In the
rehearsal an account created after the restore point logged in before the
switch (`200`), was refused after it (`401`) while an older account still
logged in, and logged in again after the rollback.

What the rehearsal showed: the app's managed-identity role and its grants
come back with the restore; nobody had to recreate them.

Limits, stated plainly:

- **Rollback** is `az containerapp revision copy -g $RG -n $APP
  --from-revision <previous-revision> --revision-suffix <suffix>`. It was
  rehearsed. In a real recovery there is nothing to roll back to.
- Anything written while the app serves the restored server lives only there.
- After a real recovery the endpoint and the connection string were made by
  hand and no longer match the templates (`network.bicep` names one server).
  Reconciling them is not written or rehearsed.
- The source server's delete lock, backups settings and diagnostic settings
  were not checked on the restored server.

## Step 6 — clean up

For a rehearsal, or once the restored server is no longer needed:

```sh
unset PGPASSWORD
az network private-endpoint delete -g $RG -n pe-$T
az postgres flexible-server delete -g $RG -n $T --yes
az network private-endpoint list -g $RG --query "[].{name:name, state:provisioningState}" -o table
az network private-dns record-set a list -g $RG -z privatelink.postgres.database.azure.com --query "[].{name:name, ip:aRecords[0].ipv4Address}" -o table
az postgres flexible-server list -g $RG --query "[].{name:name, state:state, public:network.publicNetworkAccess}" -o table
az containerapp revision list -g $RG -n <container-app> --query "[].{rev:name, active:properties.active, traffic:properties.trafficWeight}" -o table
```

If the app was pointed at the restored server, roll it back and prove it
(step 5d) **before** deleting anything, so it never points at a server that
is gone. Deleting the endpoint removes its DNS record (seen in run 4). No
active revision may still name the deleted server.

`delete` prints nothing on success, and also nothing if the server never
existed. **Always run the `list` and read it**: only the expected servers,
each `Ready` with public access `Disabled`.

## The deletion list

Step 4 depends on a list that lives **outside the database**, because a
restore rewinds everything inside it. Owner decision on #13:

- Contents: account id and deletion time, nothing else.
- Kept for 7 days (the backup retention), then removed.
- Backup retention stays at 7 days; raising it requires revisiting this.
- A deletion is only "completed" for the player after those 7 days.
- This is an approved, minimal exception to Decision 14.

The app side is `backend/auth/deletion_list.py` (design:
`docs/superpowers/specs/2026-11-20-deletion-list-design.md`): one blob per
accepted deletion, named by the account id, containing the deletion time. A
deletion is refused when the note cannot be written. The storage is
`deletion-list-storage.bicep`; see [[deletion-list-storage]].

On staging this is deployed and a real deletion has written a real note
(issue #13, 2026-11-20). The read command in step 4 has unit tests only.

### Emergency: the app's container is not running

`az containerapp exec` needs a running container. If the whole app is down,
the list can only be read by opening the storage account, as was done for the
database. **This procedure has never been run**; treat every line as
unverified.

1. Give the operator's own account *Storage Blob Data Reader* on the
   `deletions` container (being subscription Owner does not grant data
   access).
2. Enable public network access on the account with default action `Deny`
   and one IP rule for the operator. Note that storage IP rules may not
   apply to callers inside the same Azure region; if Cloud Shell is refused,
   use a machine outside Azure.
3. `az storage blob list --auth-mode login` on the container, then
   `az storage blob download` for each name; the body is the deletion time.
4. Remove the IP rule, disable public network access, remove the role
   assignment, and **read back all three** before moving on. A cleanup
   command that printed nothing has not been shown to work.

A note can exist for an account that was never deleted (the app crashed
between writing the note and confirming the deletion). When the live database
is still reachable, check each listed account there before re-applying.

## Still open

- Deletion list: watch one note expire. The emergency read procedure has never been run.
- One recovery with steps 1 to 5 in sequence, timed end to end (step 5a has not been run after a real step 2).
- Bringing the templates back in line after a real recovery.
- Run the whole runbook on the separate pilot environment.
- Geo-redundant backup (only settable when a server is created).
- Owner approval of the data-loss and restore-time targets.
- Player-facing wording about the 7-day completion delay.
