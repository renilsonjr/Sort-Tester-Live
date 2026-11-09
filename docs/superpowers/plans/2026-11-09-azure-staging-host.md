# Azure Staging Host Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deploy the existing FastAPI health service and a fictional PostgreSQL foundation to a cost-bounded Azure staging environment without exposing employee data or changing the Practice interface.

**Architecture:** GitHub Pages remains the frontend host. Azure App Service on Linux hosts FastAPI and authenticates to Azure Database for PostgreSQL Flexible Server through its managed identity and short-lived Microsoft Entra tokens. GitHub Actions deploys with a resource-group-scoped OIDC identity after an owner-run resource-group bootstrap. Bicep makes the staging resources reproducible and a guarded cleanup path removable.

**Tech Stack:** Python 3.14, FastAPI, Uvicorn, Psycopg 3.3.8, Azure Identity 1.27.0, Bicep, Azure CLI, Azure App Service, Azure Database for PostgreSQL Flexible Server 18, Microsoft Entra, Azure Monitor, GitHub Actions OIDC

**Spec:** `docs/superpowers/specs/2026-11-09-azure-staging-host-design.md`

## Global Constraints

- Use the shared `codex/ranked-mode` branch; do not create a separate branch or worktree.
- Preserve the existing GitHub Pages UI and Practice behavior.
- Use fictional probe data only; no employee or competition data may enter Azure.
- Make no Azure resource until the read-only inventory and cost gate is reviewed by the owner.
- Keep the Azure subscription spending limit enabled and require separate approval for any paid tier.
- Use Entra-only PostgreSQL authentication; never create an application database password or log, commit, echo, artifact, or place an Azure token in a process argument.
- PostgreSQL must require TLS and must never use `0.0.0.0/0`, `::/0`, or "Allow Azure services" access.
- `/health` remains database-independent; database readiness is separate and sanitized.
- Use test-driven development, one reviewed commit per task, and run all existing backend and JavaScript regressions before handoff.
- Do not merge, close Issue #6, remove issue dependencies, publish employee access, or change branch protection.

## Review Focus

- An unexpected existing Azure resource must stop deployment instead of being adopted or replaced; Task 2 tests the ownership/tag guard.
- A paid or unavailable free SKU must stop before creation and produce a reviewable estimate; Task 1 tests the entitlement gate.
- A changed App Service outbound address set must reconcile PostgreSQL rules before a new connection is allowed; Task 4 tests drift handling.
- A database or secret failure must return a sanitized readiness response and logs; Task 5 tests disclosure prevention.
- Partial deployment or failed restore cleanup must remain visibly failed and preserve unrelated resources; Tasks 6 and 8 test cleanup behavior.

---

### Task 1: Read-only Azure subscription and cost preflight

**Files:**
- Create: `infra/azure/preflight.py`
- Create: `infra/azure/README.md`
- Create: `backend/tests/test_azure_preflight.py`
- Create at execution time outside Git: `$HOME/.local/state/sort-tester-live/azure-preflight-<timestamp>.json`

**Interfaces:**
- Consumes: Azure CLI JSON from authenticated, read-only `az account`, provider,
  SKU, resource-list, consumption, and budget queries.
- Produces: `PreflightDecision(allowed: bool, blockers: tuple[str, ...], evidence: dict[str, object])` and a secret-free JSON report for owner review.

- [ ] **Step 1: Write failing preflight tests**

  Add unit cases asserting that `evaluate_preflight(evidence: Mapping[str, object]) -> PreflightDecision` rejects an unexpected subscription, disabled spending limit, existing unowned resource, unavailable Python 3.14/Linux runtime, unavailable PostgreSQL/free allowance, absent price estimate, and estimated paid usage without owner approval. Assert that the accepted case records `eastus2`, falling back to `eastus` only when the complete required set is unavailable in `eastus2`.

