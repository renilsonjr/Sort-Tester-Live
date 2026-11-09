# Curated Ranked bank — implementation verification

**Status:** implementation completed on shared `codex/ranked-mode`, through `d01cd3c`, after owner plan approval. Five separate task reviews and the final whole-branch review approved, with no outstanding findings. Exact-head hosted results are tracked in [PR32](https://github.com/renilsonjr/Sort-Tester-Live/pull/32). Owner manual Windows verification remains pending. This note does not claim a merge or deployment.

**Related:** [[2026-11-08-curated-ranked-bank]], [[2026-11-08-curated-ranked-bank-design]], [[2026-11-08-ranked-full-chart-review]], [[2026-11-08-ranked-question-wording-review]]. Tracker: [Issue5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

## Implemented scope

- Immutable typed models and strict pinned JSON loading; aliases/languages/examples do not create extra canonical slots.
- Effective coverage and fixed-example validation, exact literal exceptions across printed state labels, separate ordinary/+1/EAM/suffix contexts.
- Reproducible authoring export and versioned artifact:283 distinct IDs,103 Easy /127 Medium /53 Hard. Original17 bilingual records, expanded266 copies and all20 approved display examples are preserved. Four CHECK rows remain held. Typed totals:174 prefix ranges,85 qualified codes,6 exact literals,8 suffixes,5 named destinations,5 any-route qualifier rules.
- Immutable revision catalog checks content reuse against all retained manifest versions.
- Complete randomized compatibility search, exactly5 questions per difficulty, internal immutable snapshots and defensive serialization. Read-only CLI prints counts/references, never an answer key.

Bank revision: `ranked-routes-v1`. Source: `twilight-2026-11-08-r2`. Canonical bank digest: `12ebcf08bd5236f13e14b491cd2d103c151204a794bd527565e961dab332a2c3`.

## Fresh controller verification

At `d01cd3c`, from the Live repository root:

- `backend/.venv/bin/python -m unittest discover -s backend/tests -v`:78 tests,OK.
- `node --test tests/*.test.mjs`:386 passed,0 failed.
- `backend/.venv/bin/python -m pip check`:no broken requirements.
- `backend/.venv/bin/python -m backend.ranked_bank.check --revision ranked-routes-v1 --seed 42`:15 questions,Easy5/Medium5/Hard5.
- `git diff --check`:clean; working tree clean before this documentation update.

Seed42 ordered references: `S73,D16,S11,E1,G01,G62,G34,G71,H3,N43,D02,S19,D50,N06,H6`.

The tests exercise malformed schema/Unicode, alias duplicates, pin/revision failures, immutable records, exact exceptions/marker conflicts, source/copy preservation, reproducible export, filename/cwd portability, incompatible pools and the greedy-choice trap. Real-bank selection is checked over50 deterministic seeds. No browser or live-game behavior follows from these backend checks.

## Windows CI newline correction

Hosted Windows run `42549747930` at `64cf503` ran78 backend tests:77 passed and `test_published_artifact_equals_fresh_export` failed because Git checked out the published JSON with CRLF while the fresh exporter wrote LF. This was a test comparison portability defect; the canonical pin was unaffected.

The local follow-up changes only the published/export comparison to normalize CRLF to LF, preserving all other bytes. A simulated CRLF checkout regression failed before the fix and passed afterward; the same regression confirms additional non-newline bytes still fail. Repeated fresh exports remain compared byte-for-byte. Production artifacts, pins, content, versions, schema and workflow were unchanged.

At the local follow-up tree based on `64cf503`, `backend/.venv/bin/python -m unittest discover -s backend/tests -v` passed79 tests; `git diff --check` passed. These results describe the local fix tree, not a hosted result for its new commit. Controller verification of the new exact head on hosted Windows remains pending.

## Review corrections

Separate task reviews caught and verified fixes for lone-surrogate error handling, excluded-only presentations, unsupported combined markers, and locale-dependent Unicode test I/O. Artifact bytes were unchanged by those fixes. Integration also added the source alias “2 Day Air” alongside “2nd day air”. Task commits: `16f2c86`,`8351538`,`65bba3a`,`c539522`,`b083b4d`,`1e8002f`,`2c5f0fb`,`d01cd3c`.

## Remaining gates

- Run the documented commands on the owner’s Windows computer and compare seed42 output. Hosted Windows CI is separate evidence, not this physical-machine check.
- Later Issue6/engine work must persist immutable assignments and consume selection before creating an attempt/score; no transaction/restart guarantee is implemented here.
- Only the separate sort-work-methods tie content remains deferred; normal route content does not silently replace it. Other tie policies remain unchanged.
- No new API, auth, database, timer, scoring, frontend screen or public deployment is added by this implementation. The earlier Indiana Practice correction remains part of PR32 and awaits owner merge.

## Execution decisions

- Passed the shared contract with each extracted task brief, because the brief script extracts only its task section. If wrong, interface assumptions would need rework.
- Used the existing non-main shared checkout instead of a new worktree, honoring the owner’s branch preference. The tradeoff is coordination with the Windows checkout; no concurrent changes were observed.
- Treated the owner’s “yes” as implementation-plan approval and updated completion markers after implementation. If that interpretation were wrong, these reversible branch changes would need review before any integration; no merge was performed.
