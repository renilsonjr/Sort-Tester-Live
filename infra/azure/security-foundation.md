# Registry and secret-store foundation — Task 5 preparation

Status: **prepared for review; not deployed**. Related: [[db-runtime-role]],
[[container-apps-app]], [[../../docs/superpowers/plans/2026-11-15-security-remediation]].

## Proposed scope

[[security-foundation.bicep]] adds only two empty resources to the existing
fictional-data staging resource group in North Central US:

- ACR Standard: authenticated private image storage, administrator login disabled,
  anonymous pulls disabled. The verified student allowance covers the registry unit within its quota and term.
- Key Vault Standard: RBAC authorization, no access policies or role assignments,
  soft deletion with seven-day recovery; purge protection is not enabled in this
  staging proposal. No secrets, keys or certificates are created.

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

- `acrsortstgzp6nl6c3wplfy`
- `kv-sortstg-zp6nl6c3wplfy`

Both name-availability checks returned true. These are prospective names, not
provisioned services. The review tag is not a requested hosting term; the owner
may choose an earlier review date before creation. Subscription balance and
spending-limit checks must be refreshed before a paid deployment.

### Student allowance revision

The template now selects Standard to match the verified free-service meter.
Bicep 0.49.2 compilation and compiled JSON checks passed for Standard. A fresh
Azure what-if required exactly two Creates and no changes to existing resources;
the returned registry SKU was Standard and the vault SKU standard. The previous
Basic what-if is historical evidence. Names and app/secret/access boundaries
stay the same. No resources were created. The owner's credit-only condition is
verified; PR review/merge remains pending before execution.
