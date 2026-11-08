# Ranked worked examples and state transitions

**Status:** The owner confirmed examples 1–27 individually in chat on November 7, 2026. The state-transition table below is a proposed consolidation for review, not a separately approved implementation. Documentation only: no Ranked engine or executable business-rule tests are added here. Issue [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4) remains open.

**Controlling policy:** [[2026-11-07-ranked-decision-record]]. Technical defaults and operational evidence gates: [[2026-11-07-ranked-security-operations-design]]. Build order: [[2026-11-06-ranked-roadmap]]. Do not reinterpret a future verification target as a passing feature test.

## Reading the arithmetic

“Raw score” means the ordinary difficulty-weighted performance score. A promotion stores that performance separately, but its applied adjustment gives correct answers zero and deducts for mistakes/timeouts; perfect completion instead sets cap+1. The one current balance, not raw performance, determines badge and standings. A partial score is the accepted/resolved result so far, not the potential result of unanswered questions. Except where an example explicitly includes a later timeout, partial-score arithmetic assumes no further deductions before settlement.

For regular attempts in a capped badge, calculate the whole result and any Quit -10 first, then apply that badge's cap once. Discard overflow. Never cap each answer. Challenger is uncapped. Settlements, phase changes and terminal actions must be applied once; these examples describe required outcomes, not code that currently enforces them.

## Owner-confirmed examples

