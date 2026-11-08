# Ranked question bank — candidate inventory and owner review

**Historical r1 status before PR #31 merge:** Chart corrections and destination +1 are implemented and locally verified on `codex/ranked-mode` through application commit `929f189`. They are **not live or published**. Counts are candidate inventory, not owner-approved Ranked content. Implementation owner: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5). Policy: [[2026-11-07-ranked-decision-record]]; proposed versioning: [[2026-11-07-ranked-security-operations-design]]. Active source: [[2026-11-08-ranked-chart-reference]]; implementation plan: [[2026-11-08-chart-corrections-and-destination-plus-one]].

## Full-chart difficulty milestone complete

All283 review entries now have owner-approved labels:103 Easy /127 Medium /53 Hard. [[2026-11-08-ranked-full-chart-review]] contains the complete ledger and final consistency audit. Original17 bilingual approvals are preserved. Four expanded bilingual explanations were subsequently approved;262 English and262 Spanish explanations remain pending, tracked in [[2026-11-08-ranked-expanded-wording-review]]. Canonical identity/coverage and versioning/assignment validation remain open. Four broad NJ CHECK rows stay held without guessed answers; the six hyphenated Ground codes are now owner-confirmed exact literals, not ranges; their approved answers and Hard labels are unchanged. Only the work-methods tie-question content is deferred. This completes difficulty classification, not Issue5 or a usable Ranked bank.

## Owner scope expansion — full-chart bank

The owner explicitly requested classifying all usable chart directions to randomize the15-question quiz, preserving the17 existing difficulty approvals without asking to rank them again. The17 are a reviewed subset, not the bank-size limit. [[2026-11-08-ranked-full-chart-review]] accounts for every source row and the four+1 contexts, tracks the new difficulty proposals and subsequent approvals while keeping four broad-NJ CHECK rows on hold. New labels and wording are not automatically approved. Source entries may need canonical merges/splits or exception clarifications before becoming executable questions. The proposed bank design was revised to this expanded scope; it still needs owner review.

## Subsequent owner decisions — November 8, after PR #31 merge

PR #31 is merged and deployed. The r1 evidence below is historical; the subsequent 2DA Indiana ORANGE correction is pending review/publication as source revision `twilight-2026-11-08-r2`. Source details: [[2026-11-08-ranked-chart-reference]].

Settled rules for future Ranked assignment (not implemented by Practice code):

- Copies of the same scenario across Practice decks count once. Different base services and ordinary versus destination +1 remain distinct contexts.
- Owner explicitly approved treating `GND` and `GRD` as the same Ground service for canonical duplicate detection. Equivalent service abbreviations must not create additional assignment slots.
- Overlapping ZIP ranges for the same service/destination context cannot appear together in a Ranked quiz.
- Broad-range question wording must explicitly exclude answer-changing exceptions.
- Each scenario receives one owner-reviewed fixed difficulty, independent of Practice deck membership.
- Starting guideline: standard routes Easy; narrower ranges/service distinctions Medium; exact exceptions/suffixes/destination modifiers Hard. Owner review can override this guideline.

The following labels were individually reviewed in chat. English wording/explanations were subsequently approved separately in [[2026-11-08-ranked-question-wording-review]]. Spanish translations were subsequently approved in three separate group reviews as well. These reviews do not approve a canonical schema, immutable assignments or a usable Ranked bank.

