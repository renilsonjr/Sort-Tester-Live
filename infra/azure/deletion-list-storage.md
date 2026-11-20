# Deletion-list storage — issue #13, Fatia B

Status: **deployed to fictional-data staging on 2026-11-20** (what-if: 9 to
create, nothing modified or deleted; read-back matched the template). A real
deletion through the app wrote one note (`PutBlob` success in the account's
metrics). Not yet observed: a note expiring, and the list being read back.
Related: [[restore-runbook]], [[runtime-identity]], [[policy-validation]],
[[../../docs/superpowers/specs/2026-11-20-deletion-list-design]].

## What it is for

A database restore brings back accounts that players deleted after the
restore point. The app notes every accepted deletion outside the database so
the restore runbook can re-apply it. `deletion-list-storage.bicep` is the
place those notes live: one small blob per deletion, named by the account id,
containing the deletion time.

## What the template creates

| Resource | Name | Why |
|---|---|---|
| Storage account | `stsortdel<unique>` | Holds the notes. No keys, no SAS, no anonymous access, no public network access, TLS 1.2. |
| Blob container | `deletions` | The only container. |
| Lifecycle rule | `expire-deletion-notes` | Azure deletes each note once it is older than 7 days. |
| Role assignment | on the container only | Lets `id-sort-app-stg` read, write and delete blobs in `deletions`, nothing else. |
| Private endpoint | `pe-sort-deletion-list` | Gives the account an address inside `vnet-sort-stg` (`snet-data`). |
| Private DNS zone + link | `privatelink.blob.core.windows.net` | Makes the account name resolve to that private address inside the network. |

It modifies nothing that already exists. The network, the identity and the
Container App are only referred to.

## Three settings that must stay as they are

- **Soft delete and versioning are off.** They keep a recoverable copy of a
  blob after it is deleted, which would stretch a note past the 7 days the
  owner approved. They look like safety features. Do not enable them.
- **Shared-key access is off.** A leaked account key would read and rewrite
  the whole list.
- **Public network access is off.**

CI enforces all three (`policy/check.py`: `storage-shared-key-off`,
`storage-anon-access-off`, `storage-public-network-off`,
`blob-no-retained-copies`).

## How long a note really lives

The rule deletes blobs **older than** 7 days, so a note always covers every
restore point still inside the backup window. Azure evaluates lifecycle rules
about once a day and can take up to another day to act, so the real lifetime
is roughly 7 to 9 days. A new rule can take up to 24 hours before its first
run.

## Cost

Approximate list prices; confirm against the Azure pricing page before
approving, and against the remaining student credit.

- Private endpoint: about US$7 a month. This is nearly all of the cost.
- Private DNS zone: about US$0.50 a month.
- Storage and operations: cents.

A cheaper alternative exists: a virtual-network service endpoint on `snet-app`
instead of a private endpoint (no monthly fee). It was not chosen here because
it means modifying the existing virtual network, and because the database
already uses the private-endpoint pattern. It is the owner's call.

## Consequences to know before deploying

- **The operator cannot read the list from Cloud Shell** while public network
  access is off, exactly as with the database. The list is read from inside
  the app's container instead (`az containerapp exec`, see
  [[restore-runbook]] step 4), which needs the container to be running. The
  fallback for a fully down app is in the runbook and has never been run.
- **The resource group's `CanNotDelete` locks do not cover this account**, and
  none is added here. Note that a lock would not stop the lifecycle rule
  (that is data-plane), but decide deliberately whether to lock it.
- **Not verified:** that the lifecycle rule runs with the storage firewall
  set to `Deny` and `bypass: None`. Microsoft documents lifecycle management
  as working behind the firewall; confirm on staging by watching one note
  expire.

## Steps (each needs owner approval; 1 to 3 done on staging 2026-11-20, first half of 4 done)

1. **Preview.** In Cloud Shell, with the repository checked out:

   ```sh
   az deployment group what-if -g rg-sort-tester-staging \
     --template-file infra/azure/deletion-list-storage.bicep \
     --parameters expiresOn=<YYYY-MM-DD>
   ```

   Expected: only *Create* lines, for the resources in the table above. Any
   *Modify* or *Delete* means stop.

2. **Deploy.** The same command with `create` instead of `what-if`. Keep the
   `deletionListUrl` output.

3. **Point the app at it.** Set `SORT_TESTER_DELETION_LIST_URL` on
   `ca-sort-app-stg` to that URL, using an image that contains
   `backend/auth/deletion_list.py`. Until this is done the app either runs an
   older image (list absent) or needs the value `disabled` to start.

4. **Prove it.** Delete a fictional account through the app and confirm one
   blob named by its account id appears. Then repeat the restore rehearsal,
   re-applying from the real list instead of a hand-typed id. Only this makes
   the feature verified; the unit tests use a fake transport.

5. **Watch one note expire** after 7 to 9 days.

## Removing it

`az storage account delete` on the account, plus the private endpoint and the
DNS zone. Removing the account removes every note, so do it only when no
restore inside the last 7 days could still be needed.
