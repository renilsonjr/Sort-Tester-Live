# Azure infrastructure

This directory holds the validated **Azure Container Apps** path for the
fictional-data-only FastAPI staging work. The earlier App Service plan
(`main.bicep`, `bootstrap-resource-group.bicep`, `preflight.py` and related
tests) was historical and has been removed from the tree — the full files
remain in git history (see the 2026-11-09 staging-host documents under
`docs/superpowers/`).

## Current contents

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

Fictional data only. No employee data, no production launch, no PostgreSQL
connection from the app host, no removal of the subscription spending limit.
Azure deployments require explicit owner approval via a reviewed what-if.

## Start here

Read `container-apps-staging.md` before any deployment, and
`CONTAINER-APPS-SPIKE.md` for the spike history that justifies the current
design.
