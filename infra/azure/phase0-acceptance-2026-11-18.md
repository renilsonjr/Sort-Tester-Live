# Phase 0 acceptance record — audit final gate (#196)

Consolidated sign-off sheet for
[issue #196](https://github.com/renilsonjr/Sort-Tester-Live/issues/196),
the exit gate of the
[security remediation plan](../../docs/superpowers/plans/2026-11-15-security-remediation.md).

This document gathers the evidence already recorded across the plan, the
issue and the per-task Azure records into one place, so the only step left
is the owner's own decision on the two items that are genuinely the owner's
to decide. It **claims nothing new**: every line below points at evidence
collected earlier, and it preserves the limits each piece of evidence was
recorded with.

- **Fictional data only.** Staging holds no real employee data (owner
  attestation, 2026-11-18). Nothing here authorises the employee pilot
  (#13), employee data, or any Azure change.
- **Evidence provenance.** The Azure observations were produced by the
  owner running read-only commands in Cloud Shell and supplying the
  outputs; the assistant reviewed the outputs, not a live Azure
  connection. The code/CI evidence is from GitHub Actions runs on
  `codex/ranked-mode`, linked below.
- **Source boundary.** The fixes and their evidence predate the
  glassmorphism UI work. The remediation code and the final-pass evidence
  were scoped to the merged documentation/CI source
  `7609311f7e76d53e5cd2cecf8de974b14163782a` (PR #204) and earlier; the
  serving image digest is
  `sha256:37c37ba6…`, built from source `44e98a97`. PRs #209–#211
  (ranked/login glass) landed on `codex/ranked-mode` **after** the
  evidence and touch only `index.html` and frontend tests — they do not
  change any backend, infra or workflow path verified here.

---

## Definition-of-Done ledger

The checkbox state mirrors what is now in the plan's Definition of Done.
Each line states the evidence and its scope limit.

### ✅ Met, with evidence

- **Backend suites green (macOS and Windows CI).** macOS:
  `python -m backend.ci_tests` against the dedicated scratch database —
  **1042 tests, 0 failures/errors/skips** (refreshed 2026-11-18). Windows
  CI: PR [#202](https://github.com/renilsonjr/Sort-Tester-Live/pull/202) /
  [#204](https://github.com/renilsonjr/Sort-Tester-Live/pull/204) ran
  **1042 tests, 0 failures/errors/skips** against a real job-owned
  PostgreSQL cluster, then passed HTTP health. The earlier Windows "green"
  that had 670 skips is corrected and guarded (Task 22 — the runner now
  fails on any skip).
- **Node suites green.** Frontend **551/551 pass, 0 fail/skip** locally on
  this branch; CI frontend job reported **543 pass, 0 fail/skip** on the
  evidence source.
- **App image workflow green, blocking Trivy included.** The App image and
  App image publish workflows are green on `codex/ranked-mode` through
  `28ec74c`, including the blocking HIGH/CRITICAL Trivy scan. Scope: this
  gates the built image; it is distinct from the live-deployment decision,
  which remains the owner's.
- **Staging smoke — H-1 renewal, attempt flow, owner approval, recovery
  open.** Owner-supplied outputs, 2026-11-18: active session renewed over
  **21 minutes (22/22 HTTP 200)** past the 15-minute idle window, logout
  204 then 401; a full quiz (15 reads + 15 answers + 14 advances, all 200)
  with owner approval of the exact fictional account and a recovery opened
  with **no credential handover**. Scope: least-privilege DSN
  (`current_user=sort_app`) confirmed in the same session; this tests the
  HTTP/DB flow, not answer accuracy, browser UX or concurrent settlement.
- **H-2 credential isolation + M-1 public notice off the sweep chain.**
  H-2: ten bad attempts → 401, the eleventh → 429, **a different valid
  credential from the same client still logged in (200)**. M-1: a fictional
  quiz completed while four external workers issued bounded
  `/season/notice` GETs — **100/100 notice requests 200, all overlapping
  the quiz**, quiz p95 366 ms. Scope: bounded overlapping load, **not** a
  30-player flood, a no-load latency baseline, or the 15-minute pilot
  target — those stay in #13.
- **Network isolation + registry credential.** `psql` from the public
  internet times out (H-4: private endpoint, public firewall rule removed,
  verified read-back shows publicNetworkAccess Enabled with **0 firewall
  rules**); GHCR PAT revoked, registry pulled via managed identity (H-5).
- **No secrets in tracked files; gitleaks green.** Whole-history
  [Security gates run](https://github.com/renilsonjr/Sort-Tester-Live/actions/runs/44355451109)
  on `7609311f…`: Gitleaks scanned **367 commits, no leaks**; Bicep compile
  and both pip-audits passed. `test_docs_hygiene` guards resource-name
  shape and the vault-write DSN role on every run. Scope: states tool/run
  coverage, not a proof that no secret exists on any path ever.

### ⚠️ Owner decision required — the two genuinely open items

1. **`what-if` is 2 Modify / 13 Ignore, not NoChange.** The reviewed
   Incremental preview for `container-apps-app.bicep` (source
   `53fd8740…`, reconstructed private parameter file, `databaseUrl`
   explicitly empty) parsed as **Succeeded, 2 Modify, 13 Ignore, 0
   Create/Delete/Replace**. All thirteen Ignore entries have identical
   before/after payloads. The two Modify entries reduce to **seven
   property-level omissions** from the template — not resource deletions —
   each interpreted in
   [`final-verification-2026-11-18.md`](final-verification-2026-11-18.md)
   and in the what-if table of that record:

   | Property | Before | Reading |
   |---|---|---|
   | App ingress `exposedPort` | 0 | App keeps Auto transport, targetPort 8000; no TCP exposure requested. |
   | App ingress `traffic` | latestRevision=true, weight=100 | Single mode; ready-revision routing is platform-managed. **Needs explicit interpretation.** |
   | App template `revisionSuffix` | temporary return suffix | Manual experiment metadata absent from the normal template. **Not guaranteed a no-op on redeploy.** |
   | App scale `cooldownPeriod` | 300 | Matches documented default; replicas stay 1/1. |
   | App scale `pollingInterval` | 30 | Matches documented default; replicas stay 1/1. |
   | Env `peerAuthentication` | mtls.enabled=false | Already-disabled setting omitted; nothing enabled is removed. |
   | Env `peerTrafficConfiguration` | encryption.enabled=false | Already-disabled; nothing enabled is removed. |

   Azure documents default-value omission as a known source of
   false-positive property deletions, but that general limitation does not
   by itself prove each delta is a no-op; **`traffic` and `revisionSuffix`
   in particular need the owner's explicit acceptance** before any
   redeployment. No deployment followed the preview. The owner's decision
   here is whether this reviewed preview is accepted as the final-pass
   `what-if` for Phase 0, or whether a redeploy to converge the suffix is
   wanted first.

2. **Owner answers to the seven questions + the Phase 0 signature.** Six
   of the seven are answered below; question 5's game-design items and
   question 3's retained-backup check have gaps, stated as such. Signing
   Phase 0 is the owner's act, and it is the last thing this gate needs.

---

## The seven owner questions — consolidated answers

1. **Flexible Server TLS / firewall / auth state.** Answered, read-only
   outputs 2026-11-18: PostgreSQL 18, Ready; `require_secure_transport=on`
   (TLS required); **publicNetworkAccess Enabled with 0 firewall rules**
   (corrected `--server-name` query, `length(@)=0`); both password and
   Entra auth **Enabled**. Scope: configuration only, not a live
   connectivity probe.
2. **Admin password date / holder / rotation.** Partially answered, and the
   gap is accepted: only the owner holds it, in a private location
   accessible only to the owner; **last-change date is unknown** and the
   owner **declined immediate rotation** on 2026-11-18, instructing that
   remaining work proceed. 90-day-policy compliance is therefore **not
   established** and is carried as a known, owner-accepted gap into #13. No
   password value was requested or disclosed.
3. **Backup/retention; do backups still hold the dropped `emails` data
   (migration 0021)?** Partially answered: retention **7 days**, earliest
   restore **2026-11-11T23:40:03Z**, geo-redundancy Disabled. **Whether a
   backup inside that window still holds the dropped email content is NOT
   verified** — it requires a restore, which belongs to #13. Gap carried
   forward.
4. **Does the database hold fictional data only?** Answered: owner
   attestation, 2026-11-18, fictional data only. Not an independent
   data-content audit.
5. **Game-design decisions.** *Negative balances:* answered — intended
   (wrong answers deduct), so Task 13 clamps at **±30000** rather than
   `>=0`, with a schema CHECK. *Concurrent-session cap of 5 (Task 17)* and
   *list caps (Task 18):* implemented in code and tested, but **not
   recorded as an explicit owner game-design confirmation**. Gap:
   owner to confirm the cap of 5 and the list caps (500 history/tickets/
   standings, 100 review queues) are the intended behaviour, or request a
   change before the pilot.
6. **Log ingestion posture.** Answered 2026-11-18: **zero ingestion
   accepted** for fictional-data staging (Decision in Task 21 / PR #198),
   with the loss of centrally retained logs and auth-flood alerting
   accepted as a documented risk. Reassess before #13.
7. **VNet subnet CIDR + downtime; do spike/staging retire?** Answered
   2026-11-16 under Task 6: owner-selected subnet ranges, spike/staging
   retirement and downtime decision recorded, with applied network
   evidence. Do not re-ask.

---

## Accepted risks carried into the pilot gate (#13)

These are owner-accepted for fictional-data staging and **must be
revisited before real people use the app**:

- Admin-password last-change date unknown; rotation declined; 90-day
  compliance unestablished (question 2).
- No verification that retained backups are free of the dropped email
  content, and **no backup has ever been restored** (question 3, #13).
- Zero log ingestion / no auth-flood alerting (question 6, Task 21).
- The database password still exists in Key Vault + the owner's store;
  managed-identity removal is tracked in **#84**.
- Additional policy / what-if CI automation is deferred to **#205**.
- Mandatory performance validation — 30 players × 15 minutes, p95 ≤ 1s —
  is **not** done; the bounded smoke here does not substitute for it (#13).

---

## What remains for closure

| Item | Owner | Status |
|---|---|---|
| Accept the reviewed 2-Modify / 13-Ignore preview as the final `what-if`, or request a converging redeploy | **Owner** | Open |
| Confirm the Task 17 session cap (5) and Task 18 list caps as intended, or request a change | **Owner** | Open |
| Sign the Phase 0 gate, preserving the accepted risks above | **Owner** | Open |

Once those three are recorded, #196 can close. #84, #205 and #13 then
carry the remaining, separately-gated work. Parent roadmap: #1.
