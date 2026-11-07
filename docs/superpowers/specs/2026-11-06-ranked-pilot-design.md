# Ranked pilot: confirmed scope and open decisions

**Status:** Updated November 7, 2026. Backend health and local browser/API foundations are complete (#2/#3 closed); competition features remain planned.

**Related:** [[2026-11-07-ranked-decision-record]], [[2026-11-06-ranked-roadmap]].

## Approved rule source

Read [[2026-11-07-ranked-decision-record]] for the current owner decisions, examples, superseded proposals and decision-status register Q1–Q13. It controls wherever older planning wording differs. Open questions/recommendations are not implementation permission. Keep #4 open until affected cases are resolved.

The repository is `renilsonjr/Sort-Tester-Live`. Continue on shared `codex/ranked-mode`; main publishes static assets through GitHub Pages, not the Python server.

## Current scope

- Preserve guest Practice/study, 15-second timer, feedback, local results and export. Login unlocks separate Ranked/Profile/leaderboard/Support flows.
- Normal Ranked: solo, 15 questions, five per difficulty, ten seconds each, server-owned assignments/deadlines and once-only settlement; immediate answer feedback.
- Easy +10/-15, Medium +20/-10, Hard +30/-5; timeout wrong. Raw regular range -150 through +300. Negative totals allowed.
- One balance, overflow discarded, perfect promotions and mandatory re-promotion after demotion. Correct promotion answers add zero; mistakes/timeouts deduct normally.

| Rank | Points / cap | Perfect promotion result |
| --- | --- | --- |
| Iron | Negative totals through 1,000 | 1,001 / Bronze |
| Bronze | 1,001–2,000 | 2,001 / Silver |
| Silver | 2,001–3,000 | 3,001 / Gold |
| Gold | 3,001–4,000 | 4,001 / Challenger |
| Challenger | 4,001 upward, uncapped | None |

- One active attempt per account, including original-session 15-second grace. Current timer continues; no unseen next question while disconnected. Grace expiry settles partial score; Quit applies a -10 adjustment before the rank cap (Q1 settled); apply the cap once to the final attempt result, never per answer (Q2 settled). Terminal attempts never resume.
- Confirmed server-wide outage voids affected normal attempts. Tie-break outage policy instead restarts the current round for all participants. No reliable intent/hardware-device detection claim.
- Case-insensitive unique usernames, permanent unique six-character uppercase letter/number tags, optional private email, no required real name/employee ID or phone collection.
- Non-punitive server connection flags, player-requested private Support → Tickets, 15-day closed descriptions/event retention, open-case/score-history preservation. Routine admins cannot change points.

## Seasons, prizes and display

Owner launches from Pre-Season on a date still undecided. Reset current points/rank/promotion to 0/Iron/none while retaining accounts/history. Official close: December 31, 2026 at 11:59 p.m., America/New_York. Existing attempts get five extra minutes, then partial settlement/freeze. Active Pre-Season attempt treatment at manual launch is Q13, still open. No January start is approved.

Three winners receive one UPS hat each. Q5 eligibility is settled: owner-approved sorters in Primary Sort on Twilight at Saddle Brook only, one fixed prize account/hat per person, owner approval before scheduled season close, and one valid completed Ranked quiz credited to the official season. Already-approved players may complete that quiz within the finishing window; negative completed scores count. Pre-Season/void/unfinished/tie-break-only histories do not qualify. Recovery keeps the same account, with no point transfer. Public identity remains username/tag.

The official competition leaderboard includes only eligible players. Ineligible accounts may still play and view their own points/badge, but have no competition position; they are not automatically deleted or blocked. Eligibility does not change points or partial-score rules.

Initial prize tie-break rounds use five shared Hard sort-work-methods questions, five seconds each, one asynchronous attempt per round, 0–5 score without changing seasonal points. First deadline: close+24 hours. Additional rounds use fresh shared sets and new 24-hour windows; at most three valid rounds for Challenger. Lower-rank prize ties use at most five valid rounds: rounds 1–3 at five seconds per question, round 4 at four seconds, and round 5 at three seconds. Each round has five shared Hard questions. Outage-voided restarts do not consume a valid round and retain its timer. If players remain tied after round five, stop automatic rounds and leave only the affected prize positions pending for the owner to decide manually among the still-tied eligible players. Preserve resolved positions and frozen seasonal points; this is prize placement, not permission to edit quiz results or points. Challenger keeps its separate three-valid-round limit and seasonal-score fallback. If a fresh shared set of five approved Hard questions is unavailable before completing five valid lower-rank rounds (including an outage restart), stop automatic rounds and leave the affected unresolved prize positions pending for the owner to select manually among the still-tied eligible players. Do not reuse questions silently, create unreviewed questions, change frozen points, or reopen resolved positions. Challenger retains its existing seasonal-score fallback. At the end of each lower-rank round’s 24-hour window, completed attempts still outrank incomplete attempts and no-shows, including a completed 0/5 result. Any prize spots still unresolved among multiple incomplete/nonparticipating lower-rank players wait for the owner to select manually among those eligible players. Preserve resolved places and frozen seasonal points; do not award automatic winners or start another quiz for that incomplete group. Challenger retains its separate seasonal-score fallback; its exact event semantics remain Q6. First-reached seasonal-score fallback applies only to tied Challenger players (4,001+), not lower badges or tie-break quiz scores; exact event semantics remain Q6. Outage-voided rounds do not count. Completed players outrank incomplete/no-shows; exact first-reached fallback semantics remain Q6. Scores, correctness, answers and review wait until the round's 24-hour window closes; show submission confirmation meanwhile. Normal Ranked keeps immediate feedback.

Leaderboard requires login and updates after settlement; provisional until final resolution. Ranked landing page hosts season notices/countdowns. Keep main-home sort-change announcements. One-time verified-email launch reminders require separate consent, cancellation and at most three send attempts within the first hour; provider details remain open.

## Foundations and release gates

Implemented: FastAPI health/CORS and local browser/API check, 10 backend tests and 23 Node cases, plus recorded Mac/Windows browser walkthroughs. These cover foundations, not competition features. There is no implemented competition database/account/Ranked/Support/email service yet.

Preferred persistence: PostgreSQL private behind the API. Candidate Windows 11 server: 16 GB RAM; target 30 simultaneous players with eventual internet access. Verify secure hosting, startup/recovery, backup/restore and load acceptance; RAM alone is not a capacity guarantee.

Use owning GitHub issues for small verified deliverables. Do not implement unanswered policy or treat additional achievements/MMR as approved.
