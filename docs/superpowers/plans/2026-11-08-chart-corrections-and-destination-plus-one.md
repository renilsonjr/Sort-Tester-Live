# Chart Corrections and Destination +1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans for native task-by-task execution after owner approval. Do not implement this document merely because it is committed.

**Status:** Proposed for owner review, November 8, 2026. Confirmed outcomes: active chart/retained exceptions and +1 coverage in Practice and the future Ranked bank. The field design, pool sampling and tasks below are assistant proposals. No product code has changed.

**Goal:** Make current route answers/explanations consistent with the selected chart and owner overrides, and teach destination +1 PURPLE without changing existing Practice run lengths or screen layouts.

**Architecture:** Keep current chart/deck/quiz modules. Store +1 as an optional `destinationModifier` alongside the unchanged base `svc` and routing `code`; preserve it through response/history/export. Sample expanded ordinary-deck pools through a separate `practiceRunSize` property so existing `questionCount` continues identifying the three level decks in the picker.

**Tech Stack:** Existing browser JavaScript, Node built-in test runner, existing English/Spanish translation helpers. No new runtime package or backend/database change.

**Spec:** [[2026-11-08-ranked-chart-reference]] (owner source/overrides/scope); [[2026-11-07-ranked-question-bank-review]] (remaining curation gates).

## Approaches considered

1. Append four +1 cards and play the full expanded Common Missorts deck: simplest, but changes ordinary run length from 14 to18. Not recommended under the preserve-Practice constraint.
2. **Recommended:** expanded candidate pools, same existing run lengths, using `practiceRunSize` distinct from `questionCount`. Requires sampling/count-label tests, keeps picker grouping and run lengths stable.
3. Encode +1 inside `svc` or append it to `code`: not selected. It is a separate destination indicator; service translation/grouping and routing code must remain meaningful.

Owner review must explicitly cover approach2 and the destination-label example: **Ground +1 · NY**, routing code **109**, answer **PURPLE**. No new screen, control or layout is proposed; existing destination text gains the relevant marker.

## Global constraints

- Work only on shared `codex/ranked-mode` in Sort-Tester-Live. Never push main or modify the private source application's code. Keep chart photos private.
- Use the photo plus every confirmed exception in the spec, not historical sort-change assumptions. No new broad NJ rule for unlisted codes.
- Practice stays 15 seconds/question. Preserve current run lengths: Basic15, Medium20, Hard30; Common Missorts1/2 each14; Mixed16; NY/NDA/2DA/3DS each10. Ordinary decks remain in their current picker group.
- Scope is content corrections and +1 support. No Ranked engine/auth/scoring, new visual design, employee data migration or publication. Ranked candidates still need owner difficulty/work-methods review in Issue5.
- +1 is a destination modifier, not a ZIP/routing suffix or a fifth base service. Correct belt PURPLE on all four services. 2S/1S retain their approved routing-ending meanings.
- Do not author combined +1/conflicting2S scenarios until precedence is approved. Existing valid ordinary/1S/2S cards remain available.
- Old saved Practice results keep their historical answer/explanation/count; do not rewrite or rescore them. Missing modifier/version fields must render normally.
- All new/changed text must be escaped at HTML boundaries and correct in English and Spanish. Preserve existing export structure; put +1 in its Service text, not Routing code.

## Review focus

- Broad IL600–619 crosses YELLOW/ORANGE in the active chart: retire that ambiguous question rather than choose one belt for the whole span (Task1).
- Ground-only NY140–147 GOLD must not leak through sharedEast into 2DA/3DS, and NY1481/NDA136 exceptions must survive (Task1).
- New candidate pools must not move ordinary decks into the level picker, alter run counts or fail to produce a full run under belt/service sampling constraints (Task2).
- Correct destination display on initial render can be lost on language toggle, feedback/history or Excel export; old saved rows have no new field (Task3).
- +1 PURPLE can look accidentally correct where a base route is already PURPLE: demonstrate it with NY109, normally ORANGE, for each base service; never infer +1 from route text (Tasks2/3).

## Task1: Independent reference cases and content corrections

**Files:** Create `tests/helpers/load-app-modules.mjs`, `tests/fixtures/twilight-reference-2026-11-08.json`, `tests/chart-reference.test.mjs`; modify `src/chart.js`, `src/questions.js`, `src/decks.js`, `src/i18n.js` as required by the reviewed source matrix.

**Interfaces:** Fixture cases carry stable case ID, service, state, code/range, expected belt and photo/owner-override provenance. Temporary test loader provides `loadAppModules(relativePaths) -> { modules, cleanup }`: copy source modules to an isolated temporary directory with `type: module`, import their actual ESM/query-string dependencies, then remove it after tests. No repository package/module-mode change.

