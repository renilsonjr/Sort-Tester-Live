# Azure Staging Host Design

## Intent

Run the Sort Tester Live backend and a PostgreSQL foundation outside the
owner's personal computer, using the existing Azure for Students subscription
as a bounded staging environment. The first deployment exists to prove that
the application can be deployed, secured, observed, recovered, and removed.
It is not authorization to store employee data or run the prize competition.

## Why this approach

The owner wants to reduce the risk of keeping employee data on personal
hardware. Azure App Service and Azure Database for PostgreSQL separate that
data from the home computer and move operating-system and database maintenance
to managed services. The tradeoff is a new public-cloud attack surface,
subscription expiry, usage charges, and Azure for Students use restrictions.

## Goals

- Deploy the existing FastAPI `/health` endpoint to Azure App Service on Linux.
- Establish a least-privilege connection to Azure Database for PostgreSQL
  Flexible Server using fictional probe data only.
- Keep the existing GitHub Pages Practice application operational and visually
  unchanged.
- Prove TLS, access restrictions, secret handling, logging, restart behavior,
  backup restoration, cleanup, and thirty-client health-load behavior.
- Make every Azure resource reproducible and removable from versioned
  infrastructure definitions.
- Establish measured cost and a migration deadline before employee use.

## Non-goals

- No employee names, email addresses, roster identifiers, quiz history, scores,
  credentials, or eligibility records.
- No account registration, login, Ranked gameplay, assignment persistence,
  score settlement, leaderboard, or prize processing.
- No production service-level claim and no public launch.
- No deletion or reconfiguration of the Ubuntu development computer.
- No native PostgreSQL cluster, root helper, Docker installation, router rule,
  or home-network exposure.
- No assumption that an Azure student benefit can legally host the final UPS
  employee competition.

## Approaches considered

### Small paid VPS

A 2 GB Linux VPS would give full server control and predictable performance,
but the owner would be responsible for operating-system patches, PostgreSQL,
TLS, monitoring, backups, and recovery. It remains the fallback if Azure terms
or pricing do not fit.

### Azure Linux virtual machine

An Azure VM would preserve the native PostgreSQL design closely, but it repeats
the same server-administration burden as the home Linux machine and may consume
the student credit quickly. It does not make good use of Azure's managed
services.

### Azure managed application and database — selected

Azure App Service hosts FastAPI and Azure Database for PostgreSQL Flexible
Server hosts PostgreSQL. This reduces host administration and supports a
clear separation between application and data. It requires adapting native
PostgreSQL administrator tests because Azure does not grant operating-system
or unrestricted PostgreSQL superuser access.

## Architecture

```text
GitHub Pages Practice frontend
              |
              | HTTPS, explicit CORS origin
              v
Azure App Service (Linux, Python 3.14, FastAPI)
              |
              | PostgreSQL TLS, least-privilege runtime role
              v
Azure Database for PostgreSQL Flexible Server
              |
              +-- managed backup retention
              +-- guarded fictional restore test

Owner bootstrap/deploy --> Azure staging resource group
GitHub Actions -- OIDC --> later resource-group deployments
App Service managed identity --> Microsoft Entra PostgreSQL role
Azure Monitor <--------------- sanitized application/platform telemetry
```

## Subscription and cost gates

The screenshot observed on November 9, 2026 shows an Azure for Students
subscription with USD 100 remaining and an expiry date of November 9, 2027.
That screenshot is evidence of the account balance, not proof that every
resource in this design is free.

Before creation, a read-only preflight must confirm all of the following:

- the exact active subscription and tenant;
- the spending limit remains enabled;
- the available App Service and PostgreSQL free-service entitlements;
- the selected region supports Linux App Service, Python 3.14, and the chosen
  PostgreSQL version and SKU;
- a portal pricing estimate for compute, database, storage, backup, monitoring,
  public IPv4, and outbound transfer;
- no unrelated resource with the planned names already exists.

The initial smoke deployment may use App Service F1 only if the subscription
offers it. F1 has no production SLA and is limited to development testing. A
paid tier requires a separate owner approval after a written monthly estimate.
PostgreSQL Flexible Server may be created only if the portal confirms the
applicable 12-month free allowance or the owner separately approves its
estimated charge.

Create a USD 5 monthly staging budget with notifications at 50, 80, and 100
percent. Budget alerts do not stop charges. Keep the subscription spending
limit enabled as the hard account-level stop. Tag
every resource with `project=sort-tester-live`, `environment=staging`,
`data-classification=fictional-only`, and `expires-on=2027-10-09`.

## Region and resource boundary

Use one Azure region for all resources. Prefer `eastus2`; use `eastus` only if
preflight proves that a required free SKU or runtime is unavailable in
`eastus2`. A dedicated resource group named `rg-sort-tester-staging` is the
deletion and cost boundary. The owner performs one reviewed subscription-scope
bootstrap to create this group. GitHub's deployment identity receives access
only inside that group and cannot create or modify other groups.

The first bootstrap requires the resource group to be absent. Later deployments
must match every existing resource by exact ID, name, type, and a reviewed
deployment manifest; matching tags alone never authorize adoption.

Resource names are generated from a short, nonsecret suffix recorded in the
deployment manifest. The suffix prevents global-name collisions; it is not an
authentication secret.

## Network model

Only App Service accepts requests from the general public. HTTP redirects to
HTTPS. During fictional staging, PostgreSQL retains a publicly resolvable
endpoint protected by exact firewall rules, TLS, and Entra authentication; it
never accepts all networks and never uses the broad "Allow Azure services"
rule.
During the free staging phase, PostgreSQL's public endpoint may allow only the
documented App Service outbound IPv4 addresses and one temporary `/32` address
used by a guarded migration or restore check. The temporary rule is removed in
guaranteed cleanup and its removal is verified.

