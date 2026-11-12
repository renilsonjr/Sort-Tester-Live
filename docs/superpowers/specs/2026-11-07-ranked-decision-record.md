# Sort Test — settled decisions and open questions

**Status:** Owner decisions recorded November 7, 2026, from the November 6–7 discussion. Requirements only: competition features are not implemented. Backend health and local browser/API foundations are complete (#2/#3 closed).

**Related:** [[2026-11-06-ranked-pilot-design]], [[2026-11-06-ranked-roadmap]]. Parent roadmap: [#1](https://github.com/renilsonjr/Sort-Tester-Live/issues/1).

This record controls where earlier planning text differs. Only settled owner rules are approved. Assistant technical defaults remain proposals for PR review; implementation/resource gates are not completed features. **Update (2026-11-11, login/auth v2):** password-based login/recovery proposals are superseded by the [login ID auth plan (v2)](../plans/2026-11-11-login-id-auth-plan.md): login uses a system-generated **login ID shown once** (single-field sign-in, no password), **admin grants/regenerates access** for lost login IDs, and sensitive actions require **login ID reauthentication** (not “current password”). Where Decision 14/Q10 below mention passwords or self-service password recovery, read them through that plan. Keep #4 open until its required rule examples and affected ambiguities are resolved.

## Baseline retained

- Solo Ranked requires login: 15 randomized questions, five per difficulty, ten seconds each, locked answers and forward-only progression. Normal Ranked immediately reveals correctness and point changes after acceptance/timeout. Ranked/promotion feedback remains visible until Next; no next-question timer runs during feedback (Q8 pacing settled).
- Easy +10/-15; Medium +20/-10; Hard +30/-5. Timeout is wrong. Complete regular quiz raw range: -150 through +300.
- Owner timing clarification: a question clock starts when the server first sends its content, not when the browser acknowledges receipt. A sent question may time out without appearing during a connection failure; future questions never sent receive no deduction. Retransmission cannot reset the deadline. Applies to Ranked, promotion and prize tie-breaks.
- Server-owned assignment, deadlines, validation, atomic updates and exactly-once attempt settlement. Preserve raw performance versus applied adjustment in history; this is not a second points balance.
- Negative totals allowed, Iron badge floor. Repeat regular attempts after the previous one ends while season admission is open, subject to Q7 promotion-only entry at a capped badge’s cap.
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
- Losses demote; Bronze 1,010 with -150 → 860/Iron. Regaining Bronze requires 1,000 then perfect promotion again. Promotion entry follows settled Q7: explicit Start promotion is the only Ranked option at the cap, with Practice available.

- Q7 entry settled: Promotion entry uses an explicit “Start promotion” action. Show that a perfect 15/15 quiz is required before the player starts. Reaching the current badge cap makes promotion available but does not automatically create or start a promotion attempt; merely opening the promotion information does not start the quiz or its question timer. The player chooses when to initiate the attempt. Existing promotion scoring, cap+1 success, demotion/re-promotion, one-active-attempt and season-admission rules remain unchanged. At a capped badge’s settled point cap (Iron 1,000, Bronze 2,000, Silver 3,000, Gold 4,000), Start promotion is the only Ranked entry option; ordinary Ranked quizzes cannot start. Practice remains available unchanged. Below that badge’s cap, ordinary Ranked quizzes remain available under existing season/active-attempt rules. Challenger is uncapped and has no promotion gate. Apply this gate when starting a new attempt using current server state; do not interrupt an existing quiz or cap individual answers. A failed promotion that settles below the cap returns the player to ordinary Ranked until eligible again.

- Q8 feedback pacing settled: In ordinary Ranked and promotion quizzes, after the server accepts an answer or resolves its timeout, show the answer feedback and keep it visible until the player presses Next. Do not auto-advance or run the next question’s ten-second timer while feedback is displayed. Activate the next question and its new server-controlled deadline only after Next is accepted; do not deliver a future question while disconnected. Accepted answers remain locked, and repeated Next requests must not skip questions, extend deadlines or create multiple active questions. Existing season-close/finishing-window, connection-grace, refresh and one-active-attempt rules remain active during feedback; feedback is not an indefinite extension past season termination. The final question completes/settles the attempt under existing rules without needing a Next click; no extra question is created. Practice is unchanged. Prize tie-break score/correctness/answer-review secrecy until the round deadline is unchanged; this decision does not authorize revealing tie-break feedback.

## Decision 5 — grace, timeout and outage

**REVISE / ADOPT NEW.** Owners: #4/#8/#9/#23/#25.

- Fifteen seconds of grace after server loss declaration before terminal disconnection. Reconnect before expiry to continue the original still-running session; reloading the tab does not permit resumption (Q8 refresh policy settled). At expiry end permanently and settle partial score.
- Current question clock keeps running; timeout deducts normally. Send no next question until reconnection. No deductions for future questions never sent. Owner clarification: a sent question can time out even if a connection failure prevents its display; its server clock starts at first send, never client acknowledgment.
- Confirmed server-wide outage voids affected normal Ranked/promotion attempts: zero adjustment, no Quit penalty or suspicious flag, no resume. Fresh attempts after recovery remain subject to season admission.
- Server loss/outage evidence and cadence defaults are in [[2026-11-07-ranked-security-operations-design]] (Q8 proposal). A failed request alone does not prove a server-wide outage.

## Decision 6 — active attempt and original session

**ADOPT NEW.** Owners: #4/#7/#8.

One active Ranked attempt per account, including grace. Another tab/device cannot start a replacement, cancel the original, or continue it. Reconnect only through the original quiz session, not another device. Practice remains available. Refreshing or reloading the original quiz tab must not allow the attempt to be resumed, even within the 15-second grace period. Grace-based continuation is limited to recovery in the original still-running quiz session. This applies to ordinary Ranked, promotion and prize tie-break attempts. Another tab/device still cannot resume or replace the attempt. No page reload may reset a question clock, erase accepted answers, or bypass the one-active-attempt rule. After refresh-related connection loss, finalize the attempt at the existing server-controlled 15-second connection-loss deadline. The refreshed page cannot rejoin during that window. Reloads, repeated reconnect requests or new tabs do not reset or extend the deadline or question clock. Keep the account’s active-attempt lock until the server finalizes exactly once. Ordinary Ranked/promotion settle accepted partial results under their existing rules, without an extra Quit penalty; prize tie-breaks become incomplete with no same-round retry or seasonal-point adjustment. Current-issued-question timeout and no-never-sent-question deduction rules, confirmed-outage exceptions and season-closing rules remain unchanged. Q8 implementation defaults are proposed in [[2026-11-07-ranked-security-operations-design]]; do not claim every refresh is instantly detected. Partial-score settlement and explicit-Quit-only penalties retain the existing rules; a refresh is not automatically assigned the extra -10 Quit penalty. An account’s active attempt remains active until the server finalizes it under the approved termination policy. Confirmed-outage exceptions remain unchanged. No reliable physical-device identification is promised.

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
- Delete each closed ticket/reviewed-flag description and its unshared detailed connection events 15 days after closure. Keep open cases until resolved; seasonal scores and quiz history remain. Show the applicable deletion date, or that shared evidence is retained for an open linked case. Q9 settled: Keep a shared detailed connection log while any linked Support ticket or administrator flag review remains open. Once every linked case is closed, delete that shared log 15 days after the last linked case’s closure. If a linked case is reopened or another open case is linked before deletion, do not purge evidence still needed by that open case; apply the last-closure rule once all linked cases are closed again. For confirmed account deletion, Q10’s wipe with only the minimal eligibility record exception applies: purge/delink the deleted account’s own detail while preserving evidence belonging to other players; implementation boundaries still need design. This Q9 ordinary-closure exception extends only the shared connection evidence: each closed ticket/review’s own description keeps its separate 15-day cleanup schedule. Preserve seasonal scores/quiz history for accounts not deleted under Q10, and preserve existing access controls; sharing evidence does not expose one player’s ticket or private notes to another player.
- Exceptional score corrections are not authorized by this review.

## Decisions 9–10 — three hats and tie-breaks

**REVISE — dense ranking superseded for prize positions.** Owners: #12/#24/#5/#7/#11/#16/#17.

- Three prize positions, one UPS hat per winner, three hats total. Use separate quizzes for ties affecting prizes; Q5 eligibility below still applies.
- Five shared Hard sort-work-methods questions per round. Correct +1, wrong/timeout 0; total 0–5, with no seasonal-point changes. Challenger rounds and lower-rank rounds 1–3 use five seconds per question; lower-rank round 4 uses four seconds and round 5 uses three seconds, the minimum.
- Play asynchronously once per participant per round. First deadline is scheduled season close +24 hours, not settlement +24 hours; start after eligible season attempts settle. Each additional round uses a fresh shared set and a new 24-hour window from opening. Preserve valid prior tie-break outcomes and remaining-player relative order/earlier valid rounds.
- Challenger has at most three valid rounds; lower ranks have at most five. Outage-voided rounds do not consume this limit and their restarts retain the current round timer. After the applicable maximum, any remaining completed-player prize tie waits for authorized owner selection among the still-tied eligible players. No automatic extra round or first-arrival ordering.
- If there is no fresh shared set of five approved Hard questions for any round or outage restart, affected unresolved prize positions wait for authorized owner selection, for every badge including Challenger. Do not silently reuse questions or approve new content. Preserve valid prior tie-break outcomes and remaining-player relative order and frozen points.
- Completed attempts outrank incomplete/no-shows. For lower ranks, any prize places still unresolved among multiple incomplete/nonparticipating eligible players after the round deadline wait for owner selection, below completed attempts; no extra quiz for that incomplete group.
- At the close of a valid Challenger tie-break round’s 24-hour window, automatically exclude participants whose attempt is incomplete or who did not participate from that season’s top-three prize positions. If both players fail to complete, both are excluded. Keep their frozen seasonal points, badge and history unchanged; this affects prize placement only. A completed 0/5 attempt remains completed. A confirmed server outage voids/restarts the whole round under the existing policy, so a voided round or its superseded deadline cannot trigger this exclusion.
- Q14 backfill approved: After automatic Challenger noncompletion/no-show exclusion, fill vacant top-three prize places from the next eligible, non-excluded players using frozen seasonal points and the existing prize tie-break rules. Do not change points or badges or reinstate excluded players. Preserve valid prior relative tie-break order; numbered prize places compact upward after approved removals. A tie newly affecting a prize must be resolved before a winner is finalized; do not invent ordering between tied candidates. A newly affected replacement tie group gets a fresh 24-hour window measured from the opening of its round, not the original season-close deadline or another group’s deadline. All players in that round share its deadline; per-question timers, feedback release, one-attempt rule, exclusion handling and confirmed-outage restarts retain the existing tier-specific policies. Preserve frozen seasonal points and valid prior relative order; numbered prize places can shift upward. If fewer than three eligible, non-excluded players remain after the approved backfill/tie-break process, award one hat to each available confirmed winner and leave every remaining hat unawarded. If nobody remains eligible, award no hats. Do not reinstate excluded players, waive eligibility, invent winners, change frozen points/badges, or discard valid prior tie-break outcomes to force three awards. Unresolved ties or an owner selection still pending are not candidate exhaustion; finalize those cases under the existing rules first.
- Disconnection: 15-second original-session grace; current question timer continues, with no next question sent while disconnected. Expiry ends the attempt as incomplete with no same-round retry and no seasonal adjustment. Intentional Quit warns, ends incomplete/no retry, and has no seasonal -10 deduction.
- A confirmed server outage interrupting an attempt restarts the whole current round for all participants, including players already finished, with fresh questions and a new 24-hour window. Earlier valid rounds remain. This is the approved exception to the original deadline.
- Q4: after submission show “Attempt submitted”; withhold scores, correctness, correct answers and detailed review in API responses and UI until the current round’s 24-hour window closes, including an outage-reset deadline. Normal Ranked retains immediate feedback. This cannot prevent sharing question text.
- Q8 tie-break advancement settled: Prize tie-break questions advance automatically after the server accepts an answer or resolves the current question’s timeout. There is no Next button or player-controlled feedback pause between tie-break questions. Activate each next question with its own existing round-specific timer: five seconds for Challenger and initial lower-rank rounds, four seconds for lower-rank round four, three seconds for round five. Keep answers locked and resolve each question only once; duplicate/late requests cannot skip questions or restart/extend clocks. After the fifth resolved question, finish the attempt under the existing completion rules and show only submission confirmation. Do not reveal correctness, scores, answers or review in API responses/UI before the round’s valid deadline. Do not send a next question while disconnected: keep the current clock, original still-running-session grace and refresh restrictions; on eligible recovery continue automatically without resetting clocks. Grace expiry, Quit, season/round deadlines and confirmed-outage policies keep their existing effects. Ordinary Ranked/promotion feedback still waits for Next and Practice remains unchanged.
- Question inventory (#5): owner prepares/reviews Easy, Medium and Hard lists, answers and explanations. Verify unique approved normal questions for 5/5/5 assignments and approved Hard work-methods sets for tie-breaks; bank sufficiency has not been verified.
- Q6 is settled: the earlier first-reached-seasonal-score fallback and its timestamp/event-definition questions are superseded. Current points still determine ordinary leaderboard order and badge rules are unchanged. Manual selection is limited to the approved unresolved prize cases; it does not authorize point/result edits.

### Q5 — settled prize eligibility

- Only sorters in Primary Sort on the Twilight shift at Saddle Brook may win the three hats; one prize-eligible account and at most one hat per sorter.
- The owner privately confirms the sorter and approves their chosen account. Public identity stays username/tag; no public real-name/employee-ID or upload requirement is introduced. Delegation to other approvers is not approved.
- The approved account is fixed for that official season. Recovery uses the same account; no eligibility swap or point transfer. Other accounts are not automatically deleted or blocked.
- Approvals must be recorded before scheduled season closing: first official close December 31, 2026 at 11:59 p.m. America/New_York. No new approvals in the five-minute finishing window or tie-breaks; freeze the approved roster at closing.
- Also require one valid completed Ranked quiz credited to the official season. Already-approved players may satisfy this minimum through an eligible finishing-window completion; negative completed scores qualify. Pre-Season, void, unfinished or tie-break attempts alone do not qualify.
- The official competition leaderboard includes only players meeting those eligibility criteria. Ineligible accounts receive no competition position but may still play and see their own points/badge in their profile. Login is still required to view the leaderboard.
- Eligibility never changes point/partial-score rules or blocks registration/play. Approval contracts are owned by #7, admin UI by #11, standings by #12 and tie-break entry by #24; #16 reviews the screens.
- Unique final prize placements are required only for the top three. Numbering/display of tied non-prize places is a routine presentation detail, not an unresolved competition-policy decision or implementation blocker. Do not run extra tie-break quizzes solely to distinguish places below the prize top three. No specific shared-place/dense/skipped-number format was selected. If a previously non-prize tie later affects a prize through approved withdrawal/backfill, apply the existing prize tie-break rules and replacement-round windows. Preserve valid earlier relative tie-break order and the approved leaderboard eligibility/visibility rules.

## Decision 11 — schedule

**REVISE.** Owners: #23/#13/#10.

Pre-Season runs until owner-controlled manual launch; official start date is not chosen. First official season ends December 31, 2026 at 11:59 p.m. Eastern (America/New_York). Later launch shortens the season. No January start, automatic launch date, or future season schedule is approved.

## Decision 12 — official launch reset

**ADOPT NEW.** Owners: #23/#6/#9/#10.

At the owner’s manual official-season launch, end/void every unfinished Pre-Season Ranked or promotion attempt, including active questions, feedback-waiting attempts and connection-grace attempts, without applying its score or promotion result. Preserve its Pre-Season record and accepted history; do not mark it completed or credit it to the official season. Then reset current points/badge/pending promotion to 0/Iron/none while retaining accounts and earlier completed Pre-Season history. Show preserved completed and launch-ended Pre-Season attempts in a profile tab named exactly “pre season history”. Distinguish completed results from attempts ended at launch; do not invent missing answers. Pre-Season results never count toward official-season points or prize qualification. Practice remains unchanged, as do existing private Support/email/flag access restrictions; the new history tab must not expose private incident details. The “pre season history” tab is owner-private under settled Q10 history visibility: no other-player access, server-side ownership checks, and no automatic administrator exception. Q10 implementation defaults are proposed in [[2026-11-07-ranked-security-operations-design]]. Launch/reset and attempt finalization must enforce phase ownership and once-only cutover: a Pre-Season answer/result arriving late must not add points or a promotion to the official balance. A result settled before launch remains completed Pre-Season history, then the reset applies; a still-unfinished attempt at cutover is preserved as launch-ended/void. Repeated launch/finalization requests must not reset newly earned official points or apply an old result twice. Exact transaction implementation belongs to #6/#8/#9/#23; the approved observable result is no Pre-Season carryover. This manual launch is not an intentional Quit or a connection-loss event and creates no extra Quit penalty or loss flag. Current-rank badges do not imply an additional achievement system.

## Decision 13 — ending-season attempts

**ADOPT NEW.** Owners: #23/#8/#9/#12.

Stop new Ranked admission at closing. Already-started attempts get five extra minutes, counting toward the ending season. At that deadline permanently end unfinished attempts and apply normal/promotion partial results, without Quit penalty, deductions for never-sent questions or suspicious-loss flags. Freeze points after settlement; prize standings remain provisional until required tie-breaks resolve.

## Decision 14 — identity, recovery, deletion and privacy

**SETTLED OWNER POLICY (revised 2026-11-11 for login ID auth; see [login ID auth plan (v2)](../plans/2026-11-11-login-id-auth-plan.md)); technical defaults proposed separately.** Owners: #6/#7/#10/#11/#12/#15/#16.

- Case-insensitive unique username, stable internal ownership (`accounts.id` UUID) and generated permanent unique six-character uppercase alphanumeric tag. Supported renames keep ownership/tag. No required real name, employee-ID upload or phone collection. Optional email remains private and never appears in profiles/leaderboards.
- **Login credential (v2):** on account creation the system generates a separate **login ID** (short, grouped, easy-to-type secret) shown **once**; the login page accepts only this login ID (no password). It is distinct from the display identity beside names (`username`/`tag`). Store only a verifier (no raw login ID); treat as a bearer secret with rate limiting and generic failures.
- **Lost access / recovery (v2):** there is no self-service password or secret recovery. If a user loses the login ID, only the **admin/owner may grant/regenerate access** after **in-person verification at work against a trusted participant/account link established before the request** (owner-approved). Public username/tag alone is insufficient; no trusted prior link means no reset/grant via this route. Recovery restores access only to the same existing account by issuing a **new login ID shown once** (revoking the old credential and sessions); never disclose the old secret, never transfer points, never create substitute prize eligibility, and never restore wiped data or grant player-private history access. Adding/verifying email or recovering access never grants reminder consent.
- The exact “pre season history” tab and all underlying lists/attempts/details/downloads are private to the owning player, server-enforced; no other-player access or automatic administrator exception. Authorized Support incident review remains limited to its incident scope.
- Own-account deletion is self-service, authenticated and ownership-confirmed; no owner/admin approval. Opening the screen, checking a checkbox, canceling, a recovery request or a failed/unconfirmed deletion does not delete or withdraw anyone. The server must validate explicit acknowledgment and ownership, not trust a disabled browser button.
- Dialog question: “Are you sure you want to proceed with deleting this account?” Required initially unchecked checkbox: “I agree to delete my account. I understand that deleting it before prizes are finalized removes this account from this season’s competition.” Offer Cancel and final Delete account, disabled until checked. Reopening resets it unchecked. Explain: “After deletion is completed, your profile, quiz history and points are removed. A new account starts at 0 points / Iron.” Disclose: “Your profile, email, quiz history and points are deleted. We keep only a private season-ineligibility record until prizes are finalized.”
- **Reauthentication (v2):** require recent **login ID reauthentication** (re-enter login ID / equivalent short-lived reauth bound to the session) in place of “current password”, together with CSRF protection, account ownership and the approved explicit unchecked acknowledgment/final Delete action. Cancel is available before final submission; after the server accepts the irreversible authorized deletion there is no undo or restoration. Invalid/unauthorized requests roll back without withdrawal.
- Confirmed deletion before prizes are finalized automatically withdraws the account. Remaining eligible candidates move up; preserve prior valid relative tie-break order, not fixed numbered places. New prize-impacting ties use approved replacement-round rules. No already-finalized-award clawback or automatic reinstatement is authorized.
- Completed deletion wipes profile/contact/credentials, all quiz/attempt/answer/history/score records including Pre-Season, personal Support/flag/connection details and account-owned email records. No “Deleted player” score row, hidden recoverable profile or restoration of old data. A fresh account starts 0/Iron and may use otherwise permitted modes, but cannot regain this season’s prizes. Preserve other players' results/evidence, shared question content and guest Practice.
- **Only retention exception (recognizable roster reference explicitly approved November 7):** minimal owner-recognizable private roster reference, season reference and ineligible state, solely for owner eligibility checks until that season's prizes are globally finalized, then purge. No username/email, old account/profile/credentials, history, answers, score or badge. No public exposure or recovery authority. No additional deleted-account retention is approved; ordinary Support retention does not override the wipe.
- Proposed irreversible acceptance, active-attempt/session/mail cleanup, marker linkage, shared-evidence redaction, finalization races and deletion-safe backups remain as detailed in [[2026-11-07-ranked-security-operations-design]] **as superseded for credential mechanics by the login ID auth plan (v2)**. These are reviewable implementation defaults, not working features or a new retention exception. If actual provider/storage behavior cannot meet the wipe rule, stop and return that conflict for owner review.

## Decision 15 — one-time launch reminders

**ADOPT NEW.** Owners: #27/#7/#10/#16/#23.

- Separate initially unchecked option: “Email me when the first official season starts.” Recovery email alone is not consent; preference can change before launch.
- Delivery requires verified email plus active opt-in; choosing preference before verification does not permit unverified delivery.
- At launch retire opt-in, show season-start notice, preserve recovery email, and do not carry consent into future seasons.
- Consent withdrawal/email removal cancels unsent/queued mail. Recheck consent/verification immediately before sending.
- One initial attempt plus at most two retries within the first hour after launch: three total. Stop after provider-confirmed success, cancellation or exhaustion; record failure without blocking Ranked.
- Proposed provider/budget, uncertain-send reconciliation and post-launch pending cancellation behavior are in [[2026-11-07-ranked-security-operations-design]] (Q11). No provider-independent exactly-once email guarantee is approved.

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
| Dense prize ranking / duplicate full prizes | Three hats; prize tie-break phases retained. First-reached-score fallback superseded by manual owner selection and Challenger noncompletion exclusion; lower-rank ties remaining after round five require owner selection; earlier fresh-question exhaustion also goes to owner selection; unresolved no-show spots go to owner selection after the round deadline, below completed attempts |
| Indefinite official competition/no reset | Owner-controlled Pre-Season; official close/reset defined |
| Count four ended quizzes | Count distinct server-observed losses within an attempt |
| Automatic Support ticket / 90-day closed retention | Player-requested ticket / 15 days after closure |
| Phone/SMS, extra achievements, January season start | Deferred/unapproved |

## Decision status and implementation gates

Owner competition policies are settled. Q8/Q10/Q11/Q12 now have explicit **assistant-proposed technical defaults** in [[2026-11-07-ranked-security-operations-design]], for review through this PR. These are not claims of owner-approved software details or completed features. Actual content approval, service provisioning/contract tests, reviewed mockups and rollout measurements remain execution gates in their owning issues.

| ID | Decision / status | Owners |
| --- | --- | --- |
| Q1 | Settled: Quit -10 before cap | #4/#9/#17 |
| Q2 | Settled: cap once after whole attempt, never per answer | #4/#8/#9 |
| Q3 | Settled: lower-rank rounds 5/5/5/4/3 seconds, maximum five valid rounds, then owner selection; insufficient fresh questions also owner selection | #4/#5/#24 |
| Q4 | Settled: hide tie score/correctness/answers/review until valid round deadline | #4/#17/#24 |
| Q5 | Settled: Primary Sort / Twilight / Saddle Brook sorters; owner approves fixed prize account before close; one valid completed official quiz required, even negative, with finishing-window completion allowed for already-approved players | #7/#11/#12/#23 |
| Q6 | Settled: no first-reached timestamp fallback; Challenger incomplete/no-show exclusion at valid deadline, max three valid five-second rounds then owner selection | #4/#12/#24 |
| Q7 | Settled: explicit Start promotion only at capped rank's cap; no automatic start; Practice available | #4/#8/#10/#17 |
| Q8 | Pacing/refresh/grace and first-send timer settled; a sent-but-undelivered question may time out, never-sent questions cannot be deducted; loss cadence, page capability, delivery and outage protocol proposed in technical design; acceptance tests required | #6/#7/#8/#9/#17/#24/#25/#13 |
| Q9 | Settled: shared logs retained while any linked case open, then 15 days from last closure; each closed description retains its own schedule; account wipe overrides own data | #11/#25/#26 |
| Q10 | Recovery proof settled: in-person plus trusted prior link; recognizable private roster reference approved for the minimal season marker. Account/privacy/deletion outcomes settled. **Auth v2 (2026-11-11):** login by system-generated login ID shown once (no password), admin-granted/regenerated access for loss, login ID reauthentication for sensitive actions (PostgreSQL). Marker, purge/backup and race defaults remain proposed in technical design as adapted by [login ID auth plan (v2)](../plans/2026-11-11-login-id-auth-plan.md) | #6/#7/#10/#11/#12/#16/#23/#26 |
| Q11 | Conditional Brevo adapter, $0 budget, bounded outbox/reconciliation and pending cancellation proposed; no live sends/provider contract verified | #7/#16/#27 |
| Q12 | Bank identity/versioning and same-origin Windows/tunnel/load/recovery defaults proposed; actual owner content approval, resources and measured rollout thresholds still required | #5/#6/#13 |
| Q13 | Settled: void unfinished Pre-Season at manual launch, reset 0/Iron/none, preserve private history; block late Pre-Season effects | #6/#8/#9/#10/#23 |
| Q14 | Settled: backfill next eligible, compact places preserving relative order, new prize ties get new 24 hours; fewer eligible winners means fewer hats awarded | #12/#16/#17/#24 |

Existing health/CORS, rendering and API-client tests cover foundations only. No authentication, competition database, Ranked engine, deletion, Support, email or public pilot is implemented by this documentation PR.