- [ ] Transcribe the complete main/exception source matrix independently from the private photo and all eight confirmed spec clauses. Do not generate expected values from current CHART. If a row is unreadable or conflicts with an unconfirmed rule, stop that case for owner review before changing it.
- [ ] Write failing reference/card tests covering: 2DA GA300–319 BLUE; IL600–608 YELLOW,609–629 ORANGE; 3DS TX750–768/770–784 BLUE,7690/785–799 PURPLE; cropped811–999 PURPLE. Include lower/upper boundaries and special-code exceptions.
- [ ] Add explicit tests for Ground NY128–147 GOLD; 2DA/3DS140–147 ORANGE; NY120–121 GOLD allfour; NY1481 GOLD on Ground/2DA/3DS only; NDA136 PURPLE; retained TN376–378 BLUE; four approved NJ codes across allservices; preserved1S/2S rules.
  Exact example assertion in `test('2DA Georgia uses the owner-selected reference')`:

```js
assert.equal(CHART['2 Day Air'].main.find(([state, code]) => state === 'GA' && code === '300–319')?.[2], 'BLUE');
```

- [ ] Run `node --test tests/chart-reference.test.mjs`; confirm relevant source inconsistencies fail, not just harness setup. A passing NJ/exception case is expected protection for unchanged correct rules.
- [ ] Correct CHART per the independently checked matrix. Separate service-specific NY overrides from sharedEast. The photo's generic NJ070–089 CHECK is not evidence every unspecified code is RED; retain the explicit owner-confirmed preload overrides, and keep broad unreviewed NJ scenarios out of question assignment.
- [ ] Correct manual cards and explanations in Common/NewYork/service/Mixed arrays and Spanish feedback. Retire `mixed-il-600-619-2da`; replace it with `mixed-il-600-608-2da` YELLOW and `mixed-il-609-619-2da` ORANGE. Keep620–629 ORANGE with a corrected explanation. Change existing `2da-il-600-608` to YELLOW. Update stale multi-service NY140–147 explanations and neighbouring-belt descriptions.
- [ ] Give changed routes new IDs when their meaning changes; preserve IDs for unchanged scenarios. Add/export `ROUTE_REFERENCE_VERSION = 'twilight-2026-11-08-r1'` in `src/chart.js`; attach that provenance to current cards without treating it as Ranked difficulty approval. Audit every card against its referenced scenario, not just the initially flagged GA conflict.
- [ ] Run reference tests, all existing Node tests and `git diff --check`; inspect the independent matrix versus actual changes. Commit the tested content correction.

## Task2: +1 candidates and stable Practice lengths

**Files:** Modify `src/questions.js`, `src/decks.js`, `src/levels.js`; create `tests/destination-plus-one.test.mjs`, `tests/practice-selection.test.mjs`; use the Task1 loader.

**Interfaces:** Cards keep `{id,svc,state,code,belt,confusions,why,tags}` and may add `destinationModifier: '+1'`, `referenceVersion`. Ordinary decks may add `practiceRunSize`; existing `questionCount` retains its current level-deck/picker meaning. `selectLevelCards(deck, rand)` returns the requested count for either size property, otherwise the whole ordinary deck as today.

- [ ] Write failing tests for four explicit +1 candidates: `destination-plus-one-gnd`, `destination-plus-one-nda`, `destination-plus-one-2da`, `destination-plus-one-3ds`; each NY109, respective base service, `destinationModifier:'+1'`, beltPURPLE, three distinct non-PURPLE distractors and clear destination-based explanation. Code stays109. Include synthetic control without modifier showing base NY109 ORANGE.
- [ ] Add those candidates to shared COMMON_CORE; all four are eligible future Ranked candidates, with difficulty still unapproved. Add authoring assertions to `tests/destination-plus-one.test.mjs`: every defined modifier must be +1, no authored routing code may contain literal +1, and a +1 card cannot also carry a conflicting2S ending. These tests reject ambiguous future seed content in CI; no runtime authoring API is introduced. Do not invent priority or rewrite arbitrary route strings.
  In `test('plus-one cards carry separate destination metadata')`, for each of the four exact IDs above:

```js
assert.equal(card.code, '109');
assert.equal(card.destinationModifier, '+1');
assert.equal(card.belt, 'PURPLE');
assert.ok(['GND', 'NDA', '2DA', '3DS'].includes(card.svc));
```

- [ ] Add `practiceRunSize:14` to each Common Missorts deck and `practiceRunSize:16` to Mixed. Do not set `questionCount` on ordinary decks. Common candidate arrays expand14→18; Mixed16→17 after the IL split, but playable counts remain14/16.
- [ ] Extend selection to use `questionCount ?? practiceRunSize` while preserving existing service/belt constraints and shuffle behavior. Keep non-sized service decks unchanged. Ensure every Common run includes at least one +1 candidate without repeating an ID; do not assume shuffle alone guarantees coverage. Reserve one randomly chosen +1 candidate, then fill remaining slots with the same constraints, counting that reservation toward the belt cap.
- [ ] Test counts, unique IDs, service/marker coverage and full selection under deterministic RNG seeds0–99 plus all-zero/near-one generators for both expanded Common pools and Mixed; level15/20/30 and four10-card decks remain valid. The `verified` status is not owner Ranked-content approval.
- [ ] Run new selection/destination tests and all Node tests; commit only after they pass. Do not resample or rewrite previously saved results.

