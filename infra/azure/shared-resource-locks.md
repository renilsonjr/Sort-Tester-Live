# Shared-resource delete locks — Task 20 / issue #196

**Applied and read-back verified — 2026-11-18.** The owner ran every `az`
command in Cloud Shell; §7 records the supplied evidence. The three locks
are installed, with unchanged app snapshot fields and passing HTTP smoke.
The owner accepted configuration-based lock verification on 2026-11-18,
using the alternative already allowed by Task 20; no actual delete was
attempted. The procedure below is retained for repeatable operation; PR
merge alone was not treated as deployment evidence or approval.

## Scope and limits

[[shared-resource-locks.bicep]] creates exactly three
`Microsoft.Authorization/locks@2020-05-01` resources, all `CanNotDelete`,
named `sort-tester-prevent-delete`, each scoped to one existing resource:

| Parameter | Resource type | Boundary |
| --- | --- | --- |
| `postgresServerName` | `Microsoft.DBforPostgreSQL/flexibleServers` | The existing staging server |
| `appInsightsName` | `Microsoft.Insights/components` | The existing component |
| `logAnalyticsName` | `Microsoft.OperationalInsights/workspaces` | The existing workspace |

All three must be in the selected subscription and `rg-sort-tester-staging`.
Their real names/IDs stay in the private inventory. No default resource
names, arbitrary target IDs, resource-group/subscription locks or `ReadOnly`
levels are accepted by the template. Existing resources are referenced,
not redeclared for creation/update. The template does not configure the
app, secrets, network, database, ingestion, retention, identities or grants.

**Implementation choice:** the original audit plan suggested adding the
locks to the app template. This standalone deployment keeps the approved
change to three lock writes and avoids replaying app parameters/defaults
just to protect resources the app template does not own. The existing
Bicep CI glob compiles the new file automatically.

