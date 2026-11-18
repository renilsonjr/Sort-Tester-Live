# Azure infrastructure

This directory holds the validated **Azure Container Apps** path for the
fictional-data-only FastAPI staging work. The earlier App Service plan
(`main.bicep`, `bootstrap-resource-group.bicep`, `preflight.py` and related
tests) was historical and has been removed from the tree — the full files
remain in git history (see the 2026-11-09 staging-host documents under
`docs/superpowers/`).

## Current contents

**The live deployable is `container-apps-app.bicep`.** It is the whole app
on one origin — FastAPI serving `/api` and the frontend — running on a
VNet-injected environment, pulling its image from the project's own
registry as a managed identity, and reading its database URL from Key
Vault. `container-apps-app.md` is its runbook, and the section to read
before deploying is §4: every parameter Azure already holds must be passed
again, or the template's defaults quietly undo it.

The two templates below it are **history, not deployables**: the spike was
deleted after its test, and the API-only staging template was retired when
the app template replaced it.

- `container-apps-app.bicep` (+ `.md`, `.dockerignore`) — the deployed app.
- `app.Dockerfile` — its image: Alpine, non-root, runtime dependencies
  only, with pip removed after install.
- [[pool-verification-2026-11-18]] — observed eight-connection cap,
  latency/throttling measurements, temporary capacity experiment and
  verified return; pool protection accepted in #196, mandatory pilot
  performance validation remains open in #13.
- `diagnostics/` — bounded HTTP burst generator and read-only pool/CPU
  observers; runbook §10 explains the two-terminal method.
- [[final-verification-2026-11-18]] — H-1/H-2, Ranked/owner/recovery,
  runtime-role and bounded mixed-traffic evidence; full app-template preview
  and its seven omissions. Final audit and pilot acceptance remain open.
- `network.bicep` — the VNet, private DNS zone and private endpoint the
  database is reached through (audit H-4).
- [[shared-resource-locks]] (+ `.bicep`) — independently deployable
  `CanNotDelete` locks for the existing PostgreSQL, Application Insights
  and Log Analytics resources; applied/read-back verified 2026-11-18,
  no-change preview and unchanged app checks passed. The owner accepted
  configuration-based verification on 2026-11-18; no real deletion was
  attempted. Section 7 records evidence and the acceptance decision.
- `runtime-identity.bicep` (+ `.md`) — the app's identity and its two
  resource-scoped roles: pull from the registry, read from the vault.
- `security-foundation.md` — how the registry and vault were created.
- `container-apps-spike.bicep` — disposable spike template (validated
  2026-11-10; app and environment deleted after the test).
- `container-apps-staging.bicep` — guarded API-only staging template, pinned to
  the scanned GHCR image digest.
- `container-apps-staging.md` — staging runbook with verification and scan
  evidence.
- `CONTAINER-APPS-SPIKE.md` — spike evidence record (digests, workflow runs,
  cleanup).
- `spike.Dockerfile` (+ `.dockerignore`) — Alpine-based, non-root image build.

## Standing boundary

Fictional data only. No employee data, no production launch, no removal of
the subscription spending limit.

The old wording also forbade "no PostgreSQL connection from the app host".
That was true of the API-only staging template and stopped being true when
the app template shipped: the app reads its own database, over a private
endpoint, as a least-privilege role. Left standing it would have read as a
rule being broken rather than a rule that was superseded.

## Real names are not in here

Resource names — the server, the registry, the vault — live in the private
inventory, not in tracked documents (audit L3). They are not credentials,
but on a public repository they say exactly which resources to probe, and
vault and registry names resolve in global DNS. Documents use placeholders
like `<key-vault>`; `backend/tests/test_docs_hygiene.py` fails if a real
one comes back, matching the *shape* of these names rather than listing
them, since a guard that spelled them out would be the leak it prevents.
Azure deployments require explicit owner approval via a reviewed what-if.

## Start here

Read `container-apps-staging.md` before any deployment, and
`CONTAINER-APPS-SPIKE.md` for the spike history that justifies the current
design.
