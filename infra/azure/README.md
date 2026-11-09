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
   backups, monitoring, public IPv4, and outbound transfer in East US 2.
6. The Azure for Students terms. This preflight authorizes fictional staging
   only, not an employee competition.

The free-services list confirms allowance limits but is not a monthly price
estimate. Do not enter `0.00` below until the Pricing Calculator review covers
every planned component. Do not select **Remove spending limit**, upgrade to
pay-as-you-go, create a resource, or approve a paid estimate during this check.

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
  --monthly-estimate-usd '0.00'
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
- no price estimate;
- any estimated charge that was not separately approved.