Any App Service tier change invalidates the assumed outbound-address set. The
deployment must re-read the platform's current outbound addresses, reconcile
the database firewall, and prove a new TLS connection before serving traffic.
Before employee data, App Service must move to a paid tier that supports virtual
network integration, PostgreSQL must receive a private endpoint, and public
database access must be disabled and tested. Azure currently permits a server
created in public-access mode to add private endpoints and later disable public
access. A clean private production environment remains an allowed alternative.

CORS allows only the exact production GitHub Pages origin and explicitly
approved loopback development origins. CORS is not authentication.

## Identity and secrets

- GitHub Actions authenticates to Azure with OpenID Connect. No long-lived
  Azure client secret or publish profile is stored in GitHub.
- App Service receives a system-assigned managed identity.
- PostgreSQL uses Microsoft Entra-only authentication. The App Service identity
  obtains short-lived tokens for the PostgreSQL resource; the running
  application has no permanent database password.
- The owner configures an Entra administrator for initial provisioning. A
  separate GitHub OIDC principal may be mapped to a restricted migration role;
  it is not a PostgreSQL administrator.
- The application identity maps to a dedicated `sort_tester_runtime`
  PostgreSQL role with only CONNECT, schema USAGE, and required table DML. It
  cannot create roles, databases, schemas, extensions, or tables and cannot
  grant its privileges.
- Tokens and identities never enter Git, workflow output, command arguments,
  screenshots, application logs, or test reports.
- The Entra PostgreSQL administrator is used only for initial provisioning and
  guarded recovery tasks, never by the running application.

## Database foundation adaptation

The paused native-Linux proposal is not executed against Azure. Azure Managed
PostgreSQL does not provide the native `postgres` operating-system identity,
cluster configuration ownership, or unrestricted superuser semantics assumed
by that proposal.

The Azure foundation creates a fictional `foundation_probe.records` table and
separate administrator and runtime roles within the privileges Azure permits.
Tests verify connection identity, TLS use, committed writes, rollback, restart
persistence, runtime DML, runtime DDL denial, cross-database denial, sanitized
errors, and guarded restore behavior. The foundation is not the final users,
attempts, scores, or ranking schema and does not close Issue #6.

## Deployment and configuration

Azure resources are described with Bicep. The owner executes a one-time
subscription-scope bootstrap to create the resource group and performs the
first reviewed resource-group-scoped deployment. After the application and
database foundations are verified, a GitHub OIDC identity scoped only to that
group takes over later deployments. Deployments run `what-if` first and stop
for review when they would delete or replace a resource.

The FastAPI process starts from the existing `backend.main:app`. `/health`
continues to prove that the web process responds and must not query PostgreSQL.
A separate `/ready` endpoint may be added for a bounded database readiness
probe; it returns only `{"status":"ready"}` or a sanitized 503 response and
never exposes hostnames, usernames, SQL, or driver errors.

GitHub Pages remains the frontend host. No frontend visual change is part of
this plan. A staging API URL is not published into the employee interface until
the owner separately approves the integration.

## Observability and privacy

Platform and application telemetry records request identifiers, status codes,
latency, deployment revision, and sanitized error codes. It must not record
answers, quiz payloads, credentials, database connection strings, request
bodies, email addresses, roster identifiers, or player names. Retention starts
at 30 days with the smallest practical daily ingestion cap. Alerts cover
unavailable health checks, repeated 5xx responses, database connection failure,
and approaching cost thresholds.

## Verification gates

The deployment progresses only when each gate is recorded:

1. **Inventory:** subscription, terms boundary, free entitlements, region,
   estimate, spending limit, and names verified without creating resources.
2. **Infrastructure:** `what-if` reviewed; tagged staging resources created;
   public exposure matches the network model.
3. **Application:** hosted `/health` returns exact HTTP 200 JSON over HTTPS;
   HTTP redirects; unknown routes return 404; no database is required.
4. **Database:** fictional probe tests pass through a new TLS connection;
   prohibited runtime operations fail.
5. **Recovery:** a fictional sentinel survives restart; an actual guarded
   backup restore is read and cleaned up; original data remains unchanged.
6. **Load:** thirty simulated clients complete the agreed health/API workload
   without functional errors; results are not described as gameplay capacity.
7. **Cleanup:** a dry run lists only tagged project resources; a disposable
   rehearsal removes them and verifies absence without touching unrelated
   resources.
8. **Employee-data decision:** student-use terms, paid-tier costs, private
   networking, business schema, authentication, retention, incident response,
   and backup recovery are separately approved.

## Failure and rollback

Every deployment records resource IDs and the Git commit. Application rollback
redeploys the last verified artifact. Database changes use forward migrations
plus tested restore procedures rather than destructive ad-hoc reversal.
Temporary firewall rules, restore databases, and test credentials use
guaranteed cleanup; cleanup failure is a failed verification, not success.

If the credit expires, the spending limit disables resources, Azure student
terms do not permit the intended pilot, costs exceed the approved estimate, or
secure database connectivity cannot be established at the approved tier, stop
the Azure track. Export only fictional test artifacts, remove the staging
resource group after reviewed backup/cleanup, and return to the paid VPS
alternative. November 9, 2027 is not the operational deadline: migration or
renewal must be complete by October 9, 2027.

## Approval boundary

Approval of this design authorizes an implementation plan and fictional-data
staging work only. It does not authorize charges beyond confirmed free
allowances, removal of the spending limit, employee data, production launch,
subscription upgrade, domain purchase, issue closure, or merge to `main`.
