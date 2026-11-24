# Additional infra policy validation — decision and evidence

Closes the tracking item from issue
[#205](https://github.com/renilsonjr/Sort-Tester-Live/issues/205), the
"additional policy or what-if validation" that audit follow-up #196 Task 20
deferred after the plain Bicep compile landed. Fictional-data staging only.
This record does not approve the employee pilot (#13) or expand Azure access.

## 1. The decision: offline static policy, not a live what-if

Two options were on the table (issue #205 item 1):

- **Offline policy validation** — compile the Bicep and assert invariants on the
  resulting ARM, with no Azure connection.
- **A live `az deployment group what-if`** — ask Azure to preview the change
  against the real resource group.

We chose **offline policy validation**, implemented in
[`policy/check.py`](policy/check.py) and wired into CI by
[`.github/workflows/infra-policy.yml`](../../.github/workflows/infra-policy.yml).

The deciding reason is item 4: a what-if that runs on a pull request needs a
credential that can read — and, to be meaningful, resolve against — the staging
subscription. That is exactly the broad, PR-triggerable Azure access the audit
set out to remove (H-5). Even a read-scoped federated credential on untrusted
PR code is a standing door into the subscription for a gate whose whole value is
that it runs on every change, including forks. Offline validation needs no
`az login`, no federated credential, no subscription id and no secret, so it can
gate every pull request while granting nothing.

We did not pick PSRule for Azure specifically. PSRule's value is its large
library of generic Azure best-practice rules, but this infrastructure is a
deliberately minimal, consciously-reviewed staging footprint (public network
access on the registry and vault, no diagnostic settings, single replica — all
recorded and accepted in the audit). A generic baseline would fire on those
accepted defaults, i.e. blanket-flag reviewed decisions, which is the mirror
image of the failure item 2 warns against. A small, repo-specific invariant set
says precisely what must not regress and stays quiet about what was already
reviewed. The checker is plain-Python and matches the existing offline pattern
in [`validate.py`](validate.py) ("never calls Azure … validates
already-collected JSON").

The what-if is not discarded. It remains the **manual, owner-reviewed**
pre-deployment step it already is (§5c of the runbooks), evidenced in
[`final-verification-2026-11-18.md`](final-verification-2026-11-18.md) and the
Task 20 lock application. This CI gate is a floor that runs on every change; the
owner's what-if review is the ceiling that runs before a deployment.

## 2. The checks, and why they are not a blanket Modify/Delete ignore

The checker does **not** diff two deployments, so it has no Modify/Delete
buckets to ignore (issue #205 item 2). It asserts invariants that the reviewed
baseline holds and that must keep holding, over the compiled ARM — the same
artefact a what-if would send Azure. A violation fails the job however it
arrived: a Modify that flips a flag, a Delete-and-recreate, or a new resource.

| Rule | Invariant | Resource |
| --- | --- | --- |
| `ingress-https-only` | `ingress.allowInsecure` is explicitly `false` (absence also fails — HTTPS-only must be stated, not defaulted) | `Microsoft.App/containerApps` |
| `image-digest-pinned` | every container image carries an `@sha256:` digest, never a mutable tag | `Microsoft.App/containerApps` |
| `no-plaintext-secret` | no `secrets[].value` holds an inline literal (a Key Vault reference or a parameter/function expression is fine) | `Microsoft.App/containerApps` |
| `registry-admin-off` | `adminUserEnabled` is `false` | `Microsoft.ContainerRegistry/registries` |
| `registry-anon-pull-off` | `anonymousPullEnabled` is `false` | `Microsoft.ContainerRegistry/registries` |
| `keyvault-rbac` | `enableRbacAuthorization` is `true` | `Microsoft.KeyVault/vaults` |
| `keyvault-soft-delete` | `enableSoftDelete` is `true` | `Microsoft.KeyVault/vaults` |
| `storage-shared-key-off` | `allowSharedKeyAccess` is explicitly `false` (no account keys, no SAS) | `Microsoft.Storage/storageAccounts` |
| `storage-anon-access-off` | `allowBlobPublicAccess` is explicitly `false` | `Microsoft.Storage/storageAccounts` |
| `storage-public-network-off` | `publicNetworkAccess` is `Disabled` | `Microsoft.Storage/storageAccounts` |
| `blob-no-retained-copies` | versioning, blob soft delete and container soft delete are each explicitly `false`, so a deletion note cannot outlive its 7-day window (#13) | `…/storageAccounts/blobServices` |
| `postgres-public-network-off` | `network.publicNetworkAccess` is the literal `Disabled` | `Microsoft.DBforPostgreSQL/flexibleServers` |
| `postgres-backup-matches-deletion-list` | `backupRetentionDays` is the literal `7` and `geoRedundantBackup` is `Disabled`, so no backup can outlive or outreach the deletion list (#13) | `Microsoft.DBforPostgreSQL/flexibleServers` |
| `no-broad-role` | no role assignment references Owner, Contributor, User Access Administrator or RBAC Administrator | `Microsoft.Authorization/roleAssignments` |
| `oidc-issuer` | a federated credential's `issuer` is the GitHub Actions OIDC issuer and nothing else | `…/federatedIdentityCredentials` |

The checks are chosen against the *real* templates: HTTPS-only and
digest-pinned images are the app's posture (`container-apps-app.bicep`,
`container-apps-staging.bicep`); admin/anonymous
off is the registry's (`security-foundation.bicep`); RBAC + soft delete is the
vault's; the narrow-role rule encodes H-5's "AcrPull / AcrPush / Key Vault
Secrets User and nothing wider" by rejecting the broad roles by their published
GUIDs; the issuer rule guards the publish identity's federated trust
(`publish-identity.bicep`).

What it deliberately does **not** touch — and what therefore stays the manual
reviewer's call — is the benign churn the recorded what-if already accounts for:
tags, `expires-on`, location, scale cooldown/polling, the temporary revision
suffix, and the platform's own default-value noise. Those are not invariants, so
they neither pass nor fail here.

## 3. Evidence

**Rule logic (offline, deterministic).** `infra/azure/policy/test_check.py`
runs the invariants over two crafted fixtures and each rule in isolation. From
the repository root:

```
$ python -m unittest infra.azure.policy.test_check -v
… Ran 12 tests … OK
```

- `fixtures/baseline.arm.json` — the reviewed baseline's security properties in
  compiled-ARM shape — yields **zero** findings.
- `fixtures/unsafe.arm.json` — a representative unsafe change (plaintext HTTP
  ingress, a `:latest` image, an inline database credential, a registry with
  admin and anonymous pull on, a vault off RBAC with soft delete disabled, a
  Contributor assignment, and a rogue federated issuer) — fails on **all nine**
  rules, and the CLI exits non-zero (issue #205 item 3).

**Real templates (in CI).** The `infra-policy` workflow compiles every
`infra/azure/*.bicep` with `az bicep build` (no login required to compile) and
runs the same rules over the output. The reviewed baseline must pass; a separate
step re-runs the checker on the committed unsafe fixture and fails the job if it
is *not* rejected, so the gate cannot silently stop biting.

## 4. Coverage limits

- It reads the templates, not the live resource group. It cannot see drift
  applied outside Bicep, nor a resource that exists only in Azure. That is the
  manual what-if's job and remains so.
- Values that compile to ARM expressions (a parameter or a function) are not
  resolved. The `no-plaintext-secret` and `image-digest-pinned` rules are
  written to tolerate this (a reference or a `format(... @sha256: ...)` passes),
  and the federated `subject` is a reviewed parameter the checker cannot judge
  statically — it guards only the `issuer`.
- It is an allow-known-bad / require-known-good invariant set, not a complete
  Azure best-practice baseline. It catches regressions in the postures listed in
  §2; it does not claim to be exhaustive.
- It performs no deployment and makes no Azure call of any kind.

## 5. The deployment process is unchanged

Nothing here deploys. The owner-reviewed path is still: compile → owner reviews a
live `az deployment group what-if` for the specific change → owner approves →
owner runs the deployment → read-back. This gate runs earlier and on every
change; it does not replace, authorise or shortcut that review. The recorded
examples remain [`final-verification-2026-11-18.md`](final-verification-2026-11-18.md)
and the Task 20 lock application in
[`shared-resource-locks.md`](shared-resource-locks.md).

## 6. Review before the #13 pilot

This automation decision — offline validation over a live what-if, and this
specific invariant set — must be **reviewed again before the employee pilot in
#13**, when real (non-fictional) data and wider exposure change the threat model
and may justify the credentialed what-if we declined here. **This issue does not
approve the #13 pilot** and does not satisfy any #13 gate.

Related records:
[[../../docs/superpowers/plans/2026-11-15-security-remediation]] (Task 20),
[[final-verification-2026-11-18]], [[shared-resource-locks]].
