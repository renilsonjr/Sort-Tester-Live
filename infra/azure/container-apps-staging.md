# Azure Container Apps API staging runbook

This runbook is for a small, fictional-data-only FastAPI health test. It does
not connect to PostgreSQL or authorize employee access. The former App Service
plan in this directory is historical and must not be deployed. The November 10
Container Apps spike in `CONTAINER-APPS-SPIKE.md` is the tested starting point.

## Before creating anything

1. Confirm the active Azure for Students subscription in the portal, its
   spending limit, current balance, policy-allowed `northcentralus` region,
   Container Apps Consumption grant usage, and any charges already pending.
   A scale limit is not a dollar cap. Record a current estimate for exactly
   0.25 vCPU, 0.5 GiB, zero to one replica, one Consumption environment,
   HTTPS requests, and no new Log Analytics workspace.
2. Confirm `rg-sort-tester-staging` is the intended group. List the resource
   IDs, types, names, and tags privately. The four resources left after the
   spike were PostgreSQL Flexible Server, Application Insights, Log Analytics,
   and a Smart Detection action group. Stop if the current inventory differs
   until the difference is understood. This template must not modify them.
3. Confirm the public GHCR image is anonymously pullable by its immutable
   digest and scan that digest. The reviewed digest is
   `sha256:0de6ceb356b0f82bb3dc6d3ddca263485675bd84cc3548251ef3ac01cf9baded`.
   Stop on a failed pull, architecture mismatch, scan finding requiring a fix,
   or missing cost evidence. Do not substitute a mutable tag.
4. Use only a clean, reviewed commit of `codex/ranked-mode`. Keep account IDs,
   private inventory, cost reports, and response logs outside Git. Do not run
   the old `main.bicep` App Service deployment.

## Validate and preview in Azure Cloud Shell

The following commands compile and read Azure state. Set the expiry tag to the
UTC date when the owner will review or remove the test resources. The tag does
not delete anything automatically.

```bash
az account show --query '{name:name,state:state,isDefault:isDefault}' --output table
az resource list --resource-group rg-sort-tester-staging \
  --query '[].{name:name,type:type,location:location}' --output table
az bicep build --file infra/azure/container-apps-staging.bicep --stdout >/dev/null
az deployment group what-if \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-staging.bicep \
  --parameters expiresOn=YYYY-MM-DD
```

Read the complete `what-if` output. It must show only
`cae-sort-api-stg` and `ca-sort-api-stg` as creates, with zero Delete,
Replace, or changes to existing resources. Verify tags, region, image digest,
Consumption profile, and zero-to-one replica setting. Stop if the exact target
names already exist, the subscription or cost evidence changed, or the preview
is incomplete.

## Bounded first test

After the owner reviews the preview and free-grant evidence, record the UTC
start time and a 30-minute end time privately. Then deploy only the reviewed
template:

```bash
az deployment group create \
  --name sort-tester-api-staging-review \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/container-apps-staging.bicep \
  --parameters expiresOn=YYYY-MM-DD \
  --confirm-with-what-if
```

Record the returned app and environment IDs. Confirm both have the expected
tags. A successful deployment command alone is not proof that the API runs.
Check HTTPS `GET /health` for HTTP 200 with exactly `{"status":"ok"}`;
an unknown path for HTTP 404; plain HTTP for rejection or upgrade; and cold
and warm response times. Repeat `/health` from a second device. Inspect only
sanitized runtime logs and confirm the app can scale to zero. This does not
test PostgreSQL or 30 simultaneous players.

## Keep or remove

Check current Consumption usage and cost, including delayed billing data. If
the owner cannot justify keeping the two resources within the free allowance,
remove only the app ID recorded in this test, verify it is absent, then confirm
that the environment contains no other app and remove only the recorded
environment ID. Verify both are absent and every pre-existing resource ID
remains. Do not delete the resource group or PostgreSQL server. Record any
cleanup failure or later charge. Issue #6 remains open until database
readiness, recovery, and employee-use gates have their own review.
