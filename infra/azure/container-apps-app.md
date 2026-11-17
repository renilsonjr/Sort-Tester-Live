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
an older branch will not have it), one line at a time.

Cloud Shell keeps your home directory but not a virtualenv, so a session that
has not built one yet needs this first (the runtime list carries alembic and
psycopg, which is all a migration uses):

```sh
python3 -m venv backend/.venv
backend/.venv/bin/python -m pip install -q -r backend/requirements-runtime.txt
```

Then:

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

`upgrade_app` refuses until you name the database on the command line, printing
the server and database it resolved — read that line before confirming; it is
the last check that you are migrating what you think you are.

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

> **Applied 2026-11-16 — migration 0036.** The first migration since the
> database went private, and the procedure above is what ran: a rule for the
> Cloud Shell address alone, `upgrade_app --confirm` taking it 0035 → 0036,
> then §1e. No `--public-access` change, and the rule list was empty again
> afterwards. The app answered `/api/ranked/season/notice` after it, so it
> still reads the database.

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

## 3. Copy the image into the Azure registry

The app pulls as itself, with the user-assigned identity `id-sort-app-stg`
and its AcrPull on this subscription's own registry. There is no registry
password anywhere in the deployment any more (audit H-5).

Why it changed: the old path used a GitHub token with `read:packages`, which
is **account-scoped** — it can read every private package the account can
see, not just this one — and it had to be typed into a deployment to get
there. The identity's grant is on one registry, is not a secret, and cannot
be copied out of the app.

GHCR stays where the image is built and published (§2). This step copies the
digest you are deploying into the Azure registry, which is the only thing the
app reads:

```sh
read -rsp "GHCR token (classic, read:packages): " GHTOK; echo
az acr import -n <acr-name> \
  --source ghcr.io/<user>/sort-tester-live-app@sha256:<digest> \
  --image sort-tester-live-app:stg-YYYYMMDD \
  --username <user> --password "$GHTOK"
unset GHTOK
```

`--source` takes the digest, because that is what pins the exact image.
`--image` is the **target tag** and will not take a digest: given one, the
import is refused with `InvalidImportImageParameter ... TargetTags`. The copy
is byte for byte, so the digest inside the registry is the same one -- the tag
is only a name hung on it, and the deployment still goes by digest.

The token is used **here and nowhere else**, by you, for one copy. It never
reaches Azure's stored configuration.

Confirm the digest arrived (in this command group `-r` is the registry and
`-n` the image, the reverse of the rest of the CLI):

```sh
az acr manifest list-metadata -r <acr-name> -n sort-tester-live-app \
  --query "[].digest" -o tsv
```

Then check the identity may actually pull, before a deployment discovers it
cannot. `runtime-identity.bicep` grants this, but only if it has been
deployed since the registry existed:

```sh
az role assignment list --assignee <identity clientId> \
  --scope <registry resource id> --query "[].roleDefinitionName" -o tsv
```

It must print `AcrPull`. Nothing printed means no grant, and the app will
fail to start with an image-pull error that does not name the missing role.

Once the app is deployed and pulling (§6), **revoke that GitHub token**. It is
the finding; leaving it alive leaves the finding open.

## 4. Preview the deployment, change nothing

```sh
az account show --query '{name:name,state:state}' --output table
az bicep build --file infra/azure/container-apps-app.bicep --stdout >/dev/null
az deployment group what-if \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters expiresOn=YYYY-MM-DD \
               imageSha256=<digest from step 2> \
               registryServer=<acr-name>.azurecr.io \
               runtimeIdentityId=<runtimeIdentityId from runtime-identity.bicep> \
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

**Wait for the deletion to actually finish before deploying.** The delete
command returns while Azure is still tearing the environment down, and
creating a new one under the same name during that window fails with nothing
more useful than `Operation failed with general exception`, leaving the new
environment stuck in `Waiting`. This cost a cycle on 2026-11-16. Watch until
both the environment and its infrastructure resource group are gone:

```sh
for i in $(seq 1 30); do
  e=$(az containerapp env show -g rg-sort-tester-staging -n cae-sort-app-stg \
        --query properties.provisioningState -o tsv 2>/dev/null || echo gone)
  m=$(az group exists -n ME_cae-sort-app-stg_rg-sort-tester-staging_northcentralus -o tsv)
  echo "$(date +%H:%M:%S) env=$e managed-rg=$m"
  [ "$e" = gone ] && [ "$m" = false ] && break
  sleep 30
