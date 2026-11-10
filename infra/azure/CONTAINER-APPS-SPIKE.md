# API-only Container Apps spike — prepared, not deployed

This disposable test runs the existing `/health` FastAPI service in North Central
US. It creates one workload-profile environment with only Consumption and one
app: 0–1 replicas, 0.25 CPU, 0.5 GiB RAM, HTTPS ingress to port 8000. It creates
no database, registry, managed identity, secrets, storage, or monitoring workspace.
Log ingestion is disabled. No employee or competition data belongs in this test.

## Gates before build, publish or deployment

Review `container-apps-spike.bicep` and compile it in Cloud Shell. Confirm the
subscription's policy, Microsoft.App registration, regional Consumption quota,
and actual free compute/request grant balance. Scale-to-zero and max-one are
usage bounds, not a dollar cap. Refresh the regional estimate and agree a short
test window (proposed: 30 minutes); retain the subscription spending limit.
Stop if a paid workload profile or unexpected resource appears in what-if.

The Dockerfile uses `python:3.14.10-slim` and the existing exact requirements.
Before building, confirm that base tag exists and record its immutable digest;
pin `FROM` to that verified digest for the published artifact. Build availability
were verified via GitHub Actions on 2026-11-10; see below.

Building/publishing is a separate action. The proposed public package is
`ghcr.io/renilsonjr/sort-tester-live-api-spike`; confirm package publication and
GitHub permissions first. No registry secret is needed by Azure when the package
is public. Verify anonymous pull access, Linux amd64 compatibility, package
contents and image scan before deployment. Supply the 64 hexadecimal characters
of its immutable SHA-256 digest as `imageSha256`; never supply a mutable tag.

When approved, build from the repository root using
`docker build -f infra/azure/spike.Dockerfile ... .`. Its Dockerfile-specific ignore
file permits only `backend/main.py` and `backend/requirements.txt` in the context;
the Ranked bank, tests, local configuration and credentials are excluded. The
process runs as UID 10001 and uses one Uvicorn process without reload/access logs.

## Test and evidence

Run a container smoke check locally before publishing: `/health` must return
200 and exactly `{"status":"ok"}`; an unknown route must return 404. Verify the
runtime UID is 10001 and no bank/config/secrets are present. Then review Azure
what-if against exact recorded resource IDs in the dedicated staging group.
An existing unrelated resource or replacement/deletion stops the test.

After the separately approved deployment, record the Git commit/image digest,
exact two resource IDs and start time. Test HTTPS `/health`, HTTP-to-HTTPS
redirect and unknown-route 404 from the browser/phone. Let replicas reach zero,
then measure the next request's cold-start latency separately from warm latency.
Inspect live console/system logs if startup fails; persistent log ingestion is
disabled. Do not enable paid monitoring to troubleshoot without review.

At 30 minutes or any unexpected usage/failure, stop requests and deactivate the
recorded active revision. This is only an immediate pause: remove the exact
spike app, then its exact spike environment after checking IDs, tags and that
no other app uses it. Do not delete the shared resource group or use wildcard
cleanup. Verify both IDs are absent and record cleanup success; review delayed
cost reports and free-grant consumption afterwards. Keep any failure visible.

## Verification status

Local Python/JavaScript regressions can verify the unchanged API behavior.
`.github/workflows/container-apps-spike.yml` is a manually triggered workflow
that builds the image on a GitHub-hosted Linux runner (no local Docker
required), verifies the runtime UID is 10001, checks that the Ranked bank,
data, tests, dev config and `.git` are absent, and smoke-tests `/health`
(200, exact body) and an unknown route (404). A separate manually gated
`spike-publish` job publishes the image only when explicitly dispatched with
`confirm_publish: true`.

Base image `python:3.14.10-slim` exists; verified manifest digest:
`sha256:9aaa474097d094040649f2162a627c0049b408f52138d980916788d80f04802f`.
Pin `FROM` to this digest before any published artifact is built.

Workflow runs 42772062073 and 42774893957 on `main` (2026-11-10) confirmed: the
image builds from repository root with the spike Dockerfile (base pinned to the
verified digest); the runtime UID is 10001; the Ranked bank, data, tests, dev
config and `.git` are absent; `/health` returned 200 with exactly
`{"status":"ok"}`; an unknown route returned 404.

Workflow run 42777173808 (2026-11-10, manual dispatch with `confirm_publish:
true`) published the image:

`ghcr.io/renilsonjr/sort-tester-live-api-spike@sha256:0de6ceb356b0f82bb3dc6d3ddca263485675bd84cc3548251ef3ac01cf9baded`

Anonymous manifest pull verified HTTP 200 on 2026-11-10; Azure can pull the
image without registry credentials. Use exactly the 64 hex digest characters
above (without the `sha256:` prefix) as the bicep `imageSha256` parameter.
Nothing has been deployed; no resources exist in Azure for this spike.

Image publish, base-digest pinning, bicep compile and what-if (2026-11-10)
are done. What-if showed exactly 2 creates and 4 existing resources ignored;
zero Delete/Replace.

Live deployment and verification (2026-11-10, owner-approved, 30-minute window
from 07:56 UTC):

- `az deployment group create` succeeded in ~46s with `--confirm-with-what-if`.
- Created: `ca-sort-spike-spike01` (Container App) and `cae-sort-spike-spike01`
  (Consumption managed environment). The four pre-existing resources were
  untouched.
- FQDN: `ca-sort-spike-spike01.proudwave-d6b6a65c.northcentralus.azurecontainerapps.io`
- `GET /health` returned HTTP 200 with `{"status":"ok"}` (first request ~0.39s;
  warm requests ~0.09-0.24s). Unknown route returned HTTP 404.
- Image: `ghcr.io/renilsonjr/sort-tester-live-api-spike@sha256:0de6ceb356b0f82bb3dc6d3ddca263485675bd84cc3548251ef3ac01cf9baded`
- Deployment resource ID: `.../providers/Microsoft.Resources/deployments/container-apps-spike`

Cleanup at or before 08:26 UTC (not yet executed at time of writing): delete
`ca-sort-spike-spike01`, then `cae-sort-spike-spike01`; verify both IDs are
absent; never delete or modify the four pre-existing resources. Image scan and
compute-grant/cost-estimate review remain pending.
