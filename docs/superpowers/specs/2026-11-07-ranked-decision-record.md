# Sort Test — settled decisions and open questions

**Status:** Owner decisions recorded November 7, 2026, from the November 6–7 discussion. Requirements only: competition features are not implemented. Backend health and local browser/API foundations are complete (#2/#3 closed).

**Related:** [[2026-11-06-ranked-pilot-design]], [[2026-11-06-ranked-roadmap]]. Parent roadmap: [#1](https://github.com/renilsonjr/Sort-Tester-Live/issues/1).

This record controls where earlier planning text differs. Only settled rules are approved. Recommendations and open questions are not decisions. Keep #4 open until its required rule examples and affected ambiguities are resolved.

## Baseline retained

- Solo Ranked requires login: 15 randomized questions, five per difficulty, ten seconds each, locked answers and forward-only progression. Normal Ranked immediately reveals correctness and point changes after acceptance/timeout.
- Easy +10/-15; Medium +20/-10; Hard +30/-5. Timeout is wrong. Complete regular quiz raw range: -150 through +300.
- Server-owned assignment, deadlines, validation, atomic updates and exactly-once attempt settlement. Preserve raw performance versus applied adjustment in history; this is not a second points balance.
- Negative totals allowed, Iron badge floor. Repeat regular attempts after the previous one ends while season admission is open.
- Preserve guest Practice/study, 15-second Practice timing, feedback, local results and Excel export. Practice never changes Ranked points.
- Routine administrators cannot change points, scoring values or difficulty. Additional achievement criteria and multiplayer/MMR are outside scope.

## Decision 1 — one capped balance and Challenger

**REVISE — final clarification.** Owners: #4/#9/#10/#12/#16/#17.

| Badge | Points / cap | Perfect promotion result |
| --- | --- | --- |
| Iron | Negative totals through 1,000 | 1,001 / Bronze |
| Bronze | 1,001–2,000 | 2,001 / Silver |
| Silver | 2,001–3,000 | 3,001 / Gold |
| Gold | 3,001–4,000 | 4,001 / Challenger |
| Challenger | 4,001 upward, uncapped | No further promotion |

One balance controls rank and seasonal standings. Discard overflow, never bank it; positive points cannot bypass promotion. Example: Iron 950 + regular raw +300 → 1,000, discard 250; perfect promotion → 1,001. Quit penalty is applied before the rank cap (Q1 settled). Apply the cap once to the final attempt result, not after each answer (Q2 settled).

## Decision 2 — unexpected disconnection

**KEEP EXISTING, with Decision 5 grace.** Owners: #4/#8/#9.

Grace expiry ends permanently and applies partial score under regular/promotion rules, without extra Quit penalty. Partial -40 → -40 adjustment; +80 → +80 subject to caps. Terminal attempts never resume.

## Decision 3 — intentional Quit and warning

**KEEP EXISTING.** Owners: #4/#8/#9/#17.

Normal Ranked Quit applies partial score plus -10 and ends permanently. Apply the -10 penalty BEFORE the rank cap (Q1 settled by the owner). Away from caps: +80 → +70 adjustment; -40 → -50. Iron 990 with partial +100 calculates 990 +100 -10 =1,080, capped to 1,000: overflow can absorb the visible effect of the penalty. Q2 is settled: calculate the full regular attempt result and any Quit penalty, then cap once at settlement. For promotion, retain the agreed correct+0/mistake-deduction rules and perfect-success cap+1 exception.

Confirmation: “Quit this ranked quiz? Your current score will count, and you’ll lose an additional 10 points. You cannot resume this attempt.” Continue quiz / Quit quiz. The question timer continues while confirmation is open. The previously agreed warning needs wording review in #17: describe the 10-point calculation before capping without promising a visible 10-point total decrease when overflow absorbs it. Browser-close warnings are best-effort; browser closing/network loss cannot reliably establish intent.

## Decision 4 — promotions, demotions and re-promotion

**REVISE.** Owners: #4/#8/#9/#17.

- Require 15/15 for promotion. Correct promotion answers add zero; wrong/timeouts deduct the usual difficulty amount. Perfect success sets the next cap+1 total, replacing ordinary +300.
- Iron 1,000, 14/15 with one wrong Easy: raw +275 for history, adjustment -15 → 985/Iron; earn back 15 before another promotion.
- That mistake then Quit: 1,000 -15 -10 → 975. Disconnect instead: 985, no extra penalty. Neither terminal attempt resumes.
- Losses demote; Bronze 1,010 with -150 → 860/Iron. Regaining Bronze requires 1,000 then perfect promotion again. Promotion entry behavior remains Q7.

## Decision 5 — grace, timeout and outage

**REVISE / ADOPT NEW.** Owners: #4/#8/#9/#23/#25.

- Fifteen seconds of grace before declaring disconnection. Reconnect before expiry to continue the original session. At expiry end permanently and settle partial score.
- Current question clock keeps running; timeout deducts normally. Send no next question until reconnection. No deductions for future questions never received.
- Confirmed server-wide outage voids affected normal Ranked/promotion attempts: zero adjustment, no Quit penalty or suspicious flag, no resume. Fresh attempts after recovery remain subject to season admission.
- Server-observed loss/outage confirmation is Q8. A failed request alone does not prove a server-wide outage.

## Decision 6 — active attempt and original session

**ADOPT NEW.** Owners: #4/#7/#8.

One active Ranked attempt per account, including grace. Another tab/device cannot start a replacement, cancel the original, or continue it. Reconnect only through the original quiz session, not another device. Practice remains available. Define same-session refresh/token behavior in Q8 without promising reliable physical-device identification.

## Decision 7 — connection review flags

**ADOPT NEW.** Owners: #25/#11.

Count distinct losses after recovery; duplicates for one uninterrupted loss count once. Four losses qualify when each consecutive gap is under five seconds. A gap of exactly five seconds or more starts a new sequence. Example: 0/4/8/12-second server-observed losses, with recovery between them.

Use server-confirmed events and timestamps, not client reports alone. Reset sequence at attempt end; retain a previously created flag. Exclude confirmed server outages. Flags are instability signals, not proof of cheating, and never automatically deduct points, suspend, restrict Ranked, or create Support tickets.

## Decision 8 — Support, review and retention

**REVISE / ADOPT NEW.** Owners: #26/#11/#10/#15/#16.

- Automatic recovery/settlement never waits for an administrator; it cannot guarantee repair of the player's internet.
- Support → Tickets, with Create ticket. No extra player Support options approved.
- Only a player request creates a ticket. Attach attempt ID, relevant connection events/timestamps, optional description.
- Players see their own tickets; authorized admins review tickets/flags. Other players cannot see them; never show tickets/flags on profiles or leaderboards.
- Outcomes: close as network instability; close as insufficient evidence without accusation; or leave open for follow-up. No point/access changes.
- Delete closed ticket/reviewed-flag descriptions and detailed connection events 15 days after closure. Keep open cases until resolved; seasonal scores and quiz history remain. Show deletion date. Shared open-case evidence is Q9.
- Exceptional score corrections are not authorized by this review.

## Decisions 9–10 — three hats and tie-breaks

**REVISE — dense ranking superseded for prize positions.** Owners: #12/#24/#5/#7/#11/#16/#17.

- Three prize positions, one UPS hat per winner, three hats total. Ties affecting prizes use the separate sort-work-methods quiz below. Q5 eligibility is settled in its dedicated section.
- Five Hard questions per round, five seconds each, same set for all players in that round. Correct +1, wrong/timeout 0; total 0–5. Seasonal points stay frozen.
- Asynchronous play; first deadline is season close +24 hours, not settlement completion +24 hours. Tie-breaks begin after eligible season attempts settle. One attempt per player per round.
- Completed attempts rank ahead of incomplete/nonparticipants. Compare completed players' scores; for tied Challenger players only (4,001+), incomplete/nonparticipants use who reached the tied final seasonal Challenger score first (exact event semantics Q6). The corresponding lower-rank outcome is open in Q3; do not extend this fallback to lower badges.
- Still tied: fresh five-question sets, shared within the new round, and a new 24-hour window when that round opens. Preserve resolved positions/earlier completed rounds. Q3 round limit remains settled: at most three valid rounds including the first, with outage-voided rounds excluded. The owner clarified Q6 scope: after round three or unavailable fresh questions, the first-reached-seasonal-score fallback is ONLY for tied Challenger players (4,001+), never lower badges or tie-break quiz scores. Lower-rank terminal/exhaustion/no-show outcomes are now open in Q3; exact Challenger timestamp/event semantics remain Q6. No fourth round, alternate fallback or new prize-rank minimum is approved.
- Disconnect: original-session 15-second grace; current five-second question timer continues, no next question while disconnected. Expiry → incomplete/no same-round retry. No seasonal adjustment.
- Intentional Quit: warning, immediate incomplete, no same-round retry, no seasonal -10.
- Confirmed server outage interrupting an attempt restarts the whole current round for all participants, even those already finished, with fresh questions and a fresh 24-hour window. Earlier completed rounds stay valid. This is the approved exception to the normal first-round deadline.
- Q4 settled: after a tie-break attempt show “Attempt submitted”; hide scores, correct answers, per-question correctness and detailed review until that round's 24-hour window closes. Enforce release in player-facing API responses, not only UI. Use the current round deadline after any approved outage restart. Normal Ranked keeps immediate feedback. This reduces answer sharing but cannot prevent players sharing question text. Q3 bounds valid rounds; it does not remove outage restart windows. Exact fallback ordering still requires Q6 before affected implementation; Q5 eligibility is settled below.

### Q5 — settled prize eligibility

- Only sorters in Primary Sort on the Twilight shift at Saddle Brook may win the three hats; one prize-eligible account and at most one hat per sorter.
- The owner privately confirms the sorter and approves their chosen account. Public identity stays username/tag; no public real-name/employee-ID or upload requirement is introduced. Delegation to other approvers is not approved.
- The approved account is fixed for that official season. Recovery uses the same account; no eligibility swap or point transfer. Other accounts are not automatically deleted or blocked.
- Approvals must be recorded before scheduled season closing: first official close December 31, 2026 at 11:59 p.m. America/New_York. No new approvals in the five-minute finishing window or tie-breaks; freeze the approved roster at closing.
- Also require one valid completed Ranked quiz credited to the official season. Already-approved players may satisfy this minimum through an eligible finishing-window completion; negative completed scores qualify. Pre-Season, void, unfinished or tie-break attempts alone do not qualify.
- The official competition leaderboard includes only players meeting those eligibility criteria. Ineligible accounts receive no competition position but may still play and see their own points/badge in their profile. Login is still required to view the leaderboard.
- Eligibility never changes point/partial-score rules or blocks registration/play. Approval contracts are owned by #7, admin UI by #11, standings by #12 and tie-break entry by #24; #16 reviews the screens.
- Non-prize tie-position numbering remains open under #12/#16; settling eligibility does not silently choose that ordering policy.

## Decision 11 — schedule

**REVISE.** Owners: #23/#13/#10.

Pre-Season runs until owner-controlled manual launch; official start date is not chosen. First official season ends December 31, 2026 at 11:59 p.m. Eastern (America/New_York). Later launch shortens the season. No January start, automatic launch date, or future season schedule is approved.

## Decision 12 — official launch reset

**ADOPT NEW.** Owners: #23/#6/#9/#10.

Reset current points/rank/promotion eligibility to 0/Iron/none. Treatment of active/gracing Pre-Season attempts at launch is still Q13, not implicitly settled here. Preserve accounts and Pre-Season history; Pre-Season does not count toward official prizes. Current-rank badges do not imply an additional achievement system.

## Decision 13 — ending-season attempts

**ADOPT NEW.** Owners: #23/#8/#9/#12.

Stop new Ranked admission at closing. Already-started attempts get five extra minutes, counting toward the ending season. At that deadline permanently end unfinished attempts and apply normal/promotion partial results, without Quit penalty, unseen-question deductions or suspicious-loss flags. Freeze points after settlement; prize standings remain provisional until required tie-breaks resolve.

## Decision 14 — identity and private email

**ADOPT NEW.** Owners: #6/#7/#10/#12/#15/#16.

- Chosen username plus generated unique permanent six-character uppercase letter/number tag, e.g. SortMaster#7K4P2M.
- Username uniqueness/login ignore case. Preserve internal ownership and tag through supported renames (already in #7).
- No real name/employee ID required for registration/display. Prize eligibility uses the settled owner-approval, season account lock, closing cutoff and eligible-only leaderboard policy in Q5. No real-name/employee-ID upload requirement is implied.
- Optional private email only; phone collection deferred. Never expose email in profile/leaderboard output.
- Email may support recovery and separately opted-in reminders. Remaining recovery/session/password/admin-verification/deletion rules stay open in #7/Q10.

## Decision 15 — one-time launch reminders

**ADOPT NEW.** Owners: #27/#7/#10/#16/#23.

- Separate initially unchecked option: “Email me when the first official season starts.” Recovery email alone is not consent; preference can change before launch.
- Delivery requires verified email plus active opt-in; choosing preference before verification does not permit unverified delivery.
- At launch retire opt-in, show season-start notice, preserve recovery email, and do not carry consent into future seasons.
- Consent withdrawal/email removal cancels unsent/queued mail. Recheck consent/verification immediately before sending.
- One initial attempt plus at most two retries within the first hour after launch: three total. Stop after provider-confirmed success, cancellation or exhaustion; record failure without blocking Ranked.
- Provider/costs, uncertain-send reconciliation and post-launch pending cancellation UX are Q11. No provider-independent exactly-once email guarantee is approved.

## Decision 16 — standings and notices

**ADOPT NEW.** Owners: #12/#10/#15/#16/#23.

Leaderboard requires login; guests retain Practice/study. Update canonical standings after each settled Ranked attempt, not daily. Show provisional state during season-end settlement/tie-breaks.

Logged-in Ranked landing page is the main season display: Pre-Season with no invented countdown; launch countdown when a start is confirmed; ending countdown while active; settlement/tie-break status when closed; then final results. Keep sort-change announcements on the main home page. Display capability does not authorize an automatic launch mechanism/date.

## Explicitly superseded / deferred

| Earlier proposal | Final disposition |
| --- | --- |
| Caps 100/200/300, uncapped Gold; promotions 101/201/301 | 1,000-point bands; Gold capped 4,000; Challenger 4,001+; cap+1 promotions |
| Uncapped seasonal balance or separate seasonal/rank balances | Rejected by final clarification: one balance, only Challenger uncapped |
| Zero-impact personal disconnect or Quit-only -10 | Rejected: partial score applies; intentional Quit adds -10 |
| Normal positive scoring during failed promotion | Correct +0, usual mistake/timeout deductions |
| Immediate terminal disconnection | 15-second grace; terminal attempts still never resume |
| Dense prize ranking / duplicate full prizes | Three hats; prize tie-break phases retained. First-reached-score fallback later restricted to Challenger only; lower-rank final fallback is unresolved |
| Indefinite official competition/no reset | Owner-controlled Pre-Season; official close/reset defined |
| Count four ended quizzes | Count distinct server-observed losses within an attempt |
| Automatic Support ticket / 90-day closed retention | Player-requested ticket / 15 days after closure |
| Phone/SMS, extra achievements, January season start | Deferred/unapproved |

## Decision status and visible open-question register

Q1/Q2/Q4/Q5 are settled; Q3 keeps its three-valid-round limit but lower-rank fallback is unresolved after the Challenger-only clarification. Q6 scope is partly settled; resolve its timing and Q7–Q13 individually before affected implementation; keep their IDs stable. #4 remains open. Non-prize tie-position numbering also remains open in #12/#16; recording settled decisions does not settle every boundary.

| ID | Decision / open question | Affected work |
| --- | --- | --- |
| Q1 — SETTLED | Apply the intentional Quit penalty before the rank cap. Iron 990 +100 -10 → 1,000 using the approved Q2 net-settlement cap; overflow can absorb the visible penalty. | #4/#9; warning wording #17 |
| Q2 — SETTLED | Apply the cap once when the attempt ends, after calculating its full result and any Quit penalty. Do not cap individual answers. Identical accepted answers produce the same regular adjustment regardless of order; promotion exceptions remain unchanged. | #4/#9 |
| Q3 — PARTLY SETTLED | Maximum three valid rounds, excluding outage-voided rounds. First-reached seasonal-score fallback is Challenger-only. Lower-rank outcomes after round three, missing fresh sets or unresolved no-show ties need a decision; do not invent another round/fallback or remove their prize eligibility. | #4/#5/#12/#24 |
| Q4 — SETTLED | Show submission confirmation only; withhold tie-break scores, correct answers, correctness and detailed review until the round's 24-hour window closes. Normal Ranked immediate feedback stays unchanged. | #4/#24/#17 |
| Q5 — SETTLED | Eligible-only official leaderboard: owner-approved Primary Sort/Twilight/Saddle Brook sorters, one fixed account/hat per person, approval before closing, one valid completed official-season Ranked quiz (eligible finishing-window/negative completion counts). Ineligible players may play/view own profile, without competition positions. See the dedicated Q5 section for full rules. | #4/#7/#11/#12/#24; design #16 |
| Q6 — PARTLY SETTLED | Score type/scope: tied final seasonal Challenger points (4,001+), not tie-break quiz scores and not lower-rank totals. Still open: first-ever attainment versus latest return, exact/threshold attainment and unique simultaneous-event order. Existing prize eligibility and prior tie-break phases remain unchanged. | #4/#12/#24 |
| Q7 | Automatic promotion entry or explicit action; remaining entry/acceptance boundaries? | #4/#8/#17 |
| Q8 | Server loss/outage signals, grace start/cadence, feedback pacing and original-session refresh/token definition? No reliable physical-device/intent claim. | #8/#25; affected policy in #4 |
| Q9 | Deletion of shared detailed events when another linked case remains open? | #26/#11 |
| Q10 | Remaining password/session/recovery/admin checks, disable/revocation/deletion/history, username validation and admin bootstrap? | #7/#11 |
| Q11 | Email provider/costs, uncertain-send reconciliation, post-launch pending cancellation UX? | #7/#27 |
| Q12 | Public hosting/recovery/30-player targets and owner-reviewed difficulty/version/duplicate policies? | #5/#13 |
| Q13 | What happens to active/gracing Pre-Season attempts when the owner launches/reset starts, including season ownership and settlement racing the reset? No carryover/cancel/settle policy is approved. | #4/#23; affected #6/#8/#9 behavior |

Existing health/CORS, rendering and API-client tests do not prove these planned competition features are implemented.
