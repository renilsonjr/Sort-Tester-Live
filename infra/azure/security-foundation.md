# Registry and secret-store foundation — Task 5

Status: **created and verified in fictional-data staging on 2026-11-16**; identity, secret transfer and app wiring remain pending. Related: [[db-runtime-role]],
[[container-apps-app]], [[../../docs/superpowers/plans/2026-11-15-security-remediation]].

## Foundation scope

[[security-foundation.bicep]] adds only two empty resources to the existing
fictional-data staging resource group in North Central US:

- ACR Standard: authenticated private image storage, administrator login disabled,
  anonymous pulls disabled. The verified student allowance covers the registry unit within its quota and term.
- Key Vault Standard: RBAC authorization, no access policies or role assignments,
  soft deletion with seven-day recovery; purge protection is not enabled in this
  staging foundation. No secrets, keys or certificates are created.

Both names use the existing resource-group ID's deterministic suffix. Both carry
`fictional-only` and review-date tags. The review date does not delete resources
or stop charges. Public network endpoints require authentication; private
networking is Task 6, not part of this foundation.

The template does not touch the app, environment, database, registry token,
login credentials, published image, identities or permissions. It has no secret
parameters or outputs. Running what-if does not approve deployment.

## Student credit and free allowance — checked 2026-11-16

The owner authorizes creation only while usage is covered by the Azure for
Students credit/free allowance, with spending protection kept on. Do not remove
the spending limit, upgrade to pay-as-you-go, or switch billing subscriptions.
Exact credit balance and account details are kept in private operator notes.

The actual staging subscription reports `AzureForStudents` quota, Enabled state,
and `subscriptionPolicies.spendingLimit = On`. Education Hub shows available
student credit valid until November 9, 2027. Its free-service meter shows
`Container Registry, Standard Registry Unit`, unused (`0 / 31 (1/Day)`) for
November 2026, with the free benefit expiring November 9, 2027. This is why the
proposal uses Standard instead of Basic. One Standard registry fits the verified
monthly allowance; recheck quota and credit at deployment and billing updates.