| # | Starting situation / event | Applied outcome | What can happen next |
| --- | --- | --- | --- |
| 1 | Iron 950; completed regular quiz raw +300 | 950+300=1,250, capped to **1,000/Iron**; adjustment +50, discard 250 | Only explicit Start promotion for Ranked; Practice available |
| 2 | Iron 990; partial +100, then explicit Quit | 990+100−10=1,080, capped to **1,000/Iron**; adjustment +10, discard 80 | Attempt permanently ended; promotion available. Penalty applied even though overflow absorbs its visible effect |
| 3 | Iron 1,000; promotion 14/15, one Easy mistake | Correct answers +0, mistake −15 → **985/Iron**, adjustment −15. Ordinary raw performance is +275, not the applied result | Earn 15 in regular Ranked to reach cap, then try a new promotion |
| 4 | Iron 1,000; perfect 15/15 promotion | Set **1,001/Bronze**, adjustment +1; do not add ordinary +300 | Regular Ranked below Bronze cap |
| 5 | Bronze 1,010; completed regular raw −150 | **860/Iron**, adjustment −150 | Earn back to 1,000 and pass another perfect promotion; no permanent rank entitlement |
| 6 | Iron 500; partial −40; personal loss reaches 15-second grace expiry | Assuming no further current-question deduction, **460/Iron**, adjustment −40; no extra Quit −10 | Terminal attempt never resumes; fresh admission after final settlement. Any already-sent timeout still counts |
| 7 | Connection returns before grace expires in original still-running page | Continue same attempt with its existing current deadline; no timer reset | Refresh/other tab/device cannot resume. At the deadline expiry wins; return must be strictly before it |
| 8 | Iron 500; partial +80; confirmed server-wide outage interrupts quiz | Void normal/promotion attempt, **500/Iron**, adjustment 0; no Quit penalty/flag | Fresh attempt after recovery if admission open. Uncertain outage classification keeps settlement/admission pending under the technical design |
| 9 | Iron 500; quiz active at season close, remains unfinished after five-minute finishing window with partial +80 | **580/Iron**, adjustment +80; no extra Quit penalty or deductions for never-sent questions; freeze after settlement | Unfinished attempt does not satisfy completed-official-quiz prize minimum |
| 10 | Pre-Season 850; unfinished quiz at owner's manual official launch | Void old attempt with zero adjustment, preserve accepted Pre-Season record; official balance **0/Iron/no promotion** | Private exact tab “pre season history”; late old answers cannot enter official points |
| 11 | Gold at 4,000; perfect promotion, then regular +300 | Promotion → **4,001/Challenger**; next quiz → **4,301/Challenger** | No upper cap. Later falling below 4,001 demotes to Gold; regaining Challenger requires promotion again |
| 12 | Server first sends a ten-second question; delivery fails before it appears | Its deadline continues and a timeout deducts normally, even without display | No next question while known disconnected; never-sent future questions receive no deduction. Retry cannot reset deadline |
| 13 | Iron promotion at 1,000; one Easy mistake, then Quit | **975/Iron** =1,000−15−10; adjustment −25 | Disconnect/grace expiry instead gives **985/Iron**, adjustment −15, assuming no further timeout. Both terminal attempts require fresh play |
| 14 | Two eligible Challenger players tied for third at frozen 5,000; shared five-Hard round scores 4/5 and 3/5 | After valid round deadline, 4/5 wins third; both keep **5,000/Challenger** | Tie result affects prize order only; no seasonal-point adjustment |
| 15 | Challenger prize tie: one completes 0/5, another incomplete at valid deadline | Completed 0/5 outranks incomplete; incomplete is excluded from season top-three prizes, points/badge unchanged | If neither completes, both excluded; backfill next eligible using existing prize rules |
| 16 | Confirmed server-wide outage interrupts current tie round; one participant already finished | Void **whole current round for everyone**, fresh shared set and new 24-hour window | Earlier valid rounds preserved. Void round consumes no valid-round limit/timer step and triggers no no-show exclusion |
| 17 | Challenger players still tied after three valid five-second rounds | No fourth round and no first-reached timestamp fallback | Owner selects among still-tied eligible players for unresolved prize; frozen points/badges unchanged |
| 18 | Lower-rank prize tie continues through additional rounds | Up to five valid rounds at **5/5/5/4/3 seconds** per question; each additional round fresh set/new 24 hours | Owner selection after limit or earlier fresh-approved-question exhaustion; no silent reuse |
| 19 | First place confirms account deletion before global prize finalization | Withdraw; second→first, third→second, next eligible may fill third; others' points unchanged | Preserve valid prior relative tie order, not fixed place numbers. New prize-impact tie uses existing rules/new round window |
| 20 | After valid removals and required tie resolution only two eligible confirmed winners remain | Award one hat each, leave third unawarded; nobody eligible → no hats | Pending owner selection/tie is unresolved work, not candidate exhaustion |
| 21 | Owner approved sorter before season close; first valid official quiz already active, completes in finishing window at −50 | Completed quiz satisfies participation minimum despite negative score | Final points/ties still decide prizes. Approval cutoff is not extended; Pre-Season/void/incomplete/tie-only do not qualify |
| 22 | Player deletes account and registers again same season | New account **0/Iron**, no old profile/history/scores restored; may play but no same-season prize re-entry | Only approved private owner-recognizable roster reference/season/ineligible marker remains until global prizes finalized, then purged |
| 23 | Forgotten password, no verified email | Only owner-approved **in-person check at work against trusted prior participant/account link** permits reset | Public username/tag insufficient. No trusted prior link → no reset via this route. Restore only existing account, never wiped data |
| 24 | Player refreshes active quiz then tries starting another Ranked attempt | Refreshed page cannot resume or replace original; active-account lock lasts through finalization | Existing grace/current clock continues; refresh adds no Quit −10, clears no partial result and cannot restart timer. Outage-pending settlement can retain lock longer |
| 25 | Season closes 11:59 p.m.; finishing settlement completes 12:04 a.m. | Initial tie deadline remains **11:59 p.m. following day**, 24 hours from scheduled close | Additional/replacement rounds get fresh 24 hours from opening; starting late does not extend deadline |
| 26 | Distinct server losses at 0/4/8/12 seconds, with recovery between | Four losses with each gap<5 seconds create private review flag | Exactly five-second gap resets sequence. No deduction, suspension, Ranked block or automatic ticket; not cheating proof |
| 27 | Two lower-rank tied players both incomplete at round deadline | Unlike Challenger, no automatic prize exclusion; unresolved incomplete group goes to owner selection below completed players | Frozen seasonal points unchanged; no extra round solely for that incomplete group |

## Proposed state-transition contract — review still required

These names explain behavior; they do not dictate database enum names or new API routes. Attempt progress (question versus feedback) is separate from connection status (connected versus grace), so reconnecting can return to the same feedback without creating another question.