- [ ] **Step 2: Run the preflight unit tests and verify failure**

  Run: `backend/.venv/bin/python -m unittest backend.tests.test_azure_preflight -v`

  Expected: FAIL because `infra.azure.preflight` does not exist.

- [ ] **Step 3: Implement the pure evaluator and read-only collector**

  Implement `evaluate_preflight(...)` separately from `collect_preflight(az: AzureCli) -> dict[str, object]`. The collector may execute only documented read commands, redacts tenant/user identifiers in the saved report, and refuses resource creation or registration. Create the outside-checkout state directory with mode `0700` and report with mode `0600`; refuse symlinks and existing output. Document exact Cloud Shell commands and the manual portal checks for student offer terms, free-service counters, spending limit, and pricing calculator.

- [ ] **Step 4: Run tests and inspect a real read-only report with the owner**

  Run the unit test above, then run `python3 infra/azure/preflight.py --output <outside-git-path>` in Azure Cloud Shell. Confirm the command lists no create/update/delete operation. Compare the report with the portal screenshots and price estimate. Stop if any gate is unresolved.

- [ ] **Step 5: Commit the reviewed preflight tool and documentation**

  Commit message: `feat: add guarded Azure staging preflight`

### Task 2: Define the tagged Azure staging resource boundary

**Files:**
- Create: `infra/azure/bootstrap-resource-group.bicep`
- Create: `infra/azure/main.bicep`
- Create: `infra/azure/main.staging.bicepparam`
- Create: `infra/azure/validate.py`
- Create: `backend/tests/test_azure_infrastructure_contract.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: approved Task 1 report, selected region, nonsecret deployment suffix, and a secure local parameter file outside Git.
- Produces: owner-created `rg-sort-tester-staging`, tagged App Service, Flexible Server, monitoring resources, and secret-free deployment outputs.

- [ ] **Step 1: Write failing infrastructure-contract tests**

  Assert that parsed Bicep source requires the four mandatory tags, HTTPS-only App Service, TLS PostgreSQL 18 with Entra-only authentication, backup retention, system-assigned identity, capped telemetry, no broad firewall rule, and no literal credential. First bootstrap must reject any existing resource group. Later validation rejects resources absent from the exact deployment manifest even when their tags match.

- [ ] **Step 2: Run contract tests and verify failure**

  Run: `backend/.venv/bin/python -m unittest backend.tests.test_azure_infrastructure_contract -v`

- [ ] **Step 3: Implement Bicep definitions and the ownership validator**

  `bootstrap-resource-group.bicep` is executed once by the owner and creates only the absent dedicated resource group. `main.bicep` defines resources within it, including PostgreSQL Entra-only authentication and an Entra administrator child resource whose owner principal name, object ID, type, and tenant ID are explicit nonsecret parameters. The owner performs the first `main.bicep` deployment; GitHub takes over only after Task 7. `main.staging.bicepparam` contains only nonsecret defaults. Ignore local deployment manifests and generated Bicep JSON. `validate_existing_resources(report, manifest, expected_tags) -> ValidationResult` must refuse adoption, deletion, or replacement unless exact IDs, names, types, and tags match.

- [ ] **Step 4: Build and run `what-if` without creating resources**

  Run `az bicep build --file infra/azure/bootstrap-resource-group.bicep`, `az bicep build --file infra/azure/main.bicep`, unit tests, secret scanning, and owner-run `az deployment sub what-if` for the bootstrap. After the owner creates the group, the owner runs a resource-group-scoped `what-if` and first deployment for `main.bicep`. Verify a fresh owner Entra-token PostgreSQL connection before any runtime mapping or app deployment. If the server exists but the administrator child resource or login verification fails, stop; do not enable app access. Retry only the exact child resource or, after a reviewed exact-ID cleanup, remove the newly tagged server. Save redacted reports outside Git. Owner reviews resource types, SKUs, region, tags, and estimated monthly cost before creation.

- [ ] **Step 5: Commit the reviewed infrastructure definition**

  Commit message: `feat: define Azure staging resource boundary`

### Task 3: Deploy the database-independent FastAPI health service

**Files:**
- Create: `backend/azure_startup.py`
- Create: `backend/tests/test_azure_startup.py`
- Create: `scripts/build-azure-backend.py`
- Create: `backend/tests/test_azure_package.py`
- Modify: `backend/README.md`
- Modify: `infra/azure/main.bicep`

**Interfaces:**
- Consumes: `backend.main:app`, an exact allowlist of nonsecret origins, and the reviewed runtime manifest.
- Produces: deterministic ZIP containing root `requirements.txt`, `backend/**/*.py`, and required `backend/data/**/*.json`; startup command `python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000`; and an HTTPS endpoint with unchanged `/health` behavior.

- [ ] **Step 1: Write failing startup and configuration tests**

  Assert that the startup builder returns the exact reviewed command, never enables reload, and never embeds secrets. Packaging tests require a root copy of `backend/requirements.txt`, runtime Python and JSON files, a SHA-256 manifest, stable byte ordering/timestamps, and exclusions for tests, virtual environments, local configuration, Git metadata, and secrets. Extend health/CORS tests for exact staging and GitHub Pages origins without wildcard or credentials.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `backend/.venv/bin/python -m unittest backend.tests.test_azure_startup backend.tests.test_main -v`

- [ ] **Step 3: Implement the minimal startup adapter and documentation**

  Keep `create_app()` and `/health` database-independent. Build a deterministic deployment directory and ZIP, copy the dependency file to ZIP root for Oryx, enable `SCM_DO_BUILD_DURING_DEPLOYMENT=true`, and configure App Service Python 3.14 with the exact startup command. Document local equivalence, Azure log locations, deployment revision, artifact digest, and rollback to the prior artifact.

- [ ] **Step 4: Deploy only after Task 2 creation approval and test HTTPS behavior**

  Verify exact HTTPS `GET /health` returns HTTP 200 and `{"status":"ok"}`, HTTP redirects to HTTPS, unknown route returns 404, malformed CORS origin prevents startup, and stopping PostgreSQL does not change `/health`. Record the Azure resource ID and Git commit without subscription or tenant identifiers.

- [ ] **Step 5: Run all local regressions and commit**

  Run backend unit tests, `node --test tests/*.test.mjs`, Ranked seed-42 check, and `git diff --check`.

  Commit message: `feat: run FastAPI health service on Azure staging`

### Task 4: Establish least-privilege managed PostgreSQL access

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/database/__init__.py`
- Create: `backend/database/config.py`
- Create: `backend/database/connection.py`
- Create: `backend/database/sql/azure_foundation.sql`
- Create: `backend/tests/test_database_config.py`
- Create: `backend/tests/test_database_connection.py`
- Create: `backend/integration_tests/__init__.py`
- Create: `backend/integration_tests/test_azure_postgresql.py`
- Modify: `infra/azure/main.bicep`

**Interfaces:**
- Consumes: nonsecret settings `SORT_TEST_DB_HOST`, `SORT_TEST_DB_NAME`, `SORT_TEST_DB_PRINCIPAL`, `SORT_TEST_DB_SSLMODE=require`; App Service `ManagedIdentityCredential`; and injected fake/local credentials for tests and owner-run development.
- Produces: `DatabaseConfig.from_environment(env)`, `open_connection(config, token_provider)`, a fictional `foundation_probe.records` fixture, and Entra-mapped restricted runtime/migrator roles.

- [ ] **Step 1: Pin and prove the PostgreSQL driver on Linux and Windows**

  Add exact pins `psycopg[binary]==3.3.8` and `azure-identity==1.27.0` without changing existing exact pins. Reverify release availability, resolve and commit every new compatible transitive dependency at an exact version, and compare fresh Python 3.14 Linux and Windows resolutions before committing. Do not replace the requirements with one platform's uncontrolled `pip freeze`. Fresh-install the final shared file on both systems, run `pip check`, and import both direct libraries.

- [ ] **Step 2: Write failing config and connection tests**

  Assert required settings, fixed database identity, TLS requirement, token audience `https://ossrdbms-aad.database.windows.net/.default`, bounded connect/statement timeouts, no default-database fallback, sanitized stable errors, and no token/network request during module import or FastAPI startup. Mock token and driver failures to prove no hostname, principal, token, SQL, or raw traceback reaches client-safe errors.

- [ ] **Step 3: Implement configuration and connection boundaries**

  Define `DatabaseConfig`, `DatabaseErrorCode`, `TokenProvider`, and `open_connection(config: DatabaseConfig, token_provider: TokenProvider) -> context manager[Connection]`. The App Service provider uses `ManagedIdentityCredential`; owner development uses an explicit Azure CLI credential only when selected, never an implicit credential chain. Acquire a fresh bounded-lifetime token for each new unpooled connection. Use parameterized SQL and explicit transaction boundaries.

- [ ] **Step 4: Create and test the fictional Azure foundation**

  After Task 2 proves the owner's Entra administrator login, use `pgaadauth_create_principal_with_oid` to map the App Service identity to `sort_tester_runtime` as nonadmin. Task 7 later maps the GitHub OIDC service principal to `sort_tester_migrator`. Grant only required CONNECT/USAGE/DML to runtime and explicit fixture/migration privileges to migrator. The fixture uses an application-generated valid UUID primary key plus a separately constrained text marker equal to `FICTIONAL_AZURE_FOUNDATION`. Integration tests prove TLS, role/database identity, commit, rollback, runtime DML, DDL denial, role/database creation denial, privilege delegation denial, and cross-database denial.

- [ ] **Step 5: Reconcile and test PostgreSQL firewall drift**

  Implement `expected_database_firewall(possible_outbound_ips, temporary_runner_ip=None) -> tuple[Ipv4Rule, ...]`. Permit every exact IPv4 `/32` returned by App Service `possibleOutboundIpAddresses`, never a regional range or Azure-wide service rule. A hosted integration run may add one exact runner `/32` only after identity validation and must remove and verify it in `always()` cleanup. Tier changes are maintenance events: capture the old set, stop serving, change tier, read and add the new set, prove a new TLS connection, then remove stale rules; cleanup failure blocks traffic.

- [ ] **Step 6: Run focused, full, and hosted compatibility tests; commit**

  Commit message: `feat: add Azure PostgreSQL foundation connection`

### Task 5: Add sanitized database readiness and telemetry

**Files:**
- Modify: `backend/main.py`
- Create: `backend/readiness.py`
- Create: `backend/telemetry.py`
- Create: `backend/tests/test_readiness.py`
- Create: `backend/tests/test_telemetry.py`
- Modify: `infra/azure/main.bicep`

**Interfaces:**
- Consumes: `open_connection(config, token_provider)` from Task 4, application-injected `DatabaseConfig` and `TokenProvider` dependencies, and a generated request identifier.
- Produces: `check_database_readiness(config, token_provider) -> ReadinessResult`, `GET /ready`, and structured sanitized telemetry fields.

- [ ] **Step 1: Write failing readiness and redaction tests**

  Assert ready returns HTTP 200 with `{"status":"ready"}`; timeout, authentication, configuration, and transaction failures return HTTP 503 with `{"status":"unavailable"}`. Assert `/health` remains 200. Feed credentials, DSNs, SQL, email-like strings, roster-like values, and driver traces through telemetry and assert none is emitted.

- [ ] **Step 2: Run focused tests and verify failure**

  Run: `backend/.venv/bin/python -m unittest backend.tests.test_readiness backend.tests.test_telemetry -v`

- [ ] **Step 3: Implement bounded readiness and sanitized telemetry**

  Execute a read-only `SELECT 1` with the Task 4 timeouts. The application dependency container supplies the production `DatabaseConfig` and managed-identity provider; tests inject a fake provider directly without changing production environment variables. Log only request ID, route, status, latency bucket, deployment revision, and stable error code. Configure 30-day retention and the smallest practical daily telemetry cap.

- [ ] **Step 4: Verify real success and failure states**

  Verify hosted readiness while PostgreSQL is available, while a deliberately invalid fake token provider is injected in an isolated test deployment, and after restoration. Confirm tokens and identity details are absent from App Service and Azure Monitor output. Restore the managed-identity provider and verify a newly acquired token without exposing it.

- [ ] **Step 5: Run regressions and commit**

  Commit message: `feat: add sanitized Azure database readiness`

### Task 6: Prove restart persistence and guarded restore

**Files:**
- Create: `backend/database/azure_recovery.py`
- Create: `backend/tests/test_azure_recovery_safety.py`
- Create: `backend/integration_tests/test_azure_recovery.py`
- Modify: `infra/azure/README.md`

**Interfaces:**
- Consumes: exact expected subscription/resource-group/server/database IDs, a run UUID, and a fictional sentinel UUID.
- Produces: `RecoveryManifest`, guarded sentinel commands, guarded restore verification, and cleanup evidence.

- [ ] **Step 1: Write failing recovery-safety tests**

  Assert refusal on wrong subscription, resource group, tags, source server, target name, target ID, missing fictional marker, existing target, active unexpected connections, or incomplete manifest. Assert cleanup never uses wildcard selection, `--force`, fallback-by-name, or unrelated-resource deletion.

- [ ] **Step 2: Implement fixed-target guarded recovery operations**

  Generate a run UUID and exact expected IDs before action. Write and commit a fictional sentinel, restart the PostgreSQL Flexible Server without recreation, confirm the same resource ID and sentinel, then perform point-in-time restore to a uniquely tagged **new Flexible Server**. The manifest fixes source and target server IDs, restore timestamp, PostgreSQL version, SKU, storage, maximum temporary cost, temporary firewall rule, verification identity, and expiry. Azure PITR does not copy firewall rules; add and later remove only the exact temporary `/32`. Verify through a new restricted connection and delete only the exact recorded restored server.

- [ ] **Step 3: Execute a fictional recovery rehearsal with explicit cost review**

  Review the written maximum temporary restore cost before execution. Record timestamps, IDs, backup/restore method, sentinel value, checks, and cleanup without credentials. A cleanup failure remains an open failure and blocks further deployment.

- [ ] **Step 4: Run safety, integration, and regression suites; commit**

  Commit message: `test: prove Azure staging recovery safeguards`

### Task 7: Add secretless GitHub Actions deployment gates

**Files:**
- Create: `.github/workflows/azure-staging.yml`
- Create: `backend/tests/test_azure_workflow_contract.py`
- Modify: `infra/azure/README.md`
- Modify: `docs/security/branch-protection.md`

**Interfaces:**
- Consumes: GitHub environment approval, Azure federated credential identifiers, reviewed Bicep, and the verified application artifact.
- Produces: pull-request validation with no Azure mutation and manually approved staging deployment using OIDC.

- [ ] **Step 1: Write failing workflow-contract tests**

  Assert pinned official actions, minimum permissions, `id-token: write` only in the deploy job, `contents: read`, `persist-credentials: false`, no `pull_request_target`, no production secret, required environment approval, what-if before deploy, and an immutable application revision.

- [ ] **Step 2: Implement validation and deploy jobs**

  Pull requests run Bicep build/lint, unit tests, Node regressions, secret scan, package-digest validation, and static policy checks without Azure credentials. A first authenticated job creates a secret-free immutable `what-if` artifact tied to the exact commit and exits without mutation. A separate `azure-staging` environment-protected deploy job runs only after human approval, verifies the reviewed artifact digest and commit, logs in with OIDC, rechecks preflight, deploys that exact artifact, and runs HTTPS smoke tests.

- [ ] **Step 3: Configure and independently review Azure federation**

  After the owner creates and initially deploys the resource group, the owner creates the Azure application/service principal, environment-bound federated credential, and resource-group-only role assignment. Independently review their exact IDs and permissions. The owner then uses the verified Entra administrator connection to map this service principal to the nonadmin `sort_tester_migrator` PostgreSQL role. It may deploy tagged staging resources and obtain a PostgreSQL Entra token, but cannot create resource groups, modify subscription billing, remove the spending limit, manage unrelated groups, appoint an Entra database administrator, or assign broad privileges.

- [ ] **Step 4: Run a hosted validation and one approved staging deployment; commit**

  Verify the exact-head hosted workflow, artifact revision, OIDC authentication, health/readiness results, and absence of secrets in logs.

  Commit message: `ci: add guarded Azure staging deployment`

### Task 8: Verify load, cleanup, costs, and the employee-data hold

**Files:**
- Create: `backend/load_tests/azure_staging.py`
- Create: `backend/tests/test_azure_load_contract.py`
- Create: `infra/azure/cleanup.py`
- Create: `backend/tests/test_azure_cleanup.py`
- Create: `docs/superpowers/specs/2026-11-09-azure-staging-verification.md`
- Modify: `infra/azure/README.md`

**Interfaces:**
- Consumes: exact deployment manifest and the fictional staging API.
- Produces: bounded thirty-client measurements, a dry-run cleanup manifest, verified removal rehearsal, measured costs, and an explicit employee-data readiness decision.

- [ ] **Step 1: Write failing load and cleanup contract tests**

  Assert load generation sends no personal data, uses bounded concurrency/timeouts, reports failures honestly, and does not claim quiz/login capacity. Assert cleanup requires exact IDs and ownership tags, defaults to dry run, refuses unknown resources, and preserves the original failure when cleanup also fails.

- [ ] **Step 2: Implement bounded load and cleanup tools**

  `run_health_load(base_url: str, clients: int = 30) -> LoadReport` records status counts and latency percentiles without response bodies. `plan_cleanup(manifest, observed_resources) -> CleanupDecision` returns exact IDs and blockers; execution requires a separate explicit flag and GitHub environment approval.

- [ ] **Step 3: Run the thirty-client staging measurement**

  Exercise `/health` and `/ready` with fictional/no payloads. Record SKU, region, duration, request count, error count, p50/p95/p99, resource metrics, and actual Azure cost. State explicitly that this is not authentication, quiz, scoring, or 30-player gameplay validation.

- [ ] **Step 4: Rehearse cleanup on a disposable duplicate boundary**

  The owner—not the resource-group-scoped GitHub identity—creates a minimal disposable resource group containing inexpensive non-database test resources; do not duplicate PostgreSQL or the complete stack. Run a separate owner-authenticated `what-if`, set a written maximum temporary cost and automatic expiry, obtain owner approval, review exact IDs, and have the owner remove that exact group. Verify its absence and prove `rg-sort-tester-staging` and unrelated resources remain unchanged.

- [ ] **Step 5: Write the verification record and unresolved production gates**

  Record observed evidence, costs, failures, cleanup, and remaining decisions: Azure student permitted use, paid tier/private networking, business schema and migrations, authentication, data minimization/retention, incident response, off-service recovery, domain, and October 9, 2027 migration deadline.

- [ ] **Step 6: Run the complete local and hosted verification matrix; commit**

  Run `pip check`, all backend unit tests, opted-in Azure integration tests, all Node tests, Ranked seed-42 check, Bicep build/lint, workflow-contract tests, secret scan, and `git diff --check`. Verify the working tree is clean and the hosted checks correspond to the exact head.

  Commit message: `docs: verify Azure staging host readiness`

## Execution boundary

After this plan is approved, implementation still begins with Task 1 only.
No Azure resource is created until its read-only evidence and estimate are
returned to the owner and approved. Each later task receives its own test and
review gate. Completing all tasks proves fictional-data staging readiness; it
does not authorize employee data or close Issue #6.