| Service | Scenario | Owner difficulty / status |
| --- | --- | --- |
| Ground | MA010–024 → GOLD | Easy |
| Ground | GA300–319 → BLUE | Easy |
| Ground | FL320–349 → PINK | Easy |
| Ground | VT050–059 → GOLD | Easy |
| Ground | CT060–069 → GOLD | Easy |
| 2 Day Air | IL600–608 → YELLOW | Hard; owner explicitly reclassified this range from Medium |
| 2 Day Air | IL609–629 → ORANGE | Hard; owner explicitly reclassified this range from Medium |
| 3 Day Select | TX770–784 → BLUE | Medium |
| 2 Day Air | NY140–147 → ORANGE | Medium |
| 3 Day Select | TX750–768 → BLUE | Medium |
| 2 Day Air | FL320–349 → PURPLE | Medium |
| 3 Day Select | AL350–369 → BLUE | Medium |
| Ground | TN376–378 → BLUE | Hard |
| Ground | NY148 1 → GOLD | Hard |
| Ground | NY109, destination +1 → PURPLE | Hard |
| Ground | MA025–026 → BLUE | Hard; owner clarified Ground explicitly |
| 2 Day Air | IN460–479 → ORANGE | Hard requested; owner corrected the answer explicitly |

English question wording and explanations for all17 rows were separately approved in [[2026-11-08-ranked-question-wording-review]]; Spanish translations were subsequently approved in separate group reviews; the remaining technical bank gates stay open.

Reviewed labels now total **five Easy, five Medium and seven Hard**. This meets the initial numerical minimum of five labels per difficulty, but the remaining content/explanation/canonical/version gates stay open; these labels alone do not approve a usable Ranked bank.

The proposed Hard NJ0799 and NDA NY109+1 questions were replaced at the owner's request and are not approved as Hard by this discussion. Work-methods tie content remains a separate open gate. No product difficulty labels or assignment engine are added here.

## Current branch inventory — November 8, 2026

Loaded the real `src/decks.js` and `src/chart.js` modules with `tests/helpers/load-app-modules.mjs` in a temporary ESM sandbox at `929f189`. Every current card carries source provenance `twilight-2026-11-08-r1`. Candidate arrays overlap; their memberships are not unique scenarios or per-run counts.

| Practice deck | Candidate memberships | Distinct IDs within deck | Route-only heuristic keys | Destination-aware heuristic keys | Questions per run |
| --- | --- | --- | --- | --- | --- |
| Basic | 26 | 26 | 26 | 26 | 15 |
| Medium | 185 | 185 | 185 | 185 | 20 |
| Hard | 279 | 279 | 279 | 279 | 30 |
| Common Missorts · Set 1 | 18 | 18 | 18 | 18 | 14 |
| Common Missorts · Set 2 | 18 | 18 | 18 | 18 | 14 |
| Common Missorts · Mixed | 17 | 17 | 17 | 17 | 16 |
| New York | 10 | 10 | 10 | 10 | 10 |
| Next Day Air | 10 | 10 | 10 | 10 | 10 |
| 2 Day Air | 10 | 10 | 10 | 10 | 10 |
| 3 Day Select | 10 | 10 | 10 | 10 | 10 |

Across decks: **583 memberships, 379 distinct IDs, 292 route-only heuristic keys and 296 destination-aware heuristic keys**. The four +1 scenario IDs appear in both Common pools: eight memberships, four distinct IDs. Each Common run reserves at least one +1 card while keeping 14 questions. Mixed contains the two corrected Illinois spans and retains a 16-question run from its 17-card pool.

The route-only heuristic combines service (`GRD` normalized to `GND`), state and routing-code text; Unicode dashes become ASCII hyphens and whitespace is collapsed/trimmed. The destination-aware heuristic additionally includes the optional destination modifier. The old key now conflates four NY109 pairs: ordinary ORANGE and destination +1 PURPLE, one per service. These are intentional separate contexts, not conflicting answers. The destination-aware scan found no key with multiple belts, and no ID with multiple destination/answer combinations.

**Neither heuristic is an owner-approved canonical identity or deduplication policy.** They can miss equivalent/overlapping ranges or collapse other contextual distinctions. There is no approved unique Ranked-scenario count yet. Basic/Medium/Hard Practice pools overlap and do not establish disjoint owner-approved Ranked difficulty labels. Source provenance and existing `verified` flags do not confer that approval.

## Implemented corrections and verification