These are management-plane protections. They do **not** prevent SQL data
deletion or replace the untested backup/restore procedure in #13. Locks
are inherited by child resources and can affect intentional teardown,
including some child-management operations such as RBAC assignment
deletion. An operator with lock-delete permission can remove them. See
[Azure management-lock semantics](https://learn.microsoft.com/en-us/azure/azure-resource-manager/management/lock-resources)
and the [lock resource reference](https://learn.microsoft.com/en-us/azure/templates/microsoft.authorization/2020-05-01/locks).

## 0. The deletion-list lock (added 2026-11-20)

The template takes an optional `deletionListStorageAccountName`. Given, it
adds a fourth `CanNotDelete` lock, on the storage account that holds the
deletion list (issue #13). Left empty, the template is exactly what it was.

The lock stops the account and its `deletions` container from being deleted
through Azure's management side. It does **not** stop the app or the 7-day
lifecycle rule from deleting notes; those are data operations. After applying
it, confirm that a note still expires.

The steps below are unchanged: preview, owner approval, apply, read back.
Expect one *Create* for the new lock and no change to the other three.

## 1. Read-only preflight

Use the merged, reviewed commit of `codex/ranked-mode` in Cloud Shell.
Check the selected Azure for Students subscription against the private
inventory, its credit/expiry and spending protection in the portal, and
the existing resource group. Creating/deleting locks needs
`Microsoft.Authorization/locks/*` or equivalent permission; no new role
grant is part of this procedure.

```sh
az account show --query '{id:id,name:name,state:state}' --output json
```

Enter the **existing** names from the private inventory. These are resource
names, not passwords; do not enter any credential here:

```sh
read -rp 'Existing PostgreSQL server name: ' SORT_TESTER_PG_NAME
read -rp 'Existing Application Insights name: ' SORT_TESTER_AI_NAME
read -rp 'Existing Log Analytics name: ' SORT_TESTER_LA_NAME
export SORT_TESTER_PG_NAME SORT_TESTER_AI_NAME SORT_TESTER_LA_NAME
```

Require all three reads to succeed and compare each returned ID with the
private inventory. Do not infer the target from a substring or select
the first resource in a list. `existing` declarations alone do not prove
that the typed name identifies the intended live resource.

```sh
az resource show -g rg-sort-tester-staging \
  --resource-type Microsoft.DBforPostgreSQL/flexibleServers \
  --name "$SORT_TESTER_PG_NAME" --query '{id:id,type:type}' --output json &&
az resource show -g rg-sort-tester-staging \
  --resource-type Microsoft.Insights/components \
  --name "$SORT_TESTER_AI_NAME" --query '{id:id,type:type}' --output json &&
az resource show -g rg-sort-tester-staging \
  --resource-type Microsoft.OperationalInsights/workspaces \
  --name "$SORT_TESTER_LA_NAME" --query '{id:id,type:type}' --output json
```

Inspect current direct and inherited locks in the portal and any relevant
deployment/change ownership. Stop if a same-name lock already exists until
its level, scope and ownership are understood; do not silently overwrite
or adopt it. Record app revision, image, allocation, replica count, traffic
and health before deployment for comparison afterwards. Keep actual IDs
private; share only a redacted preview/summary in tracked evidence.

## 2. Compile and prepare a private parameter file

```sh
az bicep build --file infra/azure/shared-resource-locks.bicep --stdout >/dev/null
```

Require a clean compile with no warnings. The compiled graph must contain
only three lock writes at the resource scopes above, no server/workspace
updates and no nested deployment that changes other resources.

Create a fresh owner-readable file outside the repository. Use this exact
file for both preview and apply; rebuild/review if its contents change.

```sh
umask 077
SORT_TESTER_LOCK_PARAMS="$(mktemp "$HOME/shared-lock-params.XXXXXX.json")"
export SORT_TESTER_LOCK_PARAMS
python3 - <<'PY'
import json
import os
from pathlib import Path

names = {
    'postgresServerName': os.environ['SORT_TESTER_PG_NAME'],
    'appInsightsName': os.environ['SORT_TESTER_AI_NAME'],
    'logAnalyticsName': os.environ['SORT_TESTER_LA_NAME'],
}
if any(not name.strip() or name != name.strip() or '/' in name for name in names.values()):
    raise SystemExit('Expected three existing resource names; recheck the private inventory.')
payload = {
    '$schema': 'https://schema.management.azure.com/schemas/2019-04-01/deploymentParameters.json#',
    'contentVersion': '1.0.0.0',
    'parameters': {key: {'value': value} for key, value in names.items()},
}
Path(os.environ['SORT_TESTER_LOCK_PARAMS']).write_text(json.dumps(payload))
print('Private parameters prepared; no credentials or resource names printed.')
PY
```

If file creation/preparation fails, stop. Never deploy using an empty,
old or guessed file. No database URL or other secret belongs in it.

## 3. Review the preview, then obtain owner approval

**Incremental only.** Complete mode is not appropriate for a standalone
template referencing a group that contains resources it does not manage.

```sh
az deployment group what-if -g rg-sort-tester-staging \
  --template-file infra/azure/shared-resource-locks.bicep \
  --parameters "@$SORT_TESTER_LOCK_PARAMS" \
  --mode Incremental --no-pretty-print
```

For the first rollout require **exactly three Creates**, each a
`CanNotDelete` lock at its reviewed resource ID. No application, database,
workspace, ingestion, networking, identity or grant change; no Delete or
unexpected Modify/Replace. Inspect the full changes, not only the totals.
Stop for a different resource, scope, level, pre-existing lock, unexpected
change or failed preview. A what-if is planned change, not proof of an
installed or effective lock.

The owner must approve those three exact scopes and the preview before
the next command. PR merge alone is not deployment approval. Resource
lock effects are described in this file; approval grants no permission to
delete the protected resources as a test.

## 4. Apply only the reviewed lock deployment

```sh
az deployment group create -g rg-sort-tester-staging \
  --name shared-resource-locks \
  --template-file infra/azure/shared-resource-locks.bicep \
  --parameters "@$SORT_TESTER_LOCK_PARAMS" \
  --mode Incremental \
  --query '{state:properties.provisioningState,lockIds:properties.outputs.lockIds.value}' \
  --output json
```

Require Succeeded. Keep the three output IDs privately. If it fails, read
the actual lock state before retrying; deployment failure is not proof
that none of the locks were created.

## 5. Read back each exact resource scope

```sh
az lock show -g rg-sort-tester-staging --name sort-tester-prevent-delete \
  --resource-type Microsoft.DBforPostgreSQL/flexibleServers \
  --resource-name "$SORT_TESTER_PG_NAME" \
  --query '{id:id,level:level}' --output json &&
az lock show -g rg-sort-tester-staging --name sort-tester-prevent-delete \
  --resource-type Microsoft.Insights/components \
  --resource-name "$SORT_TESTER_AI_NAME" \
  --query '{id:id,level:level}' --output json &&
az lock show -g rg-sort-tester-staging --name sort-tester-prevent-delete \
  --resource-type Microsoft.OperationalInsights/workspaces \
  --resource-name "$SORT_TESTER_LA_NAME" \
  --query '{id:id,level:level}' --output json
```

Require each ID to be exactly the reviewed parent resource ID followed by
`/providers/Microsoft.Authorization/locks/sort-tester-prevent-delete`,
with level `CanNotDelete`, matching the deployment outputs. Rerun the
same what-if and require no resource changes. Recheck the app's revision,
image, allocation, replica count, traffic and health/database-read smoke
against the preflight snapshot; the app was not a deployment target.

Record the commit, compiled-template hash, redacted preview summary,
owner approval, deployment state, three verified scopes/levels, and app
checks in #196 and a dated applied note here. Only then is the
**add-and-deploy** acceptance complete.

**Do not issue a real delete against the staging PostgreSQL server to
prove the guard works.** Its backup restore is still untested. Scope/level
read-back and a no-change preview verify installed configuration, not an
observed rejected deletion. For the 2026-11-18 rollout, the owner selected
the configuration-verification alternative already allowed by Task 20:
reviewed preview, three exact-scope `CanNotDelete` read-backs, a no-change
repeat preview and unchanged app checks. That evidence satisfies the
selected lock-verification criterion; it must not be described as an
observed failed delete. If a behavioral test is later required, propose
a disposable resource/group and explicit owner approval separately; no
such resource or test is authorised by this procedure.

## 6. Intentional removal and cleanup

Removing the resource from this template does **not** remove a deployed
lock in Incremental mode. Intentional teardown needs explicit owner
approval and removal of only the exact verified lock IDs, using
`az lock delete --ids` for each approved ID. Do not use a group-wide
delete, a wildcard or delete the parent resource to undo a lock. Confirm
the reviewed locks are absent afterwards; never remove unrelated locks.

After the work is complete, remove the temporary parameter file and clear
the resource-name variables. If Cloud Shell loses its ephemeral home or
variables, rebuild the preflight and preview instead of guessing them.
The lock template does not expire or auto-remove its protections.

## 7. Applied evidence — 2026-11-18

The owner executed the commands in Cloud Shell and supplied their outputs.
The assistant reviewed those outputs, not an independent Azure session.
Real target names, subscription ID and lock IDs remain in the private
inventory rather than this tracked record. Source: merged PR #200,
commit `9c1d38369729ba4d980c52cb993a013c676e4c1d`.

### Preflight, preview and approval

- Azure for Students reported **Enabled**. The staging inventory contained
  one resource of each expected type: Flexible Server, Application Insights
  component and Log Analytics workspace.
- Per-resource lock lists returned **empty** for all three reviewed targets.
- The Cloud Shell checkout fast-forwarded to the merged commit; the
  template compiled without reported warnings or errors. A fresh private
  parameter file held the three reviewed names.
- The full live **Incremental** what-if returned **Succeeded: 3 Create,
  15 Ignore**, error/diagnostics/potentialChanges null. Each Create was a
  `Microsoft.Authorization/locks@2020-05-01` resource, level `CanNotDelete`,
  at exactly the reviewed existing resource ID plus its extension lock
  suffix. All ignored entries had equal before/after payloads; there was
  no Modify/Delete/Replace.
- After the preview review, the owner explicitly authorised those three
  exact locks. No protected-resource deletion test was authorised.

### Apply and independent read-back

Deployment `shared-resource-locks`, using the same template/parameter file
in **Incremental** mode, returned **Succeeded** with the three expected
extension lock IDs. Subsequent independent `az lock show` calls confirmed:

| Resource scope | Lock name | Read-back level |
| --- | --- | --- |
| Existing PostgreSQL Flexible Server | `sort-tester-prevent-delete` | `CanNotDelete` |
| Existing Application Insights component | `sort-tester-prevent-delete` | `CanNotDelete` |
| Existing Log Analytics workspace | `sort-tester-prevent-delete` | `CanNotDelete` |

Read-back IDs matched the preview/deployment targets, normalising ARM ID
casing. A second what-if returned **Succeeded: 3 NoChange, 15 Ignore**;
error, diagnostics and potentialChanges were all null. There were no
remaining planned changes.

The owner's pre/post comparison covered ready revision, environment,
identity, revision mode, ingress traffic, container image/resources/env
and scale. It returned **app_snapshot_unchanged: true, changed_fields: []**.
The ready revision remained the returned baseline from the capacity test;
allocation was **0.25 CPU / 0.5 GiB**, with **1 GiB ephemeral storage**.
This is equality of the compared snapshot fields, not a full data-plane
or service-health audit.

Post-lock smoke passed:

- `/health`: **HTTP 200**, `{"status":"ok"}`.
- `/api/ranked/season/notice`: **HTTP 200**,
  `{"started":false,"label":null,"started_at":null,"closes_at":null}`,
  exercising the existing private database read path.

### Fingerprints and cleanup

The owner captured these fingerprints **after deployment**, recompiling
the same merged source, using **Bicep CLI 0.49.2 (b34271ac51)**:

| Artifact | SHA-256 |
| --- | --- |
| `shared-resource-locks.bicep` | `bd0a6092ce78702c89ee86c6d5f29e4cbf5d9699d435dcb9590b1584ea18cb75` |
| Compiled ARM JSON | `d868d96ff966b6d91e2870fd4af50b59e6f4ee1beb6350eb408c1cc21e432f67` |

Both match the assistant's local validation artifacts for that source and
compiler. These are reproducibility fingerprints, not an archived copy of
the original ARM request. The temporary compiled file/directory and private
parameter file were removed, and the task's resource-name/snapshot variables
cleared, by the operator's cleanup chain without reported errors.

### Acceptance boundary

The preview/approval/deploy/read-back/unchanged-app acceptance is complete
and recorded in [issue #196](https://github.com/renilsonjr/Sort-Tester-Live/issues/196).
**Owner decision — 2026-11-18:** accept that configuration evidence for the
lock-verification item, following the original Task 20 alternative
"test in a scratch resource group or trust what-if". The issue's earlier
wording required an observed delete refusal and was more restrictive than
that alternative; its replacement criterion is explicit:

> Verify the three `CanNotDelete` locks at the correct scopes, with a
> reviewed preview, independent read-back and a final what-if with no
> changes. No real deletion was attempted.

The recorded evidence meets this selected criterion. **No actual delete
was attempted** and no disposable test resource/group was provisioned.
Installed configuration is distinct from a demonstrated rejected operation;
the latter remains unobserved, not a required remaining step for this
owner-approved verification method. This decision changes the acceptance
method, not the measured facts or deployed configuration.
The backup restore, performance acceptance, final audit pass and employee
pilot gates remain separate work; this record does not close or approve them.
