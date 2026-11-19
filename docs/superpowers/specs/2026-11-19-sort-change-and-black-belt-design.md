# SORT CHANGE edits + BLACK belt — Design

**Date:** 2026-11-19
**Status:** Owner-approved (scope + before→after confirmed 2026-11-19)
**Base branch:** `codex/ranked-mode`

## Goal

Apply the four routing edits from the owner's "SORT CHANGE" note (photos
IMG_2400 / IMG_2401) to the Ranked chart, and introduce a new belt colour,
**BLACK**. Scope is **only** these four edits plus BLACK — not a full
re-reconciliation of the whole chart against the new reference sheet.

## Source material

- **IMG_2400 "SORT CHANGE"** — the four edits to apply.
- **IMG_2401 "SADDLE BROOK TWILIGHT PRIMARY SORT CHART"** — the full
  reference sheet, used here only to disambiguate the four edits (not
  re-imported).

## The four edits (owner-confirmed before→after)

Against the current bank (`routes-v1.json`, revision `ranked-routes-v1`,
283 questions, 9 belts, no BLACK):

### 1 + 2 · TX — Ground and 3 Day Select
| Service | Range | Now | After |
|---|---|---|---|
| Ground (GND) | 750–779 | BLUE | **BLACK** (recolour whole range) |
| 3 Day Select (3DS) | 770–784 | BLUE | **split:** 770–779 **BLACK** + 780–784 BLUE |

- GND 750-769 and 770-779 both become BLACK → net is recolouring the
  existing GND `750–779` range.
- 3DS changes only `770–779`. Untouched on 3DS: `750–768` BLUE, the
  `769 0` PURPLE qualified-code exception, `785–799` PURPLE, and the
  `786 4 / 787 9 / 796 0 / 799 9` ORANGE exceptions.

### 3 · IL — 2 Day Air only
| Service | Range | Now | After |
|---|---|---|---|
| 2 Day Air (2DA) | 600–608 | YELLOW | **600–619 PURPLE** |
| 2 Day Air (2DA) | 609–629 | ORANGE | **split:** 609–619 **PURPLE** + 620–629 ORANGE |

- Net result: 2DA IL `600–619` PURPLE + `620–629` ORANGE.
- Ground and 3 Day Select for IL are **unchanged**.

### 4 · NY — Ground, 3 Day Select, 2 Day Air
| Service | Range | Now | After |
|---|---|---|---|
| 2 Day Air | 140–147 | ORANGE | **GOLD** |
| 3 Day Select | 140–147 | ORANGE | **GOLD** |
| Ground | 140–147 | GOLD | — (already GOLD, no-op) |

- Untouched: `NDA 140–149` PURPLE, and the `148 1` GOLD / `148–149`
  ORANGE rows across services.

### New belt: BLACK
Introduced by edits 1 and 2 (TX GND `750–779`, TX 3DS `770–779`). BLACK is
a real answer belt and must be registered everywhere a belt is enumerated.

## Architecture / where the data lives

The chart is represented in **three places that must stay in sync**, and
the test suite enforces the match:

1. **Backend bank** — authored through the review source
   `docs/superpowers/specs/2026-11-08-ranked-full-chart-review.json`
   (`entries`), lowered by `tools/export_ranked_v1.py` into
   `backend/data/ranked/routes-v1.json` with `backend/data/ranked/manifest.json`
   holding its `sha256`. `canonical_id`s embed a content hash, so the file
   is **never hand-edited** — edits go in the review source and the export
   tool regenerates. The loader (`backend/ranked_bank/loading.py`) refuses
   a file whose digest does not match the manifest.
2. **Frontend chart** — `src/chart.js` exports `CHART[service][kind]`, a
   parallel copy used by the Sort Lab UI.
3. **Reference fixture** — `tests/fixtures/twilight-reference-2026-11-08.json`
   (`cases`), the matrix that `tests/chart-reference.test.mjs` checks
   **both** the frontend `CHART` and (indirectly) the bank against.

### Belt registries that gate BLACK
- **Backend allowlist** — `backend/ranked_bank/loading.py` rejects any
  `correct_belt` not in a fixed tuple. BLACK must be added there or the
  regenerated bank fails to load.
- **Frontend** — `src/belts.js` `BELTS` array and `BELT_STYLE` map. BLACK
  needs an entry in both; the chip colour must stay legible on the dark
  "twilight glass" surface (pure `#000` disappears into it).

## Belt-chip colour for BLACK

`BELT_STYLE` on dark glass already uses `CHECK: #333333`. BLACK must read
as darker-than-CHECK yet remain visible: a near-black fill with a thin
light border. Proposed: `{ bg: '#141414', fg: '#ffffff', border: '#5a5a5a' }`
(exact token finalised in the plan; if `BELT_STYLE` has no border field
today, the chip CSS adds a 1px outline for BLACK only, or a slightly
lighter fill is used). The point: a BLACK chip must be distinguishable
from the glass background and from CHECK.

## "Previous bank with the image" — removal

The owner asked that the previous (photo-sourced) bank be removed "so it
doesn't cause confusion", scoped to **only the routes these edits
replace**.

- Regenerating `routes-v1.json` **replaces** the affected TX/IL/NY rows
  in place; the old belts/ranges are no longer offered by the runtime
  bank or the frontend. That is the substantive "removal".
- `question_versions` (Postgres) is **immutable play-history**: rows are
  materialised on use (`backend/ranked/versions.py`) and referenced by
  `attempt_answers`. Rows tied to real attempts **must not** be deleted.
  Because a changed route gets a new `content_sha256`, the new wording is
  a *new* row; the old row simply stops being produced. In pre-season,
  with no qualifying historical attempts on these routes, any orphaned old
  rows may be pruned, but this is optional and must be guarded by a
  "not referenced by any attempt_answer" check. No schema change.

## Out of scope
- Re-reconciling the rest of the chart against IMG_2401.
- Any change to scoring, difficulty weights, or season logic.
- Deleting `question_versions` rows referenced by real attempts.
- Azure / deployment changes.

## Testing strategy
- Backend: `backend.ci_tests` full suite green; bank loads with BLACK;
  coverage/belt checks updated for the new belt and the changed routes.
- Frontend: `node --test tests/*.test.mjs`, especially
  `tests/chart-reference.test.mjs`, which pins every reference case and
  forbids unreviewed rows — so the fixture, `src/chart.js`, and the bank
  must agree exactly.
- The reference fixture's `cases` and `sourceSha256` are updated to match
  the regenerated review/bank.

## Acceptance
- The four edits are reflected identically in the bank, `src/chart.js`,
  and the fixture.
- BLACK is a valid belt end-to-end (backend allowlist, frontend registry,
  visible chip) and is the correct answer for TX GND `750–779` and TX 3DS
  `770–779`.
- No stale pre-edit belts remain for the four edited routes anywhere.
- Full backend and frontend suites pass.
