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

Three winners, one UPS hat each, restricted to sorters in Primary Sort on the Twilight shift at Saddle Brook (prize scope only; registration/play restrictions are not decided by this rule). Each sorter may have only one prize-eligible account and win at most one hat; this does not automatically delete/block other accounts. The owner privately confirms each sorter and approves their chosen prize account; public profiles stay username/tag, with no public real name/employee ID. After approval the prize account stays fixed for that official season; recovery uses the same account without point transfer. Approval deadline remains open in Q5. Approval does not replace the quiz minimum, change points or block play. Prize ties use five Hard sort-work-methods questions, five seconds each, one asynchronous attempt per round, score 0–5 without changing seasonal points. First deadline: close+24 hours. Additional rounds: fresh shared question sets and new 24-hour windows, with at most three valid rounds including the first. Remaining ties after round three, or unavailable fresh questions, use the first-reached-score fallback; outage-voided rounds do not count toward the limit (Q3 settled). Completed players outrank incomplete/no-shows; fallback for all incomplete/no-show attempts, with remaining eligibility and exact event definition still governed by Q5/Q6. Prize participation requires one valid completed Ranked quiz credited to the official season, including its approved finishing window; negative completed scores qualify, but unused accounts and Pre-Season/void/incomplete/tie-break attempts alone do not. This does not change point totals or partial-score rules. Tie-break scores, correct answers, correctness and detailed review stay hidden until the round's 24-hour window closes; show submission confirmation beforehand (Q4 settled). Normal Ranked keeps immediate feedback.

Leaderboard requires login and updates after settlement; provisional until final resolution. Ranked landing page hosts season notices/countdowns. Keep main-home sort-change announcements. One-time verified-email launch reminders require separate consent, cancellation and at most three send attempts within the first hour; provider details remain open.

## Foundations and release gates

Implemented: FastAPI health/CORS and local browser/API check, 10 backend tests and 23 Node cases, plus recorded Mac/Windows browser walkthroughs. These cover foundations, not competition features. There is no implemented competition database/account/Ranked/Support/email service yet.

Preferred persistence: PostgreSQL private behind the API. Candidate Windows 11 server: 16 GB RAM; target 30 simultaneous players with eventual internet access. Verify secure hosting, startup/recovery, backup/restore and load acceptance; RAM alone is not a capacity guarantee.

Use owning GitHub issues for small verified deliverables. Do not implement unanswered policy or treat additional achievements/MMR as approved.
