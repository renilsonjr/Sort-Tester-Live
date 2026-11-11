# Azure Container Apps API Staging Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the existing database-independent FastAPI health service in a bounded Azure Container Apps staging deployment while preserving GitHub Pages and existing Azure resources.

**Architecture:** A pinned public GHCR image runs on one Azure Container Apps Consumption app in one managed environment in `rg-sort-tester-staging`. The app exposes HTTPS `/health`, scales from zero to one replica, and has no database connection. Azure PostgreSQL integration is a separate plan after networking and cost review.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, Docker/GHCR, Azure Container Apps Consumption, Bicep, Azure CLI, GitHub Actions

**Spec:** `docs/superpowers/specs/2026-11-10-azure-container-apps-staging-design.md`

## Global Constraints

- Work on the shared `codex/ranked-mode` branch; reconcile current `main` without force-pushing or discarding history.
- Preserve GitHub Pages Practice behavior and appearance.
- Use fictional staging data only; no employee, account, Ranked, or prize data.
- Reuse `rg-sort-tester-staging` and its existing resources without adopting or changing them.
- Create only one Container Apps Consumption environment and one app for this stage; no PostgreSQL, VNet, public IP, registry, secret, or new logging workspace.
- Keep `GET /health` database-independent and exactly `{"status":"ok"}` at HTTP 200.
- Keep the Azure for Students spending limit enabled; require current free-grant, price, and `what-if` evidence before creation.
- Run reviewed tests with the owner at each step. Do not merge, close Issue #6, or publish employee access as part of this plan.

## Review Focus

- A changed or missing spike image digest must stop deployment rather than fall back to a mutable tag; Task 2 tests digest validation.
- An unrelated existing resource or Delete/Replace in `what-if` must stop deployment; Task 2 tests the exact target set.
- A failed image pull or startup must remain a failed deployment, with no success claim based only on resource creation; Task 3 tests live response behavior.
- A cloud health check must not be described as database or 30-player readiness; Task 3 records that boundary.
- A cleanup failure or delayed usage report must remain visible and must not remove the four existing resources; Task 3 verifies exact IDs and cost follow-up.

---

### Task 1: Reconcile the shared branch with the tested spike

**Files:**
- Merge: current `origin/main` into `codex/ranked-mode` (resolve overlapping spike files without discarding the verified fixes)
- Verify: `backend/tests/*.py`, `tests/*.test.mjs`, and `infra/azure/container-apps-spike.bicep`

**Interfaces:**
- Consumes: current local and remote branch histories and the recorded spike evidence on `main`.
- Produces: one tested shared branch containing both Ranked work and the successful Container Apps spike, with no unresolved conflict.

- [ ] **Step 1: After owner review, commit only the approved spec and plan, then record `git status`, branch tips, and the ahead/behind count after `git fetch`.** Stop if unrelated changes remain or either remote moved unexpectedly.
- [ ] **Step 2: Merge current `origin/main` into `codex/ranked-mode` without a force push.** Resolve spike-file overlap from the tested `main` version and inspect every resolution with `git diff --check` and `git diff`.
- [ ] **Step 3: Run `python3 -m unittest discover -s backend/tests -v` and `node --test tests/*.test.mjs`.** Expect zero failures; run the Ranked seed-42 check and compare its bank SHA-256 with the recorded fixture.
- [ ] **Step 4: Commit and push the reviewed reconciliation.** Verify the remote tip and clean worktree before infrastructure work.

### Task 2: Define and validate API-only Azure staging resources

**Files:**
- Create: `infra/azure/container-apps-staging.bicep`
- Create: `backend/tests/test_azure_container_app_staging.py`
- Create: `infra/azure/container-apps-staging.md`
- Reuse: `infra/azure/spike.Dockerfile`, `.github/workflows/container-apps-spike.yml`

**Interfaces:**
- Consumes: exact reviewed GHCR SHA-256 digest, `northcentralus`, existing resource-group identity, and current free-grant/price evidence.
- Produces: `ca-sort-api-stg` and `cae-sort-api-stg` definitions, exact-ID `what-if` review, and an owner-readable test/cleanup runbook.

- [ ] **Step 1: Write failing contract tests.** Assert only two create targets, required tags, Consumption profile, `minReplicas=0`, `maxReplicas=1`, 0.25 vCPU, 0.5 GiB, HTTPS-only port 8000, immutable image digest, no credentials, and no database or new logging resource. Reject malformed digest and any unexpected target.
- [ ] **Step 2: Run `python3 -m unittest backend.tests.test_azure_container_app_staging -v`.** Expect the new contract tests to fail before the Bicep file exists.
- [ ] **Step 3: Add `container-apps-staging.bicep` and its runbook using the merged, tested spike template as the source.** Keep the spike template and evidence intact. Document exact resource names, ownership check, image scan/pull check, free-grant/price gate, safe `what-if`, 30-minute first test window, and exact-ID cleanup.
- [ ] **Step 4: Run the new contract tests and `az bicep build --file infra/azure/container-apps-staging.bicep`.** Expect all tests and compilation to pass. Use Cloud Shell if local Azure CLI is unavailable.
- [ ] **Step 5: Review a fresh read-only Azure inventory and `az deployment group what-if`.** Require exactly two creates, all pre-existing resources unchanged, and zero Delete/Replace or other changes. Compare the inventory with the four resources recorded after the spike; stop if it differs or free-grant headroom is unconfirmed.
- [ ] **Step 6: Commit and push only the reviewed template, test, and runbook.** Confirm no generated parameters, identifiers, tokens, or private reports entered Git.

### Task 3: Deploy, verify, and account for the small API

**Files:**
- Record outside Git: `$HOME/.local/state/sort-tester-live/` deployment and cleanup evidence
- No application source changes are required for the previously verified `/health` image.

**Interfaces:**
- Consumes: Task 2 `what-if`, approved free-grant/price evidence, and the immutable image digest.
- Produces: observed HTTPS `/health` results, exact Azure resource IDs, cold/warm timing, usage follow-up, and cleanup or a reviewed extension decision.

- [ ] **Step 1: Recheck subscription, spending limit, image digest/anonymous pull, current free-grant use, and exact `what-if` immediately before creation.** Stop if any check changed.
- [ ] **Step 2: Deploy only the reviewed Bicep resources and record the UTC start and 30-minute test-window end outside Git.** Verify both resource IDs and tags; resource creation alone is not a pass.
- [ ] **Step 3: Test HTTPS `/health` for HTTP 200 and exact JSON, an unknown route for 404, and plain HTTP for upgrade or rejection.** Test from a second device, record cold and warm response times, and confirm the app can scale to zero without assuming gameplay capacity.
- [ ] **Step 4: Review cost and usage evidence.** If the service cannot be justified within measured free-grant headroom, remove only the exact app and environment after checking that no other app uses the environment. Verify both IDs absent and the four existing resources present. Follow up when delayed billing data appears.
- [ ] **Step 5: Record the result and limits in the runbook/issue.** Keep Issue #6 open because database readiness, recovery, and employee-use gates are not complete. Do not merge the staging template to `main` until the user reviews the tested result.

## Next plan

Design the existing Azure PostgreSQL connection after this API-only stage. Compare a private network with a temporary exact public firewall path using current Azure pricing and the server's actual networking mode. Implement managed-identity authentication, TLS, `/ready`, least-privilege roles, fictional persistence and recovery only after that design is reviewed.
