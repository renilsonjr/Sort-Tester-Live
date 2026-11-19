# SORT CHANGE edits + BLACK belt — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the four "SORT CHANGE" routing edits and introduce the BLACK belt, keeping the backend bank, the frontend `src/chart.js`, and the reference fixture in exact sync.

**Architecture:** The chart is authored in a review source JSON and lowered to `routes-v1.json` by `tools/export_ranked_v1.py` (never hand-edit the artifact); the frontend keeps a parallel `CHART`; a fixture matrix pins both. BLACK must be registered in the backend belt allowlist and the frontend belt registry before the bank that uses it will load or render.

**Tech Stack:** Python 3.14 (backend, Alembic, psycopg), Node `--test` (frontend), JSON data artifacts.

**Design:** `docs/superpowers/specs/2026-11-19-sort-change-and-black-belt-design.md`

## Global Constraints

- Never hand-edit `backend/data/ranked/routes-v1.json` or `manifest.json`; regenerate via the export tool. (`canonical_id`/`sha256` are content hashes.)
- BLACK must be added to BOTH the backend allowlist (`backend/ranked_bank/loading.py`) and the frontend registry (`src/belts.js`: `BELTS` + `BELT_STYLE`).
- The BLACK chip must be legible on dark twilight glass and distinct from `CHECK (#333333)`.
- `question_versions` rows referenced by any `attempt_answers` must NOT be deleted. No schema change, no migration.
- Keep three representations in sync: bank (`routes-v1.json`), `src/chart.js` `CHART`, fixture `cases`. `tests/chart-reference.test.mjs` enforces this.
- No Azure / deployment change.

## Before→after (authoritative, owner-confirmed)

- TX Ground `750–779` BLUE → **BLACK**.
- TX 3 Day Select `770–784` BLUE → **`770–779` BLACK + `780–784` BLUE** (split).
- IL 2 Day Air `600–608` YELLOW + `609–629` ORANGE → **`600–619` PURPLE + `620–629` ORANGE**.
- NY 2 Day Air `140–147` ORANGE → **GOLD**; NY 3 Day Select `140–147` ORANGE → **GOLD**. (NY Ground `140–147` is already GOLD — no change.)
- Untouched everywhere: NDA rows, `769 0` / `785–799` / `786 4` / `787 9` / `796 0` / `799 9` on TX 3DS, `148 1` / `148–149` on NY.

## File Structure

- `backend/ranked_bank/loading.py` — add BLACK to the `correct_belt` allowlist.
- `src/belts.js` — add BLACK to `BELTS` and `BELT_STYLE`.
- `docs/superpowers/specs/2026-11-08-ranked-full-chart-review.json` — the review source; edit/add the affected `entries`.
- `backend/data/ranked/routes-v1.json`, `backend/data/ranked/manifest.json` — regenerated (not hand-edited).
- `src/chart.js` — update `CHART` rows for the affected routes.
- `tests/fixtures/twilight-reference-2026-11-08.json` — update `cases` + `sourceSha256`.
- Tests: `backend/tests/test_ranked_loading.py`, `backend/ranked_bank/coverage.py`/`check.py` call sites, `tests/chart-reference.test.mjs`.

---

### Task 1: Register BLACK as a valid belt

**Files:**
- Modify: `backend/ranked_bank/loading.py` (the allowlist tuple on the `correct_belt` check)
- Modify: `src/belts.js` (`BELTS`, `BELT_STYLE`)
- Test: `backend/tests/test_ranked_loading.py`; a frontend assertion in `tests/chart-reference.test.mjs` or a small new `tests/belts-black.test.mjs`

**Interfaces:**
- Produces: BLACK accepted by `load_bank`; `BELT_STYLE.BLACK` exists with `bg`/`fg`.