## Task3: Destination label, recorded response and export

**Files:** Create `src/destination.js`; modify `src/app.js`, `src/quiz.js`, `src/i18n.js`, module cache-version imports in `index.html`/affected modules as needed; add `tests/destination-display.test.mjs`, extend new tests and `tests/security.test.mjs` where relevant. No CSS/layout redesign.

**Interfaces:** `formatDestinationLabel(serviceLabel, destinationModifier) -> string` is pure display formatting with absent marker returning the existing label and +1 producing e.g. `Ground +1`. It is not a routing/scoring engine; bank validation constrains authored modifier values. `serviceName(svc, destinationModifier)` in app combines the existing translated base service with that formatter. `record()` in quiz preserves `destinationModifier` and `referenceVersion` from the actual card in each response; historical absent values remain supported.

- [ ] Write failing tests asserting `formatDestinationLabel('Ground','+1') === 'Ground +1'` and absent marker returnsGround. Test ordinary and +1 response records preserve code109 separately; wrong/timeout outcomes retain marker/provenance too.
  Exact display assertions in `test('destination plus-one never changes the routing code')`:

```js
assert.equal(formatDestinationLabel('Ground', '+1'), 'Ground +1');
assert.equal(formatDestinationLabel('Ground'), 'Ground');
assert.equal(response.code, '109');
assert.equal(response.destinationModifier, '+1');
```

- [ ] Implement the small formatter and response metadata. No string parsing of ZIP codes to infer +1; correct answers remain authored card data. Do not mutate persisted old results.
- [ ] Update all destination call sites: initial card, language-toggle refresh, feedback/review, missed summaries, saved-log detail and workbook Service value. Preserve Routing code column109. Use `deck.practiceRunSize ?? deck.cards.length` for ordinary picker count text without changing its grouping filter.
- [ ] Add English/Spanish +1 explanation before generic/suffix explanation branches; use the destination modifier, not route text. Keep 1S/2S explanations correct and preserve the confirmed NJ answers. Escape marker/service text at every existing HTML sink; locally altered stored text must remain inert.
- [ ] Exercise real renderer/export functions with the existing VM/fake-DOM test pattern. Assert Ground +1 persists through language change, incorrect answer/timeout, reload and Excel data; legacy rows without modifier render/export identically. Confirm marker stays out of Routing code. No fake successful XLSX download claim from testing only workbook-row objects.
- [ ] Update existing module-version query strings for every changed module/importer so a future approved Pages deployment cannot mix old and new data/rendering. Keep dependency pins/permissions unchanged and chart photos absent from release files.
- [ ] Run all Node tests; manually walk a fictional +1 Practice quiz in both languages and an ordinary quiz, reload its saved result, generate/open a real Excel export, and inspect mobile/keyboard behavior. Record observed versus untested steps. Commit after required checks.

## Task4: Review, CI and remaining Issue5 gates

**Files:** Update [[2026-11-07-ranked-question-bank-review]] and [[2026-11-08-ranked-chart-reference]] with verified source/count/version evidence; existing workflow already runs `node --test tests/*.test.mjs`, no workflow change planned.

- [ ] Run `node --test tests/*.test.mjs`, `backend/.venv/bin/python -m unittest discover -s backend/tests -v`, `backend/.venv/bin/python -m pip check`, and `git diff --check`. Record actual totals; none of these foundation checks substitutes for new content/display tests.
- [ ] Re-run deck/canonical-scenario inventory after corrections; report candidate memberships versus unique scenarios versus per-run sizes. Do not reuse the November7 counts as if unchanged or declare all questions approved from counts alone.
- [ ] Prepare/update one review PR on the shared Ranked branch with confirmed source, new metadata/sampling behavior, browser/export evidence, risks and exact-head hosted checks. Owner reviews/merges; no auto-merge/public publication in execution authorization.
- [ ] Keep Issue5 open: owner Easy/Medium/Hard labels, reviewed separate Hard work-methods content, canonical duplicate/version approvals and sufficient fresh tie sets still need their own review. Do not call the Ranked bank usable merely because Practice corrections pass.

## Self-review / handoff

Spec coverage: photo/override fidelity→Task1; Practice+Ranked +1 scope→Task2; correct destination location and history/export→Task3; actual evidence and remaining curation gates→Task4. Count metadata avoids moving ordinary decks into the level picker. No untouched-layout claim may hide missing +1 content. No policy for conflicting markers or unlisted NJ codes is invented.

**Recommended execution:** Native in this chat, in the four reviewable increments above; the changes share source/card/rendering contracts. Await owner review of this plan and sampling/label choices before any implementation. A fresh review of the resulting branch follows implementation. This proposal does not authorize feature execution by being pushed.
