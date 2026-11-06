# Ranked pilot: confirmed scope and open decisions

**Status:** Planning reference from the November 5–6, 2026 discussion; implementation has not started in this checkout.

**Related:** [[2026-11-06-ranked-roadmap]].

## Intent

Expand the existing app in `renilsonjr/Sort-Tester-Live`, the repository serving the running website. The owner confirmed this as the development and issue-tracking destination. Reward points earned through performance and steady participation. This is a solo quiz competition; opponent matchmaking and hidden MMR are outside scope.

## Access and Practice

- Public entry page retains sort-change announcements and offers Log in and Continue as guest.
- Guests access current Practice and study features. Registration is not required for Practice.
- Logged-in employees access separate Practice and Ranked buttons and their profile.
- Preserve current Practice behavior: 15 seconds, existing questions/feedback, device-local log and export. Practice does not alter rank.

## Ranked attempt

- Login required; 15 randomly assigned questions, five Easy, five Medium, five Hard, shuffled.
- Individual question difficulty requires owner review; existing difficulty decks overlap and do not provide exclusive question-level labels.
- Ten seconds per question. Timeout is incorrect. Submitted answers lock; no backward navigation.
- Immediate feedback reveals the correct answer and the point change. Results support answer review.
- The backend owns assignments, deadlines, answer validation, scoring, and state. Correct answers must not be included in the unanswered ranked-question payload. Practice answers already shipped publicly are not secret.
- Repeated ranked quizzes are allowed immediately after the previous attempt ends. This supersedes the original one-attempt-per-employee-per-quiz rule. Each individual attempt is settled exactly once.

## Scores and terminal outcomes

| Difficulty | Correct | Incorrect / timeout |
| --- | ---: | ---: |
| Easy | +10 | -15 |
| Medium | +20 | -10 |
| Hard | +30 | -5 |

A complete regular quiz has a raw score between -150 and +300. Ranking adjustments also obey rank caps and promotion exceptions. Totals may become negative.

- Completed regular quiz: apply its net score subject to rank rules.
- Disconnected: end permanently and apply score earned/lost so far, subject to rank rules; no additional quitting penalty.
- Intentional Quit: end permanently and apply score so far plus a -10 penalty, subject to rank rules.
- Neither disconnected nor forfeited attempts resume. A new attempt is permitted.
- These rules supersede the earlier proposal that unfinished quizzes have no ranking impact.
- Clicking Quit is observable; browser closing or deliberately disabling internet may look like a disconnection. Do not promise reliable intent detection.

## Rank and promotion

| Rank | Point band / cap |
| --- | --- |
| Iron | All totals up to 100, including negative values |
| Bronze | 101–200 |
| Silver | 201–300 |
| Gold | 301 upward; no cap |

At the current rank cap, additional positive points cannot bypass promotion. Unlock a promotion quiz at the cap. Promotion requires 15/15 correct. Success replaces the usual +300 reward with the next rank's starting total: 101, 201, or 301. Badge follows current points; point losses can demote the employee. Regaining a lost rank requires reaching the cap and passing promotion again.

Rank is therefore not calculated from an uncapped lifetime sum. Keep raw quiz performance and actual ranking adjustments distinct in persisted history. Thresholds are initial pilot values, not a validated measure of sorting mastery.

## Accounts, administration, and history

- Self-registration with username/password, no email required; unique internal IDs; securely hashed passwords.
- Login/logout, username changes without losing progress, profile, current rank/points, and ranked history.
- Administrators create/edit/disable/delete accounts, reset passwords, and review performance/history.
- Routine administrators cannot manually change points, scoring values, or difficulty. Owner defines scoring/difficulty.
- Account deletion versus retaining audit history and password-reset identity checks need explicit decisions.
- Bronze/Silver/Gold here are current rank badges. Additional achievement badges need criteria before implementation and are outside the initial rank-badge task.

## Pilot and infrastructure

**Peak Season — Sort Test** has no fixed end date; owner decides when to stop. Reset timing and transition policy remain undecided. Preserve historical results.

Preferred backend is Python/FastAPI with PostgreSQL and REST. Candidate server: owner's old Windows 11 computer, 16 GB RAM. Target: 30 simultaneous players accessing from anywhere. Start on the local network, then verify secure public hosting, backups/restores, reliable startup, and load behavior. PostgreSQL stays private behind the API. Leaderboard follows verified scoring.

The Live repository currently contains static browser assets, with no backend, package manifest, test suite, or release-builder script. The November 4 study guide describes another backend setup that must be located or recreated. Do not represent its virtual environment or FastAPI installation as verified here.

## Decisions required before affected implementation

- Failed promotion: confirm applying the normal net score subject to the cap; a non-perfect quiz may still have a positive raw score. Confirm partial promotion forfeits/disconnections, and how -10 interacts with positive raw scores and caps.
- Confirm whether cap applies only to net settlement (recommended) rather than each individual answer; define overflow and large-loss demotion examples.
- Define promotion entry/acceptance and behavior when interrupted; next quiz automatic promotion versus explicit promotion action.
- Define deadline, feedback duration, and disconnection grace. Distinguish question timeout from abandoned attempt; define server-wide outage handling.
- Decide how multiple tabs/devices and active attempts interact. Enforce finalization once despite retries, races, or reconnects.
- Owner reviews exclusive difficulty labels, duplicate route handling, and bank changes/versioning during the pilot.
- Decide leaderboard refresh frequency (original daily requirement still open against the live-update proposal), tie policy, and employee display names.
- Decide password-reset verification, username rules, bootstrap admin, deletion/history policy, and current-session behavior after account disable.
- Decide hosting route and testable pilot acceptance criteria; do not infer capacity from RAM alone.

Record answers in the owning GitHub issue and update this reference before implementing the affected behavior.
