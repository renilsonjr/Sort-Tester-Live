# Azure staging preflight

This first step is read-only. It does not create, register, update, or delete
an Azure resource. It gathers enough evidence for the owner to decide whether
the Azure for Students subscription can safely continue to staging.

## What must be checked manually first

In the Azure portal, keep the subscription spending limit enabled and record:

1. The active subscription name and ID under **Subscriptions**.
2. The current Azure for Students balance and expiry date.
3. Whether the Education page shows the always-free App Service F1 allowance:
   up to 10 web or API apps, 1 GB storage, and 60 CPU minutes per app per day.
   F1 is for development and testing, has no SLA, and is not evidence that the
   API can support the employee pilot.
4. Whether it shows the 12-month PostgreSQL Flexible Server allowance for this
   subscription: Burstable B1ms, 750 hours, 32 GB storage, and 32 GB backup
   storage.
5. The Pricing Calculator estimate for App Service, PostgreSQL, storage,
   backups, monitoring, and outbound transfer in East US 2. Record both the
   gross monthly retail estimate before benefits and the expected monthly
   charge after the verified subscription allowances.
6. The Azure for Students terms. This preflight authorizes fictional staging
   only, not an employee competition.

The free-services list confirms allowance limits but is not a monthly price
estimate. The reviewed staging calculator export records a gross retail
exposure of `16.49` USD per month. The expected charge is `0.00` only while the
verified App Service, PostgreSQL, Azure Monitor, and bandwidth allowances are
active and actual usage stays within their limits. Do not select **Remove
spending limit**, upgrade to pay-as-you-go, create a resource, or approve a paid
estimate during this check.

## Run in Azure Cloud Shell

Confirm the active account without copying its identifiers into chat:

```bash
az account show --query '{name:name,id:id,state:state,isDefault:isDefault}' --output table
```

If it is not the intended subscription, select the correct one first:

```bash
az account set --subscription '<subscription-id-from-your-portal>'
```

From a clean checkout of the reviewed branch, run the collector. Replace the
two placeholders and the estimate with the values you personally verified:

```bash
python3 infra/azure/preflight.py \
  --expected-subscription-name 'Azure for Students' \
  --expected-subscription-id '<subscription-id-from-your-portal>' \
  --confirm-spending-limit-enabled \
  --confirm-student-terms-reviewed \
  --confirm-app-service-free \
  --confirm-postgres-free \
  --gross-monthly-retail-usd '16.49' \
  --expected-monthly-charge-usd '0.00'
```

Do not add `--approve-paid-usage` unless a later written estimate has been
reviewed and explicitly approved. The subscription ID is an Azure identifier,
not a password, but it is still redacted from the saved report.

The report is created under:

```text
$HOME/.local/state/sort-tester-live/
```

The directory is mode `0700`; the report is mode `0600`. The collector refuses
an existing file, a symlink, or an output outside that directory. Its Azure CLI
adapter accepts only these read operations:

- show the active account;
- list account locations;
- list Linux App Service runtimes and F1 locations;
- list PostgreSQL Flexible Server SKUs in East US 2 and East US;
- list existing resource metadata to detect planned-name collisions.

The saved report omits the raw subscription ID, tenant ID, signed-in user, and
unrelated resource details. A green result means only **ready for owner
review**. It does not authorize resource creation.

## Stop conditions

Stop and return the report without proceeding when any blocker appears,
including:

- wrong or disabled subscription;
- spending limit not confirmed;
- student terms not reviewed;
- free App Service or PostgreSQL allowance not confirmed;
- no complete East US 2/East US service combination;
- a planned-name collision;
- no or invalid gross retail estimate;
- no or invalid expected post-allowance charge;
- any expected charge that was not separately approved.

## Staging resource boundary

The infrastructure files define a fictional-data staging boundary only. They
do not authorize employee data, a public launch, paid usage, or removal of the
subscription spending limit.

`bootstrap-resource-group.bicep` creates only `rg-sort-tester-staging`.
`main.bicep` defines the Free F1 Linux App Service, PostgreSQL 18 Flexible
Server, Entra administrator, TLS settings, capped 30-day monitoring, and the
USD 5 monthly budget notifications. Every taggable resource carries the four
mandatory project tags. Child resources that Azure does not allow to carry
tags are protected by the exact deployment manifest instead.

### Mandatory first-bootstrap absence check

Bicep cannot safely distinguish an unrelated, already-existing empty resource
group from the intended new group. Before the first bootstrap, the owner must
run this read-only check:

```bash
az group exists --name rg-sort-tester-staging
```

The command must print `false`. If it prints `true`, stop. Do not run
`what-if`, deploy, adopt, retag, replace, or delete that group until its exact
ownership has been investigated and reviewed.

### Build and subscription-scope what-if

These commands compile and preview only; they do not create resources:

```bash
az bicep build --file infra/azure/bootstrap-resource-group.bicep
az bicep build --file infra/azure/main.bicep
az deployment sub what-if \
  --name sort-tester-staging-bootstrap-review \
  --location eastus2 \
  --template-file infra/azure/bootstrap-resource-group.bicep \
  --parameters location=eastus2
```

The owner must review the preview before any creation command is written or
run. The preview must create only `rg-sort-tester-staging` in East US 2 with
the four expected tags.

### Local parameters and resource-group what-if

Do not edit the tracked placeholder file with real owner identifiers. Copy it
to the ignored local filename and replace every placeholder locally:

```bash
cp infra/azure/main.staging.bicepparam infra/azure/main.staging.local.bicepparam
```

Only after the owner has separately approved and created the resource group,
preview the main deployment without creating resources:

```bash
az deployment group what-if \
  --name sort-tester-staging-main-review \
  --resource-group rg-sort-tester-staging \
  --template-file infra/azure/main.bicep \
  --parameters infra/azure/main.staging.local.bicepparam
```

Stop if the preview deletes or replaces anything, uses another region or SKU,
contains an unexpected resource, omits a required tag, enables PostgreSQL
password authentication, creates a broad firewall rule, or estimates a charge
outside the reviewed free allowances. Save redacted preview evidence under
`$HOME/.local/state/sort-tester-live/`, never inside the checkout.
