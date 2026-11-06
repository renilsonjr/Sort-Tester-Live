# Sort Tester Live / Sort Lab

Phone-friendly sorting practice for UPS Saddle Brook Twilight routes. The current app includes a searchable study chart, timed multiple-choice quizzes, English/Spanish text, a device-local shift log, and Excel export.

This is an independent training aid. Verify routes against the current approved sort chart.

**Live website:** [Sort Tester Live](https://renilsonjr.github.io/Sort-Tester-Live/).

## Current status

This is the repository serving the running application and the owner's chosen home for future development and issue tracking. The current app is static HTML, CSS, and browser JavaScript. There is no account server or central database. Results stay in this browser on this device; they do not synchronize between employees or phones.

Accounts, PostgreSQL, Ranked Mode, promotions, profiles, and the leaderboard are **planned work**, not existing features. Develop the expansion on a dedicated branch in this repository.

## Run locally

Install Git and Python 3, then clone the repository:

```sh
git clone https://github.com/renilsonjr/Sort-Tester-Live.git
cd Sort-Tester-Live
```

On macOS/Linux:

```sh
python3 -m http.server 8000 --bind 127.0.0.1
```

On Windows, with the Python launcher installed:

```powershell
py -3 -m http.server 8000 --bind 127.0.0.1
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000). Stop the server with Ctrl+C. Use HTTP rather than opening the HTML file directly because the app uses JavaScript modules. This local static server is for development; it is not the future FastAPI backend.

No npm installation or build step is needed for the current static app. Excel export uses an externally loaded spreadsheet library and requires that library to load successfully.

## Check the current app

The repository has a focused security regression check. With Node.js installed, run:

```sh
node --test tests/security.test.mjs
```

This checks saved-score and name rendering with passive markup probes. It is not a full browser or quiz regression suite. There is still no package manifest or release-builder script; broader checks belong to the backend foundation issue.

GitHub Actions runs these checks on every pull request and on main-branch updates. See [PR checks and branch protection](docs/security/branch-protection.md) for the proposed protection settings and when to make the check required.

For a manual check, open the local app, search the study chart, complete a Practice quiz, check feedback and the 15-second timer, reload the shift log, and export a workbook. Test English and Spanish, cancellation, and a narrow phone screen. Local test results remain in that browser's storage until cleared.

## Development and publishing

GitHub Pages currently serves the root of the `main` branch. A push to a feature branch does not publish that branch. Review and verify changes before merging to `main`, because that merge updates the website. A new backend will need its own hosting; GitHub Pages serves static files.

The current practice questions and answers are browser-visible. Do not place passwords, database credentials, employee records, or private reference documents in this public repository or in browser assets. Future ranked answers and point adjustments must be validated by the backend.

## Planned employee flow

The public home page retains sort-change announcements and offers **Log in** or **Continue as guest**. Guests retain current Practice and study features. Logged-in employees get separate Practice and Ranked flows plus their profile. Practice retains its existing 15-second timer and local results. Ranked uses employee accounts, a server, 15 questions, and 10 seconds per question.

The first pilot is **Peak Season — Sort Test**, ending when the owner decides. Candidate hosting is a Windows 11 computer with 16 GB RAM. The target is 30 simultaneous players; suitability must be demonstrated through testing before employee rollout.

## Build roadmap

Read the [ordered issue roadmap](docs/superpowers/plans/2026-11-06-ranked-roadmap.md) and [ranked pilot rules](docs/superpowers/specs/2026-11-06-ranked-pilot-design.md). Issues contain small deliverables, owner decisions, acceptance checks, and blocking dependencies. The leaderboard comes after verified scoring.

## Repository guide

| Location | Responsibility |
| --- | --- |
| `index.html` | App shell and styles |
| `src/app.js` | Browser screens and interactions |
| `src/quiz.js`, `src/clock.js` | Existing Practice run and timing logic |
| `src/questions.js`, `src/decks.js`, `src/levels.js` | Practice content and selection |
| `src/chart.js`, `src/study.js` | Study chart and search |
| `src/shiftLog.js`, `src/exportFile.js` | Local results and export |
| `assets/`, `mockups/` | Browser assets and existing preview |
| `docs/` | New planning references |

## Working agreements

Make one small change, explain it, run it, and verify the result before continuing. Tell the owner before changing an existing file. Keep future development and pilot databases separate. Resolve open product decisions in their owning issue rather than silently choosing behavior while coding.

Local environments, credentials, databases, backups, and employee exports are excluded by `.gitignore`. Ignore rules do not remove files already committed or make a public Pages file private. See the [scoped security review](docs/security/2026-11-06-static-review.md) for checks, fixes, and remaining limits.