- [ ] **Step 1: Failing backend test** — in `test_ranked_loading.py`, build the smallest valid bank dict (copy an existing test fixture builder) with one question whose `correct_belt` is `"BLACK"`, recompute its digest, and assert `load_bank` returns it without raising. Run: expect FAIL (`unknown belt`).
- [ ] **Step 2: Add BLACK to the allowlist** in `backend/ranked_bank/loading.py` — extend the tuple to include `'BLACK'`. Run the test: expect PASS.
- [ ] **Step 3: Failing frontend test** — assert `BELT_STYLE.BLACK` is defined and `BELTS` includes `'BLACK'`. Run `node --test`: expect FAIL.
- [ ] **Step 4: Add BLACK to `src/belts.js`** — add `'BLACK'` to `BELTS` and a `BELT_STYLE.BLACK` entry legible on dark glass and distinct from CHECK (e.g. `{ bg: '#141414', fg: '#ffffff' }`, plus a 1px light outline for the BLACK chip in the chip CSS if needed for visibility). Run `node --test`: expect PASS.
- [ ] **Step 5: Commit** — `feat(chart): register BLACK as a belt (allowlist + chip)`.

### Task 2: Author the four edits in the review source

**Files:**
- Modify: `docs/superpowers/specs/2026-11-08-ranked-full-chart-review.json` (`entries`)
- Test: a scratch assertion script (see Step 2) — not committed

Mirror the existing entry shape exactly (fields: `id, service, kind, state, code, expectedBelt, provenance, destinationModifier, difficulty, difficultyStatus, approvedReview, difficultyReason, wordingStatus, canonicalStatus, reviewNotes, wording{en,es}`). Service labels are `"Ground"`, `"3 Day Select"`, `"2 Day Air"`. Use fresh provenance tags `owner-override-10` … for edited/added entries. Update each edited/added entry's `wording.en/es.explanation` so the belt named in the text matches the new belt.

- [ ] **Step 1: Edit the belts/ranges** in the review `entries`:
  - TX Ground `750–779`: `expectedBelt` → `BLACK`.
  - TX 3 Day Select `770–784`: change its `code` to `770–779` and `expectedBelt` → `BLACK`; **add** a new entry TX 3 Day Select `780–784` `BLUE`.
  - IL 2 Day Air `600–608`: change `code` to `600–619`, `expectedBelt` → `PURPLE`; change the `609–629` entry's `code` to `620–629` (keep `ORANGE`).
  - NY 2 Day Air `140–147`: `expectedBelt` → `GOLD`.
  - NY 3 Day Select `140–147`: `expectedBelt` → `GOLD`.
  - Each touched entry: `provenance` → `owner-override-10`, and refresh `wording.*.explanation` to the new belt.
- [ ] **Step 2: Verify the source** — scratch script: load the JSON and assert the five target entries have the expected `code`/`expectedBelt`, and that the new `780–784 BLUE` and `620–629 ORANGE` entries exist. Expect PASS.
- [ ] **Step 3: Commit** — `data(chart): author SORT CHANGE edits in review source`.

### Task 3: Regenerate the bank artifact

**Files:**
- Regenerate: `backend/data/ranked/routes-v1.json`, `backend/data/ranked/manifest.json`
- Possibly modify: `tools/export_ranked_v1.py` ONLY if it carries a hardcoded question count/belt set that the edits trip

