# Runtime identity and read access — Task 5 preparation

Status: **identity and scoped grants applied and read back on 2026-11-16; no app association**. Related: [[security-foundation]],
[[container-apps-app]], [[../../docs/superpowers/plans/2026-11-15-security-remediation]].

## Scope and actor

[[runtime-identity.bicep]] prepares `id-sort-app-stg`, a user-assigned managed
identity intended only for the staging app's platform image pull and Key Vault
reference. It creates the identity and exactly two role assignments:

| Role | Scope | Purpose |
| --- | --- | --- |
| AcrPull | Existing `<acr-name>` registry only | Download images; no push or registry administration |
| Key Vault Secrets User | Existing `<key-vault>` vault only | Read secret values/metadata; no secret writes or access administration |

**2026-11-21:** the Key Vault Secrets User row is no longer granted. The app signs in to PostgreSQL as this identity and reads no vault secret, so the role was removed from the live identity (issue #13) and `grantVaultRead` now defaults to `false`. Pass `grantVaultRead=true` only for an app that really reads a secret.

The vault is dedicated to this app. The grant covers all current/future secrets
in that vault; do not use it as a shared vault for unrelated secrets. This is
vault scope, not single-secret scope. The runtime identity receives no Owner,
Contributor, subscription/resource-group role, publisher role or PostgreSQL role.

The template changes no existing registry/vault/app resource, creates no secret,
and attaches the identity to no workload. It has no credential parameters and
no federated credentials. App association, image publishing, secure database URL
transfer, Key Vault reference and old-PAT retirement are later reviewed work.
This does not implement passwordless PostgreSQL (#84).

## Why a separate identity

The earlier plan illustrated a system-assigned identity. A user-assigned one
lets permissions be provisioned and checked before app configuration changes.
[Azure recommends this option for image pulls](https://learn.microsoft.com/en-us/azure/container-apps/managed-identity-image-pull).
It has an independent lifecycle, so it must be explicitly managed and retired.
[Managed identities have no extra identity-service charge](https://learn.microsoft.com/en-us/entra/identity/managed-identities-azure-resources/overview);
existing service use still follows the owner's student-credit-only boundary.

Only operators allowed to assign this identity to a workload should do so.
The name describes intent; it is not a technical restriction to one app. Do not
attach it to other apps/jobs. Later association should configure Container Apps
`identitySettings` lifecycle `None` for this platform-only identity, keeping its
token endpoint unavailable to container code while image pull/secret references
use it. That configuration is not applied in this slice.

## Read-only preflight before approval — 2026-11-16

Verified against the existing staging resources:

- Registry Standard, `LegacyRegistryPermissions`; ARM-audience authentication
  enabled, which is required by Container Apps managed-identity pulls.
- No user-assigned identities in the staging group. Microsoft.ManagedIdentity
  provider is **NotRegistered**. Do not silently adopt an existing same-name
  identity if this changes before execution.
- Bicep 0.49.2 compiles to one identity and two role assignments. The built-in
  IDs are AcrPull `7f951dda-4ed3-4680-a7ca-43fe172d538d` and Key Vault Secrets User
  `4633458b-17de-408a-b874-0445c86b69e6`. Both bind to this template's identity
  principal, use ServicePrincipal type, and have deterministic assignment IDs.
- Compiled-graph checks accepted the intended policy and rejected four mutated
  plans: subscription scope, Owner role, foreign principal, and an extra resource.
- Azure what-if exited 0 and showed exactly three Creates, with no existing
  resource modifications/deletions. Its role principal remains a reference to
  the new identity; the actual object ID is only resolved during creation.

What-if is not effective-access verification and did not register the provider.
Before execution, recheck the source/hash, resource scopes, role definitions,
current identity inventory, student subscription and spending protection.

## Owner-approved execution only

Approval must name the new identity, both roles and their exact scopes. The
previous approval for two empty services did not authorize these grants.
Provider registration and deployment required separate approval; that approval
and the completed execution are recorded below.
After approval and PR merge:

```sh
az provider register --namespace Microsoft.ManagedIdentity
az provider show --namespace Microsoft.ManagedIdentity --query registrationState
```

Wait for Registered before proceeding. Recompile the merged source and rerun
what-if against the existing group with the same reviewed parameters. Require
one identity Create and the two scoped assignment Creates; stop on an unexpected
identity, principal, scope, role, modification, replacement or deletion.

```sh
az deployment group what-if -g rg-sort-tester-staging \
  --template-file infra/azure/runtime-identity.bicep \
  --parameters expiresOn=<review-date> --no-pretty-print
```

Use the same approved template/parameters with Incremental create only after
that review. Resolve the created identity's principal ID and verify both direct
assignments use that ID and the exact resource scopes. Confirm existing app
configuration, spending protection and health remain unchanged. Do not mark a
functional image pull or Key Vault read as verified until the later workload
association and prepared image/secret actually exercise it.

A recreate of the identity can produce a new principal with the same ARM ID.
Assignment names use the stable resource ID, so don't delete/recreate or reuse
it without reviewing/revoking the exact old bindings first. If a partial create
fails, inspect the actual identity and assignment state before retrying.

Rollback targets only the exact role-assignment IDs reported by this template;
check for current consumers before retiring the identity. Role propagation and
token caches can delay effective revocation. Do not delete the registry or
vault to roll back these grants. App connection and publish rollback belong to
the later integration slice.


## Approved execution and read-back — 2026-11-16

The owner explicitly authorized provider registration, this identity and both
named grants after PR #159 merge and a fresh matching preview. PR #159 merged
as `5bb7194b7049354f751374ed5ee3ced74ba43be8`. The merged Bicep compiled to the
same reviewed JSON (SHA-256
`4180c803ad255e4e23e7b8363800205a096bb2e4143da702bc9796b49051ed57`).

Prechecks confirmed the selected student subscription, spending limit On and
no existing user-assigned identity in the staging group. After provider state
became Registered, fresh what-if again showed exactly three Creates with no
existing-resource modifications/deletions. Incremental deployment
`sort-runtime-identity-5bb7194`, with `expiresOn=2027-10-09` (review reminder,
not automatic expiry), exited 0 and reported Succeeded.

Independent post-deployment reads verified:

- `id-sort-app-stg` principal `<principal-id>`.
- The subscription assignment inventory contained exactly two assignments for
  this principal, both ServicePrincipal type and with the expected role IDs and
  exact dedicated resource scopes from the table above.
- Both assignment IDs matched the deterministic values the template
  computes; the values themselves are in the private inventory.
- The full Container App resource equaled its pre-deployment snapshot; it still
  has no managed identity attached. Health returned HTTP 200 and the student
  subscription spending limit remained On.

No secrets were transferred. These reads verify identity/bindings, not a
functional image pull or secret read. Publisher access, image availability,
secret transfer, app association and credential retirement remain pending.