The public [Azure for Students offer](https://azure.microsoft.com/en-us/free/students)
lists one Standard registry with 100 GB storage for 12 months for new customers.
The actual subscription's allowance, usage and expiry take precedence over an
advertised benefit. Use Education Hub for the verified student credit display.

Retail fallback rates were queried from the public
[Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
for North Central US consumption in USD:

| Meter | Retail USD rate outside a free allowance | Example |
| --- | --- | --- |
| Standard Registry Unit | 0.6666 per day | 19.998 for 30 days; 20.6646 for 31 days |
| Standard Key Vault Operations | 0.03 per 10,000 operations | 0.03 for 10,000 operations |

The registry-unit charge is expected to be covered while the verified allowance
is valid and unused by another registry. Do not promise zero total cost: Key
Vault operations, excess storage, builds, transfer or other usage may consume
credit. Existing app/database use shares that credit. Service usage may be
reported late. The spending limit remains essential; exhaustion/expiry can stop
services rather than permitting a paid upgrade under this authorization.

See [registry pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/)
and [Key Vault pricing](https://azure.microsoft.com/en-us/pricing/details/key-vault/).

## Review before creation

Compile and inspect the template, then run against the existing staging group:

```sh
az deployment group what-if -g rg-sort-tester-staging \
  --template-file infra/azure/security-foundation.bicep \
  --parameters expiresOn=<review-date> --no-pretty-print
```

Require exactly two Creates, for the named registry and vault, and no
Modify/Delete/Replace of existing resources. Check name availability, provider
support, subscription credit/spending limit, and current cost before execution.
Obtain owner approval for the exact resource names, recurring cost and review
date. Only after that approval may the same reviewed template and parameters
be used with `az deployment group create` in Incremental mode.

## Follow-up after the foundation

Task 5 stays incomplete. The next reviewed slice must prepare narrow identity
grants for ACR pull and Key Vault secret read, a short-lived publisher login
(OIDC subject/audience and repository environment gate), image import/publish
by digest, secure secret transfer, app references and rollback. Check the CTU
subscription/tenant permissions for that path before committing to provisioning.
Never paste the database URL or registry token into command arguments or logs.

Keep the existing working image/connection until the replacement pull and secret
read work. Revoke the old GHCR PAT only after checking its other uses and the
rollback path; never revoke a shared token blindly. This foundation alone does
not resolve H-5, move the DB secret, implement #84 or authorize employee data.

## Validation

Bicep 0.49.2 compilation passed. Compiled JSON checks confirm exactly the two
intended resource types, Standard registry/vault tiers, authenticated registry, RBAC
vault, no role assignments, app resources or secrets. Existing frontend suite:
523 passed. The initial Basic proposal what-if succeeded in `rg-sort-tester-staging`, with `expiresOn=2027-10-09`
(the existing inventory's review tag). Automated inspection required exactly
two non-Ignore changes, both Creates, and found no modifications, deletes or
replacements:

- `<acr-name>`
- `<key-vault>`

Both name-availability checks returned true before creation. These names now
identify the two provisioned services; see the execution record below. The review tag is not a requested hosting term; the owner
may choose an earlier review date before creation. Subscription balance and
spending-limit checks must be refreshed before a paid deployment.

### Student allowance revision

The template now selects Standard to match the verified free-service meter.
Bicep 0.49.2 compilation and compiled JSON checks passed for Standard. A fresh
Azure what-if required exactly two Creates and no changes to existing resources;
the returned registry SKU was Standard and the vault SKU standard. The previous
Basic what-if is historical evidence. Names and app/secret/access boundaries
stay the same. This was the pre-execution validation; the owner's credit-only
condition and PR #157 merge were then confirmed before creation.

## Execution and service-API correction — 2026-11-16

PR #157 merged as `975aa703d1fde9b0c838a0752b3d43091bdcc7af`. Before execution,
Education Hub credit was refreshed, and subscription REST again confirmed
AzureForStudents, Enabled and spendingLimit On. The deployed compiled JSON hash
matched the merged template. A fresh what-if required exactly the two approved
Creates with no existing-resource changes.

The initial deployment `sort-security-foundation-975aa70` partially failed:
ACR creation succeeded, but Key Vault rejected explicit
`enablePurgeProtection: false`. Resource inventory confirmed the registry
existed and the vault did not. Bicep compilation and ARM what-if had accepted
that value, so they were insufficient to validate the service's create API.

The [Key Vault 2024-11-01 API contract](https://learn.microsoft.com/en-us/rest/api/keyvault/keyvault/vaults/create-or-update?view=rest-keyvault-keyvault-2024-11-01#vaultproperties)
says `enablePurgeProtection` does not accept false. The corrected Bicep omits
this optional property; it does not enable irreversible purge protection.
Generated a remaining-vault-only ARM template from that compiled source, with
registry resources/outputs removed. Its what-if guard required one Create for
the approved vault and no existing-resource changes. RBAC remained true, access
policies empty, and purge protection unset. ARM what-if omits empty arrays, so
the guard accepts an absent/empty accessPolicies value.

Deployment `sort-security-vault-975aa70-fix` then exited 0 with Succeeded.
Post-creation reads and assertions verified:

- Registry Succeeded, Standard, admin login and anonymous pulls disabled;
  repository listing returned an empty array.
- Vault Succeeded, standard, RBAC enabled, soft delete enabled for seven days,
  purge protection not enabled, no access policies and no direct role assignments.
- The full app configuration matched the private pre-execution snapshot;
  subscription spendingLimit remained On. Published app health returned 200/ok.

No secret was transferred, image published to ACR, identity created or runtime
connection changed. Key Vault data-plane contents were not enumerated; no data
read permission was added for this check. The foundation was created without
secret resources. Task 5 is still incomplete until the later access/publisher/
secret/pull/rollback steps are verified. Check actual billed usage after Azure
posts it; free-allowance verification is not a final invoice.

The separately approved [[runtime-identity]] bootstrap is now applied and its
identity/bindings were read back. The app still has no identity attached;
publishing, secret transfer and runtime migration remain pending.
