# Azure Container Apps Staging Design

## Decision and boundary

The owner chose Azure for the Sort Tester Live backend after Oracle's Always
Free A1 shape returned out-of-capacity in all three Ashburn availability
domains. This design replaces the **hosting choice** in the earlier
`2026-11-09-azure-staging-host-design.md`: Azure Container Apps Consumption
replaces Azure App Service F1, whose quota is zero in the subscription's allowed
North Central US region. The older App Service Bicep and its implementation plan
must not be deployed. They remain historical records until a reviewed update
marks them superseded.

The immediate implementation is an **API-only fictional staging service**. The
existing PostgreSQL Flexible Server remains in Azure but is not connected by
this implementation. A separate design and implementation plan must resolve
database networking, price, identity mapping, recovery, and tests before
`/ready` or any database-dependent feature is deployed. Approval here does not
authorize employee data, Ranked Mode, prizes, or ongoing paid usage.

## Why this order

The November 10 disposable Container Apps spike already proved the existing
FastAPI image can answer HTTPS `GET /health` with exactly `{"status":"ok"}` and
return 404 for an unknown route. Its app and environment were deleted. Reuse
that tested image and infrastructure shape for a bounded staging deployment;
do not repeat a new framework or move the GitHub Pages Practice app.

Container Apps can use a system-assigned managed identity for Azure PostgreSQL,
so an off-Azure certificate is unnecessary. However, Container Apps outbound
public IP addresses can change. The previous App Service plan's static
PostgreSQL firewall assumptions are invalid here. A private Azure network may
solve that problem but introduces separate resources and possible charges.
The database connection therefore remains a cost-and-network decision, not a
side effect of bringing up `/health`.

## API-only architecture

```text
GitHub Pages Practice (unchanged)

Owner/test browser -- HTTPS --> Azure Container Apps Consumption
                           /health, no database dependency

Existing Azure PostgreSQL Flexible Server -- no app connection yet
```

- Use the existing `rg-sort-tester-staging` resource group in the subscription's
  policy-allowed `northcentralus` region. Inventory it by exact resource IDs
  before deployment; the four resources reported after the spike are existing
  resources, not deployment targets.
- Create exactly one new Container Apps Consumption environment and one new
  container app. Use distinct staging names and the existing project,
  environment, fictional-data, and expiry tags. No App Service, VM, VNet,
  public IP, database, registry, secret, or logging workspace is created by
  this API-only deployment.
- Reuse the reviewed public GHCR image by immutable SHA-256 digest. Verify its
  anonymous pull, architecture, contents, and image scan before deployment.
  Do not use a mutable tag or place credentials in the image.
- Keep external HTTPS ingress, `allowInsecure=false`, target port 8000,
  Consumption profile, 0.25 vCPU, 0.5 GiB, minimum zero replicas, and maximum
  one replica. Keep the app's health endpoint database-independent. Do not add
  a deployment token, database URL, or employee data.
- Keep the student subscription spending limit enabled. Confirm current
  Container Apps free-grant use and an estimate for this exact configuration
  before creation. Scale-to-zero and maximum one replica limit usage but do not
  guarantee a zero bill. The first run has a short, recorded test window and
  explicit cleanup if the cost evidence is missing or consumption surprises us.

## Verification and operation

1. Reconcile the shared `codex/ranked-mode` branch with current `main`, which
   contains the successful spike's fixes and cleanup record. Do not force-push
   or discard either history. Run the complete existing backend and JavaScript
   test suites and inspect the final deployment diff.
2. Validate the new staging Bicep locally. Run Azure `what-if` against the
   existing resource group and reject Delete, Replace, changes to the four
   existing resources, unexpected resources, paid profile types, or missing
   ownership tags. Check the exact account and spending limit again.
3. Deploy the two reviewed resources. Record image digest, Git commit, resource
   IDs, start time, test-window end, and expected cost outside Git without
   exposing subscription or user identifiers in public output.
4. Test HTTPS `/health` (200, exact JSON), unknown route (404), HTTP upgrade or
   rejection, cold and warm responses, and zero-replica behavior. Test from a
   second device. Inspect only sanitized logs. Do not infer 30-player or
   database capacity from health checks.
5. Review actual usage and cost data after Azure posts it. If keeping the
   service running longer is not supported by measured free-grant headroom,
   remove the exact app and environment after confirming no other app uses the
   environment. Preserve all pre-existing resources. Record any delayed bill
   and cleanup failure honestly.

## Next design: Azure PostgreSQL connection

The next stage will inventory the existing server's networking mode, current
firewall, region, free allowance, and Entra administrator; then compare a
private network path with an exact temporary public firewall path for fictional
integration tests. Public egress IP drift cannot be treated as a permanent
firewall guarantee. Any VNet, Private DNS zone, private endpoint, NAT gateway,
or other charge needs its own reviewed estimate. Runtime identity must be a
restricted Entra PostgreSQL role, use TLS, and never receive an admin role or
stored database password. Only after that stage passes may `/ready` be added.

The student offer's terms and a production cost, privacy, security, and
recovery review remain separate gates before any employee information or
competition traffic is allowed.