- [ ] **Step 1: Run the export tool** — `backend/.venv/bin/python -m tools.export_ranked_v1` (confirm the exact entrypoint/args from the tool's `argparse`). It must rewrite `routes-v1.json` and update the manifest `sha256`.
- [ ] **Step 2: If the tool raises** on a hardcoded count/belt assumption, update that specific assumption (e.g. an expected question count) to reflect the two added entries — do not loosen validation. Re-run until it exports.
- [ ] **Step 3: Verify the bank loads** — `python -c` calling `backend.ranked_bank.catalog.load_reviewed_bank()`; assert it returns, that `all_belts` now includes `BLACK`, and that the five affected routes carry the new belts/ranges.
- [ ] **Step 4: Confirm no stale belts** — assert the bank has no TX GND `750–779` BLUE, no TX 3DS `770–779` BLUE, no IL 2DA `600–608` YELLOW / `609–629` ORANGE, no NY 2DA/3DS `140–147` ORANGE.
- [ ] **Step 5: Commit** — `data(chart): regenerate routes-v1 bank with SORT CHANGE edits + BLACK`.

### Task 4: Update the frontend CHART

**Files:**
- Modify: `src/chart.js` (`CHART`)

- [ ] **Step 1: Edit `CHART` rows** to match the before→after exactly: TX Ground `750–779`→BLACK; TX 3 Day Select `770–784`→`770–779` BLACK + `780–784` BLUE; IL 2 Day Air `600–608`+`609–629`→`600–619` PURPLE + `620–629` ORANGE; NY 2 Day Air `140–147`→GOLD; NY 3 Day Select `140–147`→GOLD. Match the exact en-dash/code spelling used in `src/chart.js`.
- [ ] **Step 2: Commit** — `feat(chart): apply SORT CHANGE edits to the frontend chart`.

### Task 5: Update the reference fixture

**Files:**
- Modify: `tests/fixtures/twilight-reference-2026-11-08.json` (`cases`, `sourceSha256`)
- Test: `tests/chart-reference.test.mjs`

- [ ] **Step 1: Update `cases`** for the affected routes to the new belts/ranges (add the split rows `780–784 BLUE`, `620–629 ORANGE`; change the recoloured/merged rows). Keep every other case untouched.
- [ ] **Step 2: Update `sourceSha256`** to the digest the fixture pins (recompute from the regenerated review/bank source it references — confirm which file `source`/`sourceSha256` points at and hash that).
- [ ] **Step 3: Run `node --test tests/chart-reference.test.mjs`** — expect PASS (frontend `CHART` ↔ fixture agree, no unreviewed rows). Fix mismatches in `src/chart.js` or `cases` until green.
- [ ] **Step 4: Commit** — `test(chart): update reference fixture for SORT CHANGE + BLACK`.

### Task 6: Update backend belt/coverage tests and run full suites

**Files:**
- Modify: whichever tests assert the belt set or the affected routes (`backend/tests/test_ranked_loading.py`, coverage/`check.py`-driven tests, `backend/tests/test_ranked_data.py`, etc.)
- Test: full backend + frontend suites

- [ ] **Step 1: Run the full backend suite** — `backend/.venv/bin/python -m backend.ci_tests` (with a loopback Postgres per the CI job). Note every failure caused by the belt-set change (9→10) or the four routes.
- [ ] **Step 2: Update those assertions** to the new expected belts/counts — tightening to the true new values, never deleting a check. Re-run until green.
- [ ] **Step 3: Run the frontend suite** — `node --test tests/*.test.mjs`: expect all PASS.
- [ ] **Step 4: Commit** — `test(chart): reconcile belt/coverage expectations with BLACK`.

### Task 7: "Previous bank" cleanup — verify, prune only if safe

**Files:**
- Read-only verification; optional guarded data step (no migration)

- [ ] **Step 1: Confirm the artifact removal is complete** — the regenerated bank and `src/chart.js` and fixture all agree and carry no pre-edit belt for the four routes (re-assert from Task 3 Step 4 across all three sources).
- [ ] **Step 2: Check `question_versions` exposure** — query whether any `attempt_answers` row references a `question_versions` row for the edited routes. If yes, STOP: those rows are immutable history and stay. If zero (expected in pre-season), the old materialised rows are orphaned and MAY be pruned.
- [ ] **Step 3: Prune only if zero references** — if and only if Step 2 found no references, delete the orphaned pre-edit `question_versions` rows for these routes (guarded `DELETE ... WHERE NOT EXISTS (SELECT 1 FROM attempt_answers ...)`); otherwise record "no prune — pre-season had none / history present" and move on. No schema change.
- [ ] **Step 4: Commit** (if anything changed) — `chore(chart): retire orphaned pre-edit question_versions`.

## Self-Review notes
- Spec coverage: four edits (Tasks 2–5), BLACK registration (Task 1), three-way sync (Tasks 3–5), removal (Task 7) — all mapped.
- The one unknown that execution must resolve live: whether `tools/export_ranked_v1.py` has a hardcoded count/belt set (Task 3 Step 2) and exactly which file `sourceSha256` pins (Task 5 Step 2). Both are verify-and-adjust, not guesses baked into data.