done
```

It passes through `ScheduledForDelete` and takes several minutes. If an
environment is already stuck in `Waiting`, delete it and wait the same way
before trying again.

Then deploy §5b with `appSubnetId=<the id from step 1>` added to its
parameters. The database URL does not change: inside the network the server's
own name resolves to its private address.

**Check the registry token before deploying, not after.** The image pull is
the other thing that failed here, and its error arrives only once the
deployment is half done: `DENIED: denied` on the image field. GHCR needs a
**classic** personal access token with `read:packages` — a fine-grained token
is refused. A 403 from this check means the token is real but not allowed to
read that package, which is the usual shape of the problem:

```sh
read -rsp "GHCR token: " GHTOK; echo
BT=$(curl -s -u "<user>:$GHTOK" \
  "https://ghcr.io/token?scope=repository:<user>/sort-tester-live-app:pull&service=ghcr.io" \
  | python3 -c "import sys,json;print(json.load(sys.stdin).get('token',''))")
curl -s -o /dev/null -w "manifest: %{http_code}\n" -H "Authorization: Bearer $BT" \
  -H "Accept: application/vnd.oci.image.index.v1+json" \
  "https://ghcr.io/v2/<user>/sort-tester-live-app/manifests/sha256:<digest>"
```

`200` means the deployment can pull. Anything else means fix the token first.

**Step 4 — prove the app works privately, before closing anything.** Run §6
against the new `appUrl`: `/health`, a login, one ranked attempt. `/health`
alone is not enough — it answers without touching the database. Use something
that reads: `/api/ranked/season/notice` returns real JSON only if the database
answered, and a 500 there means it did not. If the app cannot reach the
database, the DNS zone link or the endpoint's group id is wrong — fix that
before going on, because the next step removes the way back.

The app's address changes with the environment, so record the new `appUrl` and
redeploy once more with `appOrigin` set to it (§5b, no downtime: it only makes
a new revision).

**Step 5 — remove the public rule.**

```sh
az postgres flexible-server firewall-rule delete -g rg-sort-tester-staging \
  --server-name <server> --name allow-azure-services --yes
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

> **What is in force — 2026-11-16.** Step 6 was deliberately **not** taken.
> Public access stays `Enabled` with **zero firewall rules**, which is what
> actually refuses every public client today. The owner chose this because
> migrations still run often while the app is changing, and the extra
> protection did not justify the two-command dance around each one. Revisit
> it after #84, when the app signs in with a managed identity and no password
> has to cross anything.
>
> **So, to migrate:** §1c to add a rule for your own address, §1d, then §1e
> to remove it. No `--public-access` change is needed, and none should be
> made without updating this note.

**Step 7 — confirm from outside.** Cloud Shell counts as outside: it sits in
Azure but not in this network, which is exactly the case the removed rule used
to cover.

```sh
PGCONNECT_TIMEOUT=15 psql "host=<server>.postgres.database.azure.com port=5432 dbname=sort_tester_app user=<user> sslmode=verify-full" -c 'select 1'
```

A timeout is the answer you want. A password prompt means the server is still
reachable from the internet.

### 5a applied — 2026-11-16

Done, in this order, with the evidence:

1. `sort-tester-network` deployed: 5 created, 9 ignored, nothing modified.
2. Private endpoint `Approved` (auto, same subscription), and the private DNS
   zone gained an A record for the server, written by the endpoint.
3. The first environment create failed and hung in `Waiting` — the name was
   reused too soon after the delete. Deleted it, waited for `ScheduledForDelete`
   to finish, and the second create succeeded.
4. The app create then failed on `DENIED: denied` from GHCR. The token was a
   real 40-character one but got 403 for that package; a classic token with
   `read:packages` returned 200 from the manifest check and the deployment
   went through.
5. New environment domain `braveground-…`, so the app has a new address; the
   old one no longer exists. `appOrigin` redeployed to match.
6. `/health` 200 and `/api/ranked/season/notice` 200 with real JSON — the app
   reads the database.
7. `allow-azure-services` deleted, and the notice still answered 200. The app
   is reaching the database through the private endpoint and nothing else.
8. From Cloud Shell, `psql` to the server's public name: **timeout expired**.
   Before this change the same command reached it and answered.

H-4 is closed. Step 6 was not taken — see the note under it for what is in
force and what that means for the next migration.

### 5b. Create the app

```sh
az deployment group create \
  --name sort-tester-app-staging \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters @<a parameters file, 0600, deleted afterwards> \
  --confirm-with-what-if
```