| Current state | Event / guard | Required next state and effect |
| --- | --- | --- |
| No active attempt | Authenticated Start; admission/content/phase/account-lock valid | Create one normal or promotion attempt. At capped badge cap only explicit Start promotion is valid; opening info alone never starts it |
| Active question | First server send | Establish one sequence and deadline; retransmissions keep it. Never expose future question content before its activation/send |
| Active normal/promotion question | Valid answer before deadline, or resolved timeout | Lock result once; feedback, unless final question, which ends without needing Next |
| Normal/promotion feedback | Accepted Next while connected/admitted to continue | Activate/send exactly one next question and deadline. Duplicates cannot skip/extend; no timer while still awaiting Next |
| Active tie question | Answer accepted or timeout | Automatically activate/send next question while connected; final question completes. Never reveal score/correctness/keys/review before valid round deadline |
| Active progress, connected | Server declares loss | Same progress plus fixed 15-second grace; keep issued deadline and active lock; send no next question while loss known |
| Grace | Original still-running page returns strictly before expiry | Restore same attempt/progress and original deadline; no refresh/other-page continuation, no new grace extension for duplicate requests |
| Active/grace | Original page refreshes or a different page tries to rejoin | Reject resumption/replacement; keep the original loss deadline and account lock. Refresh itself does not finalize the attempt or extend grace |
| Grace | Existing deadline expires, including recovery at/after it | Permanently end; normal/promotion partial, tie incomplete/no same-round retry. No extra Quit penalty; retain lock until outcome committed |
| Any active normal/promotion progress | Authorized confirmed Quit | Permanently end with partial result and −10 before cap; do not pause clock for confirmation |
| Any active tie progress | Confirmed Quit | Incomplete/no same-round retry, no seasonal −10 |
| Terminal intent, outage classification unresolved | Trusted common-failure evidence incomplete | Settlement pending; no provisional balance/new Ranked admission/prize finalization. Practice remains separate |
| Settlement pending | Personal-loss outcome confirmed and original phase/round still valid | Apply normal/promotion partial once or tie incomplete; release lock on committed final state. Old-phase/void-round delayed results cannot write points or re-lock the account |
| Affected attempt/round | Confirmed service-wide outage | Normal/promotion void zero/no flag; tie whole-current-round void/restart for everyone with fresh questions/window, prior valid rounds retained |
| Uncommitted Pre-Season normal/promotion, including active, feedback, grace or settlement pending | Owner manual launch cutover wins transaction ordering | Preserve as launch-ended/void, no result applied; reset official0/Iron/no promotion once, release old-phase lock. Delayed old-phase classification/results cannot write official state or re-lock it |
| Official season open | Scheduled close | Reject new Ranked; existing attempts continue only within five-minute finishing window; no new prize approvals |
| Unfinished official attempt | Finishing deadline | End partial/no extra Quit/no never-sent deduction/flag; settle/freeze after required outage classification |
| Terminal committed | Repeated/late answer, Next, Quit, timeout or reconnect | Same terminal outcome, no second score/attempt/resume; no cross-phase/cross-round mutation |
| Tie round open | Valid deadline | Reveal allowed review/results; apply completed/incomplete tier rules and determine next round, owner fallback or backfill; superseded void deadline has no effect |
| Prize provisional | Accepted authorized account deletion | Serialize withdrawal with global prize finalization, then compact/backfill; no automatic clawback of finalized award or retained deleted-player score row |

## Arithmetic and boundary checks to implement later

- All fifteen regular answers wrong: 5×−15 + 5×−10 + 5×−5 = **−150**. All correct: 5×10 + 5×20 + 5×30 = **+300**. At 0/Iron, a completed −150 quiz gives **−150/Iron**, not a zero floor.
- Repeat examples 1–4 at caps 2,000/3,000/4,000: success sets 2,001/3,001/4,001 respectively. A regular capped attempt can never itself bypass a promotion.
- Exercise just-before/exactly/after question/grace/season/round deadlines, duplicate/lost responses, answer-versus-timeout, Quit-versus-completion, outage evidence delay, launch-versus-answer and deletion-versus-prize-finalization. Implement server ordering under a reviewed small plan; do not claim this document supplies an executable engine oracle.
- Check content sufficiency, privacy/role boundaries and lower/Challenger tie distinctions from the controlling record. Never use only happy-path arithmetic to certify the engine.

## Issue #4 completion boundary

Examples 1–27 are owner-reviewed expectations. The transition table and its implementation ordering still need review; executable business-rule tests are future #8/#9/#23/#24/#25 work under their own plans. Existing health/CORS/browser tests do not exercise these outcomes. Keep #4 open until its documentation/protocol acceptance is reviewed; do not wait for every downstream feature to be built to finish a requirements issue, and do not mark downstream features complete merely because #4 is accepted.
