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
  "host=<server>.postgres.database.azure.com port=5432 dbname=sort_tester_app user=<admin> sslmode=require" -c 'select 1'
```

`FATAL: password authentication failed` is the answer you want. A timeout
means the firewall rule is wrong.

### 1d. Migrate

From a checkout that **has** `backend/db/upgrade_app.py` (it landed in #79, so
an older branch will not have it), one line at a time:

```sh
read -rsp "Paste the password and press Enter: " PGPW; echo
echo "length: ${#PGPW}"     # must match the password you generated
export SORT_TESTER_DATABASE_URL="postgresql://<admin>:$PGPW@<server>.postgres.database.azure.com:5432/sort_tester_app?sslmode=require"
backend/.venv/bin/python -m backend.db.upgrade_app                      # shows the target only
backend/.venv/bin/python -m backend.db.upgrade_app --confirm sort_tester_app
```

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

Visibility (owner decision, 2026-11-14): the package is **public**. The image
contains the Ranked question bank, but that bank is already in this public
repository, so a public image exposes nothing more. If the repository ever
becomes private, make the package private first and publish with
`expected_visibility=private`.

First published 2026-11-14 from `b21e2aa`:
`imageSha256=130d9ee7ca5b4abe79ad354a5c618571ebfc83d2411c6f644a359791b876b6ee`.

## 3. Create a read-only token for the registry

The deployment template passes registry credentials, which a public package
does not strictly need but still accepts.

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

Read the **whole** what-if output. It must show exactly two creates,
`cae-sort-app-stg` and `ca-sort-app-stg`, with **zero** Delete, Modify or
Replace lines. Stop if either name already exists, if anything else is
touched, or if the output is cut off.

## 5. Deploy

### 5a. Let the app reach the database

The app runs inside Azure, not on your machine, so the rule from step 1c does
nothing for it. A Consumption Container App has no fixed outbound IP, so the
only rule that fits is the Azure-services one — the all-zero range is how
Azure spells "any Azure resource", not "the whole internet":

```sh
az postgres flexible-server firewall-rule create -g rg-sort-tester-staging \
  --server-name <server> --name allow-azure-services \
  --start-ip-address 0.0.0.0 --end-ip-address 0.0.0.0
```

Be clear about what this gives away: at the network layer, any Azure resource,
including other people's, can reach the server. The password is then the only
barrier. That is the price of the Consumption plan's dynamic egress, and it is
a large part of why #84 (managed identity) matters before employee data. Add
this rule at deployment time, not earlier, and remove it when the app is
removed in step 8.

### 5b. Create the app

```sh
az deployment group create \
  --name sort-tester-app-staging \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters expiresOn=YYYY-MM-DD imageSha256=<digest> \
               registryUsername=<username> registryPassword=<token> \
               databaseUrl=<url> \
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
az postgres flexible-server firewall-rule delete -g rg-sort-tester-staging \
  --server-name <server> --name allow-azure-services --yes
```

Remove the firewall rule from step 5a too: with no app, nothing should be able
to reach the database.

Confirm both are gone and that **every pre-existing resource ID from step 0 is
still there**. Do not delete the resource group. Record any cleanup failure
and any charge that appears afterwards.

## What this runbook does not do

No employee data, no public launch, no custom domain, no backup or restore
test, no 30-player load test, and no removal of the spending limit. Those are
#13. The app-image workflow's vulnerability scan only reports; nobody has
decided to make it blocking.