The parameters are `expiresOn`, `imageSha256`, `registryServer`,
`runtimeIdentityId`, `databaseUrl` and `appSubnetId`. The database URL is the
only secret left, and it goes through a file rather than the command line, so
it stays out of shell history and out of `ps`:

```sh
read -rsp "Database password: " PGPW; echo; echo "length: ${#PGPW}"
PGPW="$PGPW" python3 - <<'EOF'
import json, os, urllib.parse
pw = urllib.parse.quote(os.environ["PGPW"], safe="")
dsn = (f"postgresql://<user>:{pw}@<server>.postgres.database.azure.com"
       ":5432/sort_tester_app?sslmode=require")
params = {
  "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#",
  "contentVersion": "1.0.0.0",
  "parameters": {
    "expiresOn": {"value": "YYYY-MM-DD"},
    "imageSha256": {"value": "<digest>"},
    "registryServer": {"value": "<acr-name>.azurecr.io"},
    "runtimeIdentityId": {"value": "<runtimeIdentityId>"},
    "databaseUrl": {"value": dsn},
    "appSubnetId": {"value": "<appSubnetId>"},
  },
}
path = os.path.expanduser("~/app-params.json")
with open(path, "w") as f:
    json.dump(params, f)
os.chmod(path, 0o600)
print("written:", path)
EOF
```

The password is percent-encoded on the way into the URL. Pasted raw, a `@`,
`:`, `/` or `#` in it breaks the URL, and the app then fails to start with an
error that says nothing about a password.

Delete the file when the deployment is done: `shred -u ~/app-params.json`.

Record the returned `appUrl`. A deployment that returns successfully is not
proof that the app runs; step 6 is.

On a **re**deployment, pass every parameter Azure already holds, not only the
ones you are changing. A parameter left out of the file falls back to the
template's default, which silently undoes whatever is configured: omitting
`appOrigin` reset it from the app's address to empty. The what-if names each
such reset as a `-` line under `properties.template.containers`, so read
those before deploying rather than after.

### 5b applied — 2026-11-17 (the identity pull, audit H-5)

1. `az acr import` copied the running digest `b60d5a8e…` from GHCR into the
   registry as `sort-tester-live-app:stg-20261117`. `list-metadata` showed
   that digest tagged, plus the index's two untagged platform manifests.
2. `az role assignment list` on the registry scope printed `AcrPull` for the
   identity's clientId, from the Task 4 bootstrap. Nothing had to be granted.
3. What-if: `2 to modify`, zero Delete, zero Replace. `username` and
   `passwordSecretRef` out, `identity` in, `server` `ghcr.io` →
   `acrsortstgzp6nl6c3wplfy.azurecr.io`, the `registry-password` secret
   removed, the same digest on both sides. The environment was not touched,
   so **the address did not change** — unlike §5a.
4. `sort-tester-app-h5` succeeded in 1m40.
5. One active revision, `ca-sort-app-stg--0000002`, `RunningAtMaxScale`,
   image on the ACR host. `/health` 200, `/api/ranked/season/notice` 200
   with real JSON, so the app still reaches the private database.
6. The GHCR token was revoked, which is what closes the finding.
   `shred -u ~/app-params.json` then reported the file missing: Cloud Shell
   had recycled the container and taken the file with it. The right outcome
   by the wrong route, so write the file and shred it inside one command
   chain, and check with `grep -rl "postgresql://" ~` rather than trusting
   that a failed `shred` means the secret is gone.

   This Cloud Shell has **no storage mounted**: there is no `~/clouddrive`,
   and the whole home directory, the git clone included, is gone by the next
   session. Do not plan a step around a file surviving.

Note on rollback: only one revision exists at a time here, so "activate the
previous revision" is not available. A failed pull is recovered by
redeploying with `registryServer=ghcr.io` and the GHCR parameters of the
previous template — which is why §3 says to revoke the token *after* step 6
and not before.

### 5c. Move the database URL into the vault (audit §3 P0-1)

Until this is done the URL, password and all, is stored in the container
app's own configuration. Anyone with Contributor on the resource group can
ask for it back. In the vault, the configuration holds only the secret's
address: seeing the URL then needs **data** access to the vault, which is a
separate grant that nobody has by default.

Note what that last part means for you. The vault uses Azure RBAC, and in
that mode **being Owner of the subscription grants no access to the data**.
Writing the secret needs `Key Vault Secrets Officer` on the vault, assigned
to you by name. Grant it, write the secret, and remove it afterwards: an
operator role that stays is the finding in a different place.

**Step 1 — compile the template.** The secret is a conditional, and a
conditional whose two branches are different shapes is where Bicep objects:

