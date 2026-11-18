# Staging verification evidence — 2026-11-18

Partial final-pass evidence for
[issue #196](https://github.com/renilsonjr/Sort-Tester-Live/issues/196).
The owner ran the commands in Cloud Shell and supplied their outputs;
the assistant reviewed those outputs, not a direct Azure connection.
Fictional data only. This record does not close the audit or approve #13.

## Runtime and source boundaries

The configuration read-back reported Succeeded / Running, Single revision
mode, min/max replicas 1, latest-revision traffic 100%, 0.25 CPU / 0.5 GiB
and 1 GiB ephemeral storage. The serving revision had the temporary return
suffix `cpu-quarter-return`.

Image digest:
`sha256:37c37ba6471509efb92e07fc8375558fae8c75f421076cfe32d50526a7ca0aaa`.
The prior deployment record associates that image with source `44e98a97`.
The final template preview used merged documentation/CI source
`53fd8740c699bc662122fcbef45242d395b0e810`; that checkout is not evidence
that a new image was deployed. No deployment followed these checks.

## Completed HTTP and runtime observations

- [x] H-2 credential isolation: fictional registration 200; ten attempts
  with one random invalid credential returned 401, the eleventh 429;
  another valid credential from the same client still logged in with 200.
  Authenticated profile 200; logout 204; subsequent profile 401.
- [x] H-1 auth-route active-session renewal: settings read inside the serving
  container gave idle_seconds=900 and ttl_seconds=28800. One login, followed
  by 22 profile queries at minutes 0–21, returned 22/22 HTTP 200 for the
  same cookie and account. Elapsed 1260.2 seconds; first/last observations
  16:08:31.940364–16:29:31.971614 UTC. No re-login or cookie change.
  Logout 204 and subsequent profile 401. Inactivity expiry, ranked-route
  renewal and persisted timestamps were not independently inspected.
- [x] Ranked/owner/recovery smoke in open Pre-Season: normal attempt start
  201; 15 question reads, 15 answers and 14 advances all 200. Both result
  reads returned 200, with completed outcome and equal response bodies.
  Owner role was confirmed through normal login; reauthentication 204,
  approval of the exact fictional account 201, recovery open 201 with no
  login ID returned. The original player session still worked afterward.
  Both logouts returned 204. No handover, official launch or role changes.
- [x] Runtime-role read-back using the app's configured DSN: current_user
  `sort_app`; superuser, create database, create role, bypass RLS, CREATE
  on schema public and CREATE on the database all false. Read-only query,
  no password printed. This is not an exhaustive grant/ownership audit.
- [x] M-1 bounded mixed-traffic smoke: a new fictional player completed
  a normal quiz while four external workers issued 25 notice GETs each.
  All 100 notice requests returned 200 and their intervals overlapped the
  quiz interval. Quiz: 46 API calls, p95 366.2 ms, elapsed 15.87 seconds,
  completed outcome, expected sequences and correct/wrong answer outcomes
  rather than timeouts; logout 204. Notice traffic did not necessarily span
  every question. No no-load comparison or sustained capacity claim.

Test accounts and records remain in staging, including one completed quiz,
approval and open recovery for the combined owner flow, and a separate quiz
for the mixed-traffic check. No secret was printed or saved by those scripts.
They selected the first offered answer; answer accuracy, browser UX,
concurrent settlement and a ledger audit are outside these observations.

## App-template what-if: seven omissions, not NoChange

Cloud Shell cloned a fresh clean checkout at `53fd874` after the old checkout
was absent. Bicep build succeeded, with a CLI configuration warning. A new
private temporary parameter file reused the last app deployment's nonempty
parameters, checking trustedProxies=1, exact current-image match, Key Vault
reference and private subnet. The direct databaseUrl parameter was empty;
no database password was copied.

Full Incremental preview: **Succeeded, 2 Modify, 13 Ignore**; no resource
Create/Delete/Replace; error, diagnostics and potentialChanges all null.
The thirteen Ignore entries have equal before/after payloads. App image,
resources, replica limits, mode, identity, registry/secret references,
origin, proxy count, probe, tags, environment association and subnet match.

The exact property-level Delete deltas are:

| Property | Before | Interpretation and limit |
| --- | --- | --- |
| App ingress exposedPort | 0 | TCP ingress field; this app keeps Auto transport and targetPort 8000. No TCP exposure is requested. |
| App ingress traffic | latestRevision=true, weight=100 | The template keeps Single mode, whose ready-revision routing is platform-managed. The omission is not a request for a multi-revision split. |
| App template revisionSuffix | temporary return suffix | Manual experiment metadata absent from the normal template. This is a revision-scope difference, not guaranteed to be a no-op on redeployment. |
| App scale cooldownPeriod | 300 | Matches documented scaling behavior; min/max replicas remain 1. |
| App scale pollingInterval | 30 | Matches documented scaling behavior; min/max replicas remain 1. |
| Environment peerAuthentication | mtls.enabled=false | An already-disabled setting is omitted; no enabled protection appears in the before payload. Absence alone is not proof of the provider's post-deployment value. |
| Environment peerTrafficConfiguration | encryption.enabled=false | Existing false matches the documented disabled-by-default posture; no enabled protection is being removed from the before payload. |

A structural comparison confirmed that removing exactly these seven paths
from the before payloads produces the after payloads, with no other
differences. This explains the preview; it does not prove a redeployment
would perform no operation or preserve the current revision name.

No template was patched just to suppress differences. In particular, do not
freeze the temporary revision suffix into the permanent template merely to
obtain NoChange. No blanket exclusion of Modify/Delete was used. No app
redeployment is required to collect this evidence, and none was performed
or approved by the preview itself. Final deployment acceptance remains open.

Official references supporting the interpretation:

- [What-if limitations and default-value noise](https://learn.microsoft.com/en-us/azure/azure-resource-manager/bicep/deploy-what-if).
- [Single mode, automatic names and revision-scope changes](https://learn.microsoft.com/en-us/azure/container-apps/revisions).
- [Ingress schema for the exact API version](https://learn.microsoft.com/en-us/azure/templates/microsoft.app/2025-01-01/containerapps#ingress).
- [Scaling behavior](https://learn.microsoft.com/en-us/azure/container-apps/scale-app#scale-behavior).
- [Peer-to-peer encryption defaults](https://learn.microsoft.com/en-us/azure/container-apps/ingress-environment-configuration#peer-to-peer-encryption-in-the-azure-container-apps-environment).

## Remaining gates

- [ ] Reconcile the complete final Definition of Done, including source/run
  scopes, the reviewed non-NoChange preview and the remaining owner questions
  and Phase 0 sign-off. The parent final-pass checkbox stays open in #196.
- [ ] Mandatory pilot performance validation in #13: proposed 30 players /
  15 minutes / p95 control/quiz <=1 s still needs its own target review and
  mixed-traffic measurement. This short smoke does not satisfy it.
- [ ] Recovery/restore, outage handling and the other unchecked #13 gates.
  Opening a recovery request is not a backup restore or credential handover.

Related records: [[pool-verification-2026-11-18]], [[shared-resource-locks]],
[[container-apps-app]], and
[[../../docs/superpowers/plans/2026-11-15-security-remediation]].
