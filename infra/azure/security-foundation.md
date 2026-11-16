# Registry and secret-store foundation — Task 5 preparation

Status: **prepared for review; not deployed**. Related: [[db-runtime-role]],
[[container-apps-app]], [[../../docs/superpowers/plans/2026-11-15-security-remediation]].

## Proposed scope

[[security-foundation.bicep]] adds only two empty resources to the existing
fictional-data staging resource group in North Central US:

- ACR Basic: authenticated private image storage, administrator login disabled,
  anonymous pulls disabled. This adds a recurring registry charge.
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

## Estimated additional cost — checked 2026-11-16

Queried the public [Azure Retail Prices API](https://learn.microsoft.com/en-us/rest/api/cost-management/retail-prices/azure-retail-prices)
with `armRegionName eq 'northcentralus'`, `priceType eq 'Consumption'`, and
`serviceName eq 'Container Registry'` / `serviceName eq 'Key Vault'`:

| Meter | Retail USD rate | Example |
| --- | --- | --- |
| Basic Registry Unit | 0.1666 per day | 4.998 for 30 days; 5.1646 for 31 days |
| Standard Key Vault Operations | 0.03 per 10,000 operations | 0.03 for 10,000 operations |

Estimate excludes existing Container Apps/PostgreSQL costs, registry storage
beyond included quota, builds, transfer, optional services and taxes. Student
credits and the actual agreement can affect the bill; no spending-limit change
is proposed. See [registry pricing](https://azure.microsoft.com/en-us/pricing/details/container-registry/)
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
intended resource types, Basic/Standard tiers, authenticated registry, RBAC
vault, no role assignments, app resources or secrets. Existing frontend suite:
523 passed. Azure what-if succeeded in `rg-sort-tester-staging`, with `expiresOn=2027-10-09`
(the existing inventory's review tag). Automated inspection required exactly
two non-Ignore changes, both Creates, and found no modifications, deletes or
replacements:

- `acrsortstgzp6nl6c3wplfy`
- `kv-sortstg-zp6nl6c3wplfy`

Both name-availability checks returned true. These are prospective names, not
provisioned services. The review tag is not a requested hosting term; the owner
may choose an earlier review date before creation. Subscription balance and
spending-limit checks must be refreshed before a paid deployment.