The independent active-reference fixture contains 283 main/exception rows. Source/card checks cover the full matrix and retained owner exceptions. On this branch, 2DA GA300–319 is BLUE; IL600–608 is YELLOW and 609–629 ORANGE; the ambiguous Mixed IL600–619 card is replaced by separate 600–608 and 609–619 cards. 3DS TX750–768 and 770–784 are BLUE. Ground-only NY140–147 GOLD no longer leaks to 2DA/3DS, which remain ORANGE. The retained NJ/TN/NY/1S/2S exceptions and cropped 3DS 811–999 PURPLE are covered.

Destination +1 is separate metadata for all four base services, using NY109/PURPLE candidates; routing code remains 109. It persists through translated questions, feedback, saved results and workbook Service text. Legacy saved results retain their historical answers/counts. No +1/conflicting 2S scenarios were authored, and no broad answer for unlisted NJ codes was invented.

Local final verification at application head `929f189`: `node --test tests/*.test.mjs` **382/382 passing**; backend unittest discovery **10/10 passing**; `pip check` reports no broken requirements. `git diff --check` is clean. Backend checks verify the existing foundation; they do not substitute for content/display tests.

Actual Chrome acceptance used fictional local records: legacy 5/10 survived reload, and a new 14-question Common run ended 5/14 with all four +1 services observed. English/Spanish question and feedback changes, wrong answers, timeout, saved history and reload worked. At 390×844 the page width remained 390 without horizontal overflow; basic Tab/Enter interaction worked. This is limited keyboard/mobile coverage, not an accessibility audit or physical-phone test.

A real 24,401-byte XLSX was downloaded and reopened as ZIP/XML: two results and 14 missorts, including four translated +1 Service rows with Routing code 109 and correct belt PURPLE, one recording timeout. Finder Quick Look displayed both Results and Missorts; Microsoft Excel/Numbers and a physical Windows UI were not tested. Long existing Test labels can clip at fixed preview column widths; raw values are retained. Browser console warn/error logs were empty during these flows. No chart photo or screenshot is committed. No push, exact-head hosted CI, final whole-branch review, merge or publication is established by this local evidence.

## Historical inventory — November 7, 2026

The read-only snapshot at `7c3f7a43c6b9e1e671f08c84539684d9373cc801` had **574 memberships, 374 distinct IDs and 291 route-only heuristic keys**. Basic/Medium/Hard were 26/185/279; Common 1/2 were 14/14; Mixed 16; NY/NDA/2DA/3DS 10 each. Those historical counts preceded the Illinois split and +1 additions and must not be presented as current.

That scan flagged 2DA/GA300–319 PURPLE in the chart versus BLUE in Mixed. The November 8 owner-selected replacement source resolved BLUE; implementation now matches it. The superseded photo and the historical scan are not the current answer authority.

## Owner review gate before Ranked assignment

- [x] Owner selected the active route reference and confirmed overrides; recorded in [[2026-11-08-ranked-chart-reference]].
- [x] Resolve 2DA/GA300–319 to BLUE and implement source-consistent corrections, explanation/exception checks and destination +1 support on the branch.
- [x] Re-run current candidate inventory and verify Practice sampling/run lengths and source-provenance propagation.
- [ ] Obtain the separate authoritative work-methods content/reference and confirm its permitted question scope.
- [ ] Approve canonical duplicate identity, answer/explanation, one Easy/Medium/Hard label and version for each Ranked scenario; source provenance alone is insufficient.
- [ ] Verify at least five distinct approved scenarios per difficulty and prevent repeated canonical scenarios across the 15-question assignment; test Ranked version freezing when implemented.
- [ ] Review/version a separate Hard work-methods pool for shared five-question prize rounds, with enough fresh sets for additional/outage-replaced rounds.
- [ ] Complete final whole-branch review, PR update and exact-head hosted checks before owner review/merge. No automatic publication is authorized.

Issue #5 remains open. Insufficient approved normal content blocks Ranked start without a score; insufficient fresh tie content invokes the approved owner-selection fallback. Passing Practice corrections does not make the Ranked bank usable.
