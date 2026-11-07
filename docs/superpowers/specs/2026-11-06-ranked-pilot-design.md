# Peak Season — Ranked pilot overview

**Status:** Planning only, updated November 7, 2026. Current health/browser API foundations are complete; competition features are not implemented.

## Read in this order

1. [[2026-11-07-ranked-decision-record]] — controlling owner-approved competition policies and Q1–Q14 status.
2. [[2026-11-07-ranked-security-operations-design]] — assistant-proposed technical defaults, tradeoffs and implementation/resource verification gates.
3. [[2026-11-07-ranked-question-bank-review]] — candidate inventory and owner content-review checklist.
4. [[2026-11-06-ranked-roadmap]] — issue dependencies and incremental build sequence.

## Product shape

Keep existing guest Practice/study, 15-second Practice timing, feedback, local results and Excel export. Home retains sort-change announcements plus Log in / Continue as guest. Logged-in users get separate Practice and Ranked flows, profile, login-only eligible-player leaderboard and private Support → Tickets.

Ranked: solo 15 questions, five per difficulty, ten seconds each. Easy +10/-15, Medium +20/-10, Hard +30/-5. One balance, negative totals allowed; caps 1,000/2,000/3,000/4,000 for Iron/Bronze/Silver/Gold. Challenger starts 4,001 and is uncapped. Apply Quit -10 before one final cap; discard overflow. Explicit perfect promotion sets cap+1; correct promotion answers +0, mistakes/timeouts deduct. Demotion requires earning back eligibility and passing promotion again.

One active original-page attempt includes 15-second loss grace; refresh/other tabs cannot resume. Current clock continues, future never-sent questions do not accumulate deductions; a sent question can time out even if delivery fails, with its clock starting at first server send. Normal/promotion feedback waits for Next; tie-breaks auto-advance with hidden feedback. Confirmed common outage uses void/restart rules, never automatic cheating punishment. Technical detection and enforcement details are proposed separately.

Owner manually launches from Pre-Season; no start date chosen. Void unfinished Pre-Season without adjustment, reset 0/Iron/none and retain owner-private “pre season history”. Official season closes December 31, 2026 at 11:59 p.m. America/New_York, with five-minute finishing window then frozen points. Three UPS hats, one each, only for owner-approved Primary Sort / Twilight / Saddle Brook sorters with a completed valid official quiz. Only top-three prizes need unique placements.

Prize-impacting ties use shared fresh five-question Hard work-methods rounds. Challenger: at most three valid rounds, five seconds/question. Lower ranks: at most five, at 5/5/5/4/3 seconds. First deadline is season close +24 hours; later/replacement rounds receive new 24-hour windows. At valid deadline Challenger incomplete/no-shows are excluded from prizes, while lower-rank unresolved incomplete groups use owner selection below completed players. At round limits or fresh-content exhaustion, remaining unresolved prizes wait for owner selection. No first-reached timestamp fallback. Preserve valid relative order and compact/backfill places; fewer eligible winners means fewer hats awarded. Full outage/round/eligibility details remain in the controlling decision record.

Accounts use private optional email and stable username/tag identity; recovery is to the same existing account. Without verified email, owner approves only after in-person verification against a trusted prior account link. Own-account deletion wipes profile/history/scores; fresh account 0/Iron. Before final prizes it withdraws that candidate; only the minimal private season-ineligibility record with the approved owner-recognizable roster reference remains until global prize finalization, then purges. No hidden deleted-player profile or routine admin history access. Technical cleanup and backup requirements are proposals with explicit verification gates.

Player-requested private tickets and non-punitive connection flags follow scoped authorization and 15-day closed-case cleanup; shared evidence remains while linked cases are open. Verified one-time launch emails require separate opt-in and bounded retries/cancellation; provider provisioning and deletion contracts remain unverified.

## Delivery boundaries

Use shared `codex/ranked-mode`; main continues publishing the current static app. No new visual design is approved here. Mockups belong to #15/#16/#17 and must be reviewed before screen implementation. Existing 23 Node and 10 backend foundation tests do not certify any unbuilt competition feature.

Proposed stack remains FastAPI/PostgreSQL on the Windows candidate server with same-origin public pilot hosting. Actual content approval, authentication/deletion/provider proof, external monitoring, secure ingress, deletion-safe backups/restore and measured 30-player capacity remain required before employee rollout. This planning PR does not authorize service purchases, public deployment or merging itself.