```sh
az bicep build --file infra/azure/container-apps-app.bicep --stdout >/dev/null
```

**Step 2 — grant yourself write access, by name:**

```sh
ME=$(az ad signed-in-user show --query id -o tsv)
VAULT=$(az keyvault show -n kv-sortstg-<suffix> -g rg-sort-tester-staging --query id -o tsv)
az role assignment create --assignee-object-id "$ME" --assignee-principal-type User \
  --role "Key Vault Secrets Officer" --scope "$VAULT"
```

RBAC takes up to a few minutes to apply. A write that fails with `Forbidden`
right after this is usually that delay, not a wrong grant.

**Step 3 — write the secret, without it reaching the shell history.**
`--value` would put the password in history and in `ps`; `--file` does not:

Write it, store it and shred it in **one** command chain, so the file exists
for a second or two and no recycled container can carry it away (§5b):

```sh
read -rsp "Database password: " PGPW; echo "length: ${#PGPW}"; umask 077
PGPW="$PGPW" python3 -c 'import os,urllib.parse; pw=urllib.parse.quote(os.environ["PGPW"],safe=""); open(os.path.expanduser("~/dsn.txt"),"w").write(f"postgresql://<user>:{pw}@<server>.postgres.database.azure.com:5432/sort_tester_app?sslmode=require")'
unset PGPW
az keyvault secret set --vault-name kv-sortstg-<suffix> --name database-url \
  --file ~/dsn.txt --query id -o tsv
shred -u ~/dsn.txt
```

**Check the printed length before letting the rest run.** The password has
been mistyped twice here, and both times the length said so: a wrong one
written to the vault leaves an app that cannot start, with nothing in the
error naming the password.

The command prints the **versioned** id. The template wants the
**versionless** URI, so that a rotated secret is picked up without a
redeployment — that is the same address with the trailing version removed:

```sh
az keyvault secret show --vault-name kv-sortstg-<suffix> --name database-url \
  --query "id" -o tsv | sed 's|/[^/]*$||'
```

**Step 4 — confirm the identity can read it.** The grant is from Task 4, but
confirm it rather than discovering a gap during the deployment:

```sh
az role assignment list --assignee <identity clientId> --scope "$VAULT" \
  --query "[].roleDefinitionName" -o tsv
```

It must print `Key Vault Secrets User`.

**Step 5 — deploy with the URI and no URL.** Pass every other parameter
Azure already holds (§5b's note), `databaseUrlSecretUri` instead of
`databaseUrl`, and nothing for `databaseUrl` at all:

```sh
az deployment group what-if \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-app.bicep \
  --parameters @<a parameters file; it holds no secret now, which is the point>
```

Read the `properties.configuration.secrets` block before deploying. It must
show `keyVaultUrl` and `identity` arriving. It will **not** show the old
`value` leaving: what-if does not render a secure value's removal, so the
proof that it is gone comes from step 6 and not from here. If nothing at all
arrives under `secrets`, both parameters are empty — stop, because the app
would start with no database URL and exit on its own configuration check.

**Step 6 — verify, restart, then take the write role back:**

```sh
az containerapp show -n ca-sort-app-stg -g rg-sort-tester-staging \
  --query "properties.configuration.secrets" -o json
```

No `value` may appear, only `keyVaultUrl` and `identity`.

Then **restart the revision**, and only afterwards trust the app's answers:

```sh
az containerapp revision restart -n ca-sort-app-stg -g rg-sort-tester-staging \
  --revision <the active revision>
```

Changing where a secret comes from does **not** create a new revision, and
the secret is injected when the container starts. So the process answering
right after the deployment is still the one that started with the old
injected value: its 200s say nothing about the vault. Without this restart a
broken vault path stays hidden until the next scale event or deployment,
whenever that happens to be. Restart on purpose, while someone is watching
and the write role is still in place, then check `/health` and
`/api/ranked/season/notice` as in §6.

Once both are 200 after the restart:

```sh
az role assignment delete --assignee-object-id "$ME" \
  --role "Key Vault Secrets Officer" --scope "$VAULT"
```

`delete` takes no `--assignee-principal-type`; only `create` does. Passing it
fails with `unrecognized arguments`, and the role stays in place.

Chain the confirmation with `&&`, not `;`: a `;` runs the "removed" message
even when the delete failed.

Rollback: redeploy passing `databaseUrl` and leaving `databaseUrlSecretUri`
empty. That is the whole reason the inline path is still in the template, and
it is why the write role comes off last — rebuilding the secret needs it.

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
