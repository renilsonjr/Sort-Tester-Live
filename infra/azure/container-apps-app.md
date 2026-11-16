# Single-origin app on Container Apps — runbook (issue #41)

Deploys one container serving the frontend and `/api` together, connected to
the PostgreSQL Flexible Server already in `rg-sort-tester-staging`.
**Fictional data only.** No employee registers against this deployment, and
nothing here authorises a public launch; that is #13.

The owner runs every step. Each one says what to check before the next.
Stop at the first thing that does not match, and record what you saw.

## 0. Before anything, know the bill

The app runs **always on** (one replica, never zero): a cold start would eat
into the ten-second ranked question clock, and the sign-up rate limiter
counts in memory per instance. Always-on is not covered by the monthly free
grant.

1. In the portal, confirm the Azure for Students subscription: state, the
   credit balance **and its expiry date**, and the spending limit. Read the
   expiry from the portal — the student offer's terms have changed and the
   figure you remember may be stale.
2. Price the exact setup in the
   [pricing calculator](https://azure.microsoft.com/pricing/calculator/):
   Container Apps Consumption 0.25 vCPU / 0.5 GiB with one replica always on,
   plus the existing PostgreSQL Flexible Server B1ms with its current storage,
   in `northcentralus`. Write the monthly figure down; this is what the real
   bill is checked against in step 7.
3. Create a budget: **Cost Management → Budgets**, monthly, at an amount you
   accept, with email alerts at 50%, 80% and 100%. A budget alert only warns;
   it does not stop anything.
4. List the resource group by exact IDs and keep the list privately. The spike
   left four resources: PostgreSQL Flexible Server, Application Insights, Log
   Analytics, and a Smart Detection action group. **Stop** if today's
   inventory differs until you understand why. This template must not change
   any of them.

## 1. Prepare the database

The app does not create its own tables. Done once, on 2026-11-13, against
`pg-sort-tester-rjstg1109`; the steps below are what actually worked.

### 1a. Check how the server authenticates

```sh
az postgres flexible-server show -g rg-sort-tester-staging -n <server> \
  --query '{admin:administratorLogin, auth:authConfig, net:network.publicNetworkAccess}' \
  --output json
```

Use `--output json`, not `table`: a table silently hides null and nested
fields, which is how the Entra-only setting was missed the first time.

**If `passwordAuth` is `Disabled`,** the app cannot connect at all: it sends a
static `postgresql://` string, while an Entra credential is a token that
expires within the hour. Enable password authentication **in the portal**
(server → Authentication → "PostgreSQL and Microsoft Entra ID authentication"),
because `az postgres flexible-server update` has `--admin-password` but **no**
flag for the admin username, so the CLI path fails with
`EngineCredentialsNotProvided`. It takes several minutes; let it finish.
Managed identity instead of a password is #84.

Password rules: at least 8 characters, from three of uppercase, lowercase,
digits and symbols. Generate one that is also safe inside a URL — letters and
digits only, so nothing needs percent-encoding:

```sh
LC_ALL=C tr -dc 'A-Za-z0-9' </dev/urandom | head -c 32; echo
```

Keep it in a password manager. Never let a command print it: `az ... update
--password-auth Enabled` with no `-p` **generates and prints** one.

### 1b. Create the database

```sh
az postgres flexible-server db create -g rg-sort-tester-staging \
  --server-name <server> --name sort_tester_app
```

The flag is `--name`, not `--database-name`. In this command group `--name` is
always the thing being acted on — hence `firewall-rule` below, where `--name`
is the *rule* and the server is `--server-name`.

### 1c. Open the firewall for your machine only

```sh
curl -s https://api.ipify.org                      # your public IP
az postgres flexible-server firewall-rule create -g rg-sort-tester-staging \
  --server-name <server> --name migration --start-ip-address <IP> --end-ip-address <IP>
```

Confirm the path works before typing the real password — a deliberately wrong
one proves the network, TLS and the user are fine:

```sh
PGCONNECT_TIMEOUT=15 PGPASSWORD='wrong-on-purpose' psql \
  "host=<server>.postgres.database.azure.com port=5432 dbname=sort_tester_app user=<admin> sslmode=verify-full" -c 'select 1'
```

`FATAL: password authentication failed` is the answer you want. A timeout
means the firewall rule is wrong.

### 1d. Migrate

From a checkout that **has** `backend/db/upgrade_app.py` (it landed in #79, so
an older branch will not have it), one line at a time:

```sh
read -rsp "Paste the password and press Enter: " PGPW; echo
echo "length: ${#PGPW}"     # must match the password you generated
export SORT_TESTER_DATABASE_URL="postgresql://<admin>:$PGPW@<server>.postgres.database.azure.com:5432/sort_tester_app?sslmode=verify-full&sslrootcert=/etc/ssl/certs/ca-certificates.crt"
backend/.venv/bin/python -m backend.db.upgrade_app                      # shows the target only
backend/.venv/bin/python -m backend.db.upgrade_app --confirm sort_tester_app
```

`sslmode=verify-full` is now required by the app itself: a DSN without a
verifying `sslmode` is refused at startup rather than connecting in the clear
(audit M-4, `backend/db/settings.py`). It needs a CA bundle to check the
server's certificate against. `/etc/ssl/certs/ca-certificates.crt` is the
Debian/Alpine path, which is what Cloud Shell and the app image use; on macOS
point `sslrootcert` at your own bundle instead. Azure PostgreSQL's certificate
chains to a public root, so no certificate has to be copied anywhere — if a
future image turns out to ship no bundle, check with
`docker run --rm <image> ls -l /etc/ssl/certs/ca-certificates.crt` before
deploying, and bake the root in only if that file is missing.

A loopback database (`localhost`, `127.0.0.1`, `::1`) is exempt: nothing
crosses a network there, and local development would otherwise be impossible.

`read -rsp` prints a prompt, hides what you type, and keeps the password out of
shell history. Run it **alone**: pasted together with the next command, `read`
swallows that command as the password. The length check catches exactly that.

Check `Revision after: 0020` (or later), then that every table arrived:

```sh
backend/.venv/bin/python -c "
from backend.db import migrate, settings
u = settings.app_database_url()
names = '''accounts assignment_questions assignments attempt_answers
attempt_connection_events attempts balance_history balances confirmed_outages
connection_flags emails login_credentials outbox participant_links
question_versions season_markers seasons sessions settlements'''.split()
print('revision:', migrate.current_revision(u))
print('missing:', [t for t in names if not migrate.table_exists(u, t)] or 'none')
"
```

### Runtime identity after migration — Task 4

The URL above belongs to the migration owner. Before real data, prepare and
verify a separate runtime role using [[db-runtime-role]]. The application
secret must use the runtime role; `upgrade_app` continues using the migration
owner. The new script/runbook are preparation, not evidence that Azure has
switched roles. Do not deploy the migration-owner URL as the runtime secret.

### 1e. Close the firewall again

```sh
az postgres flexible-server firewall-rule delete -g rg-sort-tester-staging \
  --server-name <server> --name migration --yes
```

`az` lives in Cloud Shell, not on your own machine, unless you installed it.

## 2. Publish the image

1. Confirm the **App image** workflow passed on the commit you intend to
   deploy.
2. Run **App image publish** manually on `codex/ranked-mode`
   (`gh workflow run "App image publish" --ref codex/ranked-mode -f confirm_publish=publish`),
   typing `publish` to confirm and choosing the visibility the package must
   have. It refuses if App image did not succeed for that commit, and it
   checks the package visibility **before** pushing, so a mismatch stops the
   run with nothing published.
3. The job summary prints `imageSha256=<64 hex characters>`. That digest is
   the only thing you deploy.

Visibility: the package is **private** (set by the owner on 2026-11-14, after
the first publish created it public). The image contains the Ranked question
bank. A private package does not affect the repository or GitHub Pages. Check
the package page shows **Private** before deploying.

First published 2026-11-14 from `b21e2aa`:
`imageSha256=130d9ee7ca5b4abe79ad354a5c618571ebfc83d2411c6f644a359791b876b6ee`.

## 3. Create a read-only token for the registry

Container Apps pulls from the private GHCR package with a token.

1. Create a personal access token with `read:packages` and nothing else.
2. Keep it out of the repository and out of your shell history; it is passed
   to the deployment as a secure parameter in step 4.

## 4. Preview the deployment, change nothing

```sh
az account show --query '{name:name,state:state}' --output table
az bicep build --file infra/azure/container-apps-app.bicep --stdout >/dev/null
az deployment group what-if \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters expiresOn=YYYY-MM-DD \
               imageSha256=<digest from step 2> \
               registryUsername=<github username> \
               registryPassword=<token from step 3> \
               databaseUrl=<url from step 1>
```

On a **re**deployment the summary is `2 to modify` instead: the app (image and
settings) and the environment, whose two `-` lines (`mtls.enabled: false`,
`encryption.enabled: false`) are defaults this template does not declare and
are reported as noise. The four older resources must still show as ignored.

Read the **whole** what-if output. It must show exactly two creates,
`cae-sort-app-stg` and `ca-sort-app-stg`, with **zero** Delete, Modify or
Replace lines. Stop if either name already exists, if anything else is
touched, or if the output is cut off.

## 5. Deploy

### 5a. Give the database a private address (audit H-4)

Until this is done the app reaches the database over the public internet
through an `allow-azure-services` rule, and the all-zero range is how Azure
spells "any Azure resource" — including other people's. The password is then
the only barrier. This section replaces that rule with a private network.

**Read this before starting.** A Container Apps environment cannot be moved
into a network after it is created. Switching it on **recreates the
environment and the app, and the app's address changes**. Budget 15–30
minutes of downtime, and expect a new `appUrl` at the end. The owner accepted
both on 2026-11-16, no one outside the project using the app yet.

Retire the disposable spike and staging apps first (owner decision, same
date): each is another way into the database, and removing them makes the
switch smaller and cheaper. See `container-apps-staging.md` §8 and
`CONTAINER-APPS-SPIKE.md`.

**Step 1 — build the network.** It creates nothing that touches the app and
changes nothing on the server:

```sh
az deployment group create \
  --name sort-tester-network \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/network.bicep \
  --parameters expiresOn=YYYY-MM-DD postgresServerName=<server> \
  --confirm-with-what-if
```

Record the returned `appSubnetId`. The what-if must show creates only: a
virtual network, a private DNS zone and its link, a private endpoint and its
DNS group. Nothing modified, nothing deleted.

**Step 2 — check the name now answers privately.** From a machine inside the
network this is what the app will see; from Cloud Shell, which is outside it,
the public address still answers. Both are expected:

```sh
az network private-endpoint-connection list --id <privateEndpointId> -o table
```

The connection status must be `Approved`. The endpoint belongs to the same
subscription as the server, so Azure approves it without asking.

**Step 3 — recreate the environment inside the network.** Delete the old app
and environment first; a redeploy cannot do this in place:

```sh
az containerapp delete -g rg-sort-tester-staging -n ca-sort-app-stg --yes
az containerapp env delete -g rg-sort-tester-staging -n cae-sort-app-stg --yes
```

Then deploy §5b with `appSubnetId=<the id from step 1>` added to its
parameters. The database URL does not change: inside the network the server's
own name resolves to its private address.

**Step 4 — prove the app works privately, before closing anything.** Run §6
against the new `appUrl`: `/health`, a login, one ranked attempt. If the app
cannot reach the database, the DNS zone link or the endpoint's group id is
wrong — fix that before going on, because the next step removes the way back.

**Step 5 — remove the public rule.**

```sh
az postgres flexible-server firewall-rule delete -g rg-sort-tester-staging \
  --name <server> --rule-name allow-azure-services --yes
```

Run §6 again. The app must still work: it is now reaching the database
through the private endpoint and nothing else.

**Step 6 — close public access entirely.** This is the end state the audit
asks for, and it has a cost worth knowing before you type it: with public
access disabled, firewall rules stop applying altogether, so **migrations
from Cloud Shell no longer connect**. Running one then means re-opening
public access for the length of the migration:

```sh
# the strong end state
az postgres flexible-server update -g rg-sort-tester-staging \
  --name <server> --public-access Disabled

# and, only when a migration has to run, the two commands around it
az postgres flexible-server update -g rg-sort-tester-staging \
  --name <server> --public-access Enabled
#   ... §1c to open your own address, §1d to migrate, §1e to close it ...
az postgres flexible-server update -g rg-sort-tester-staging \
  --name <server> --public-access Disabled
```

If you would rather not carry that dance, stopping after step 5 already
closes the finding: with public access enabled but **no firewall rules at
all**, no public client can connect either. Step 6 is the stronger version,
not the only acceptable one. Whichever you choose, write down which, because
the next person to run a migration needs to know.

**Step 7 — confirm from outside.** From your own machine, not Cloud Shell:

```sh
PGCONNECT_TIMEOUT=15 psql "host=<server>.postgres.database.azure.com port=5432 dbname=sort_tester_app user=<user> sslmode=verify-full" -c 'select 1'
```

A timeout is the answer you want. A password prompt means the server is still
reachable from the internet.

### 5b. Create the app

```sh
az deployment group create \
  --name sort-tester-app-staging \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters expiresOn=YYYY-MM-DD imageSha256=<digest> \
               registryUsername=<username> registryPassword=<token> \
               databaseUrl=<url> appSubnetId=<appSubnetId from 5a> \
  --confirm-with-what-if
```

Record the returned `appUrl`. A deployment that returns successfully is not
proof that the app runs; step 6 is.

## 6. Check what was deployed

A successful command is not a working app. With `URL` set to `appUrl`:

```sh
curl -s "$URL/health"                                     # {"status":"ok"}
curl -s -o /dev/null -w '%{http_code}\n' "$URL/"          # 200
curl -s -o /dev/null -w '%{http_code}\n' "$URL/backend/main.py"  # 404
curl -s -o /dev/null -w '%{http_code}\n' "$URL/.git/config"      # 404
curl -si -X POST "$URL/api/auth/register" -H "Origin: $URL" \
  -H 'Content-Type: application/json' -d '{"username":"owner_check"}' | head -20
```

Check, in order:

- `/health` answers `{"status":"ok"}` over HTTPS, and plain `http://` is
  redirected or refused, never served;
- the home page loads in a phone browser and Practice still works;
- the sign-up response's `Set-Cookie` carries **`Secure`**, **`HttpOnly`** and
  **`SameSite=Lax`**. If `Secure` is missing, stop: the session cookie would
  travel unprotected;
- a write from somewhere else is refused:
  `curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL/api/auth/logout" -H 'Origin: https://evil.example'`
  must print `403`;
- log in in a browser, reload, and confirm you are still logged in;
- the portal shows **one** replica and no restart loop; read the revision's
  logs for errors.

Optional, once the FQDN is known: redeploy with `appOrigin=$URL` so writes are
checked against the public origin rather than the ingress host. Everything
above must still pass afterwards.

### 6a. Decide whether to trust the ingress for client addresses (issue #78)

The template defaults `trustedProxies` to `1` and accepts only `1`.
This setting trusts the single Container Apps ingress hop, verified on staging
below. Empty trust would group clients behind the ingress; trusting two hops
could include a client-supplied address. Local development and other hosts
keep their own configuration; this template applies only to Container Apps.

The check below verifies that the rightmost address is supplied by the ingress,
not the client. Repeat it after a change to the proxy topology, using fictional
login IDs and two different networks, with `URL` set to the staging URL:

```sh
# A. From one machine: a different forged address on every request.
for n in $(seq 1 12); do curl -s -o /dev/null -w '%{http_code} ' -X POST "$URL/api/auth/login" \
  -H "Origin: $URL" -H 'Content-Type: application/json' -H "X-Forwarded-For: 9.9.9.$n" \
  -d '{"login_id":"AAAA-AAAA-AAAA-AAAA"}'; done; echo
# B. Straight afterwards, from a DIFFERENT network (Cloud Shell, a phone on mobile data):
curl -s -o /dev/null -w '%{http_code}\n' -X POST "$URL/api/auth/login" \
  -H "Origin: $URL" -H 'Content-Type: application/json' -d '{"login_id":"AAAA-AAAA-AAAA-AAAA"}'
```

**Verified on staging, 2026-11-14:** with `trustedProxies=1`, A gave ten `401`
then `429`, and B gave `401` while the first machine was still locked. The
Container Apps ingress appends the real client address after anything the
client sent, so one trusted proxy is the right setting there.

- A must print ten `401` then `429`: forging the header does not evade the limit.
- B must print `401`: another network has its own counter.
If either check fails, stop the rollout and investigate the actual proxy
chain. Do not increase the trust count or disable the limiter to make the
check pass; that requires a separately reviewed topology/configuration change.

**Template hardening — 2026-11-16:** the allowed-value constraint now prevents
an omitted parameter or an explicit empty/`2` override from changing the
verified setting. Local tests and Bicep compilation check the emitted default,
allowed values and runtime environment variable. This repository change does
not redeploy or re-verify the running Azure revision.

## 7. Read the real cost

Billing data lags, usually 8 to 24 hours.

1. The next day, open **Cost Management → Cost analysis** and compare the
   actual daily cost with the estimate from step 0.
2. After a few days, read the **forecast** for the month. That figure, not the
   estimate, is what decides whether this stays up.
3. If it is above what you accept, either delete the app (step 8) or reduce
   the deployment, and record the decision.

## 8. Remove it

Deleting the app and its environment stops the Container Apps charge; the
database keeps costing until it is deleted or stopped separately.

```sh
az containerapp delete --name ca-sort-app-stg --resource-group rg-sort-tester-staging
az containerapp env delete --name cae-sort-app-stg --resource-group rg-sort-tester-staging
```

Then the network from §5a, in this order — the endpoint before the network it
sits in, or the delete fails:

```sh
az network private-endpoint delete -g rg-sort-tester-staging --name pe-sort-postgres
az network vnet delete -g rg-sort-tester-staging --name vnet-sort-stg
az network private-dns link vnet delete -g rg-sort-tester-staging \
  --zone-name privatelink.postgres.database.azure.com --name link-vnet-sort-stg --yes
az network private-dns zone delete -g rg-sort-tester-staging \
  --name privatelink.postgres.database.azure.com --yes
```

If you left public access disabled in §5a step 6, the database is now
reachable from nowhere at all. That is safe to leave, but say so in the
record, because the next person to open it will not guess it.

Confirm both are gone and that **every pre-existing resource ID from step 0 is
still there**. Do not delete the resource group. Record any cleanup failure
and any charge that appears afterwards.

## What this runbook does not do

No employee data, no public launch, no custom domain, no backup or restore
test, no 30-player load test, and no removal of the spending limit. Those are
#13. The app-image workflow's vulnerability scan only reports; nobody has
decided to make it blocking.
