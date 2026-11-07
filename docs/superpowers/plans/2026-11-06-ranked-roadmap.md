# Peak Season — incremental development roadmap

**Status:** Updated November 7, 2026. Backend health and browser/API foundations are complete; competition features remain planned.

**Related:** [[2026-11-07-ranked-decision-record]], [[2026-11-06-ranked-pilot-design]].

## Start here

Use parent roadmap [#1](https://github.com/renilsonjr/Sort-Tester-Live/issues/1), then the current decision record. This is the live application repository. Shared `codex/ranked-mode` keeps reviewed development away from main; separate runtime configuration/data is still required. Main publishes static files via Pages, not the API.

Closed foundations #2/#3 include health/CORS, local Windows startup/LAN/browser checks and 10 backend/23 Node tests. They do not prove accounts, PostgreSQL persistence or Ranked rules are implemented. Do not reopen them for this planning expansion.

Issue #4 remains open. Read [[2026-11-07-ranked-decision-record]]: Q1–Q5 are settled. Q3 limits Challenger to three valid rounds, then owner selection for any remaining tie (Challenger 4,001+). Earlier fresh-question exhaustion and incomplete/no-show fallback still need Q6. Lower-rank prize ties use at most five valid rounds: rounds 1–3 at five seconds per question, round 4 at four seconds, and round 5 at three seconds. Each round has five shared Hard questions. Outage-voided restarts do not consume a valid round and retain its timer. If players remain tied after round five, stop automatic rounds and leave only the affected prize positions pending for the owner to decide manually among the still-tied eligible players. Preserve resolved positions and frozen seasonal points; this is prize placement, not permission to edit quiz results or points. Challenger keeps its separate three-valid-round limit, then owner selection for a remaining tie. Earlier Challenger fresh-question exhaustion/incomplete cases still need Q6. If a fresh shared set of five approved Hard questions is unavailable before completing five valid lower-rank rounds (including an outage restart), stop automatic rounds and leave the affected unresolved prize positions pending for the owner to select manually among the still-tied eligible players. Do not reuse questions silently, create unreviewed questions, change frozen points, or reopen resolved positions. Earlier Challenger fresh-question exhaustion still uses the prior first-reached-score proposal pending Q6; after three valid rounds use owner selection. At the end of each lower-rank round’s 24-hour window, completed attempts still outrank incomplete attempts and no-shows, including a completed 0/5 result. Any prize spots still unresolved among multiple incomplete/nonparticipating lower-rank players wait for the owner to select manually among those eligible players. Preserve resolved places and frozen seasonal points; do not award automatic winners or start another quiz for that incomplete group. Challenger uses owner selection after three valid rounds; earlier fresh-question exhaustion/incomplete cases still need Q6. Resolve remaining Q6 timing, Q7/Q13 and affected Q8 policy before implementation. Remaining Q9–Q12 decisions stay with their owning issues. Non-prize tie-position numbering remains open in #12/#16. Recommendations are not approved rules; preliminary design may label pending states, but final affected behavior waits for its decision.

## Issues and native blockers

This table records issue-completion dependencies. Work can be developed in smaller verified increments inside each issue. In particular, basic leaderboard and account work need not implement reminder delivery or Support first; final feature completion must satisfy its listed scope.

| Issue | State | Blocked by |
| --- | --- | --- |
| [#2](https://github.com/renilsonjr/Sort-Tester-Live/issues/2) · 01 · Establish the backend workspace and first health endpoint | Complete | None |
| [#3](https://github.com/renilsonjr/Sort-Tester-Live/issues/3) · 02 · Connect a development browser page to the API | Complete | None |
| [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4) · 03 · Resolve ranked attempt and promotion edge cases | Open / planned | None |
| [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5) · 04 · Review and version the ranked question bank | Open / planned | [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4) |
| [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6) · 05 · Persist users, question assignments, attempts, and ranking history | Open / planned | [#2](https://github.com/renilsonjr/Sort-Tester-Live/issues/2), [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5) |
| [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7) · 06 · Add employee registration, sessions, and account access controls | Open / planned | [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6) |
| [#8](https://github.com/renilsonjr/Sort-Tester-Live/issues/8) · 07 · Implement the server-authoritative ranked attempt engine | Open / planned | [#3](https://github.com/renilsonjr/Sort-Tester-Live/issues/3), [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5), [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6), [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7) |
| [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9) · 08 · Apply ranked scores, caps, promotions, and demotions exactly once | Open / planned | [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#8](https://github.com/renilsonjr/Sort-Tester-Live/issues/8) |
| [#10](https://github.com/renilsonjr/Sort-Tester-Live/issues/10) · 09 · Build public entry, separate modes, and the employee profile | Open / planned | [#3](https://github.com/renilsonjr/Sort-Tester-Live/issues/3), [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7), [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9), [#15](https://github.com/renilsonjr/Sort-Tester-Live/issues/15), [#16](https://github.com/renilsonjr/Sort-Tester-Live/issues/16), [#17](https://github.com/renilsonjr/Sort-Tester-Live/issues/17), [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23), [#26](https://github.com/renilsonjr/Sort-Tester-Live/issues/26) |
| [#11](https://github.com/renilsonjr/Sort-Tester-Live/issues/11) · 10 · Add administrator account management and performance review | Open / planned | [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7), [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9), [#25](https://github.com/renilsonjr/Sort-Tester-Live/issues/25), [#26](https://github.com/renilsonjr/Sort-Tester-Live/issues/26) |
| [#12](https://github.com/renilsonjr/Sort-Tester-Live/issues/12) · 11 · Display leaderboard totals and current rank badges | Open / planned | [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9), [#10](https://github.com/renilsonjr/Sort-Tester-Live/issues/10), [#16](https://github.com/renilsonjr/Sort-Tester-Live/issues/16), [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23), [#24](https://github.com/renilsonjr/Sort-Tester-Live/issues/24) |
| [#13](https://github.com/renilsonjr/Sort-Tester-Live/issues/13) · 12 · Validate the Windows server and prepare the 30-player pilot | Open / planned | [#10](https://github.com/renilsonjr/Sort-Tester-Live/issues/10), [#11](https://github.com/renilsonjr/Sort-Tester-Live/issues/11), [#12](https://github.com/renilsonjr/Sort-Tester-Live/issues/12), [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23), [#24](https://github.com/renilsonjr/Sort-Tester-Live/issues/24), [#25](https://github.com/renilsonjr/Sort-Tester-Live/issues/25), [#26](https://github.com/renilsonjr/Sort-Tester-Live/issues/26), [#27](https://github.com/renilsonjr/Sort-Tester-Live/issues/27) |
| [#15](https://github.com/renilsonjr/Sort-Tester-Live/issues/15) · Design · Mock public entry, mode navigation, and shared visual style | Open / planned | None |
| [#16](https://github.com/renilsonjr/Sort-Tester-Live/issues/16) · Design · Mock employee profile and leaderboard views | Open / planned | [#15](https://github.com/renilsonjr/Sort-Tester-Live/issues/15), [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4) |
| [#17](https://github.com/renilsonjr/Sort-Tester-Live/issues/17) · Design · Mock Ranked questions, promotion, feedback, and results | Open / planned | [#15](https://github.com/renilsonjr/Sort-Tester-Live/issues/15), [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4) |
| [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23) · Season launch, reset, closing and final settlement | Open / planned | [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6), [#8](https://github.com/renilsonjr/Sort-Tester-Live/issues/8), [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9) |
| [#24](https://github.com/renilsonjr/Sort-Tester-Live/issues/24) · Prize tie-break quizzes and 24-hour rounds | Open / planned | [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5), [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6), [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7), [#8](https://github.com/renilsonjr/Sort-Tester-Live/issues/8), [#9](https://github.com/renilsonjr/Sort-Tester-Live/issues/9), [#17](https://github.com/renilsonjr/Sort-Tester-Live/issues/17), [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23) |
| [#25](https://github.com/renilsonjr/Sort-Tester-Live/issues/25) · Server connection events and non-punitive flags | Open / planned | [#4](https://github.com/renilsonjr/Sort-Tester-Live/issues/4), [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6), [#8](https://github.com/renilsonjr/Sort-Tester-Live/issues/8) |
| [#26](https://github.com/renilsonjr/Sort-Tester-Live/issues/26) · Player Support tickets and 15-day closed retention | Open / planned | [#6](https://github.com/renilsonjr/Sort-Tester-Live/issues/6), [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7), [#25](https://github.com/renilsonjr/Sort-Tester-Live/issues/25), [#15](https://github.com/renilsonjr/Sort-Tester-Live/issues/15), [#16](https://github.com/renilsonjr/Sort-Tester-Live/issues/16) |
| [#27](https://github.com/renilsonjr/Sort-Tester-Live/issues/27) · Verified opt-in launch reminder delivery and retries | Open / planned | [#7](https://github.com/renilsonjr/Sort-Tester-Live/issues/7), [#10](https://github.com/renilsonjr/Sort-Tester-Live/issues/10), [#23](https://github.com/renilsonjr/Sort-Tester-Live/issues/23) |

## Build sequence

1. Record settled rules and resolve required open cases in #4; review question labels/versions and Hard work-methods content in #5. Shared navigation design #15 can proceed with fictional data.
2. Implement/test core persistence #6, account/security/email verification contracts #7, attempt engine #8 and scoring #9. Feature-specific migrations follow their own issues; do not put all future features into the first migration.
3. Add season orchestration #23 and connection events/flags #25 using core contracts. Finalize profile/Ranked/tie-break designs #16/#17 from approved policy.
4. Integrate reviewed entry/profile/season UI #10; player Support #26 and administrative account/incident tools #11 are separately verified increments.
5. Implement prize tie-break rounds #24 and final leaderboard integration #12. Basic standings can be tested earlier, but final prizes need both lifecycle and tie-break outcomes.
6. Deliver launch reminders #27 using verified-email/consent and season contracts. Provider and uncertain-delivery handling remain explicit decisions. Any launch-scope deferral needs owner approval.
7. Complete hosting/recovery/backup/access and 30-player validation in #13 before employee rollout; public publication is a separate reviewed step.

## Dependency boundaries

```mermaid
flowchart TD
  R[4: Rule decisions] --> Q[5: Question banks]
  Q --> D[6: Core database]
  D --> A[7: Accounts and verification]
  A --> E[8: Ranked attempt engine]
  E --> S[9: Scoring]
  S --> L[23: Season lifecycle]
  E --> C[25: Connection events]
  C --> T[26: Player Support]
  T --> M[11: Admin incident review]
  L --> U[10: Reviewed entry/profile/season UI]
  L --> B[24: Prize tie-breaks]
  Q --> B
  B --> K[12: Final standings]
  U --> K
  U --> N[27: Launch reminders]
  L --> N
  K --> P[13: Pilot validation]
  M --> P
  N --> P
```

The table/native relationships are the complete dependency list; the diagram is a simplified overview. Later orchestration consumes core contracts and must not become a prerequisite of those same core contracts.

## Work and verification rules

- Explain the next small change before editing existing files. Keep the owner's learning pace and use one focused decision question at a time.
- Use [[2026-11-07-ranked-decision-record]] as the settled source; preserve its Q1–Q13 register and explicit superseded proposals.
- Preserve current guest Practice, timing, local results and export. No routine administrator point editing, hidden MMR, extra achievements or separate points balance.
- Use reviewed fictional-data mockups in #15/#16/#17; do not implement visual assumptions as if approved.
- Test meaningful normal/failure/race/boundary cases and record exactly what ran on Mac, Windows, browser and hosted CI. Do not call a future rule implemented because foundation tests pass.
- Close only issues whose acceptance checks pass. Keep raw quiz performance and applied rank adjustments auditable, protect private contacts/Support data, and enforce authorization server-side.
- Official launch date is unknown; close is December 31, 2026 at 11:59 p.m. America/New_York. No January start is authorized. The Windows 11/16 GB server is a candidate, not a 30-player capacity guarantee.
