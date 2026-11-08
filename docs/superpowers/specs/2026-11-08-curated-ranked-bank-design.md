# Separate curated Ranked bank — short design

**Status:** approach1 approved by the owner; this design is proposed for review before an implementation plan or product changes. Tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5). Proposed through [PR #32](https://github.com/renilsonjr/Sort-Tester-Live/pull/32).

**Related:** [[2026-11-07-ranked-question-bank-review]], [[2026-11-08-ranked-question-wording-review]], [[2026-11-08-ranked-chart-reference]], [[2026-11-07-ranked-decision-record]], [[2026-11-07-ranked-security-operations-design]].

## Intent and constraints

Create one reviewable bank covering all usable directions in the active chart and retained owner rules. Preserve the17 previously approved scenarios (5 Easy,5 Medium,7 Hard), including their approved English/Spanish copy, without re-ranking them. Review and classify the remaining chart entries before treating them as approved Ranked content. The scope is no longer limited to17 scenarios. See [[2026-11-08-ranked-full-chart-review]] and its machine-readable inventory for the full coverage/proposal ledger. Keep existing Practice behavior and decks unchanged. The source authority is `twilight-2026-11-08-r2`, including 2DA IN460–479 ORANGE. This is a backend content milestone, not accounts, scoring, timers, promotions, database persistence or a playable Ranked screen.

Only the separate sort-work-methods tie-question content is deferred. Other approved tie-break rules remain unchanged. The expanded route bank does not silently replace the deferred work-methods tie bank. Issue5 remains open for its deferred/broader gates; no dependency is silently removed from Issue6.

## Approaches

1. **Separate curated Ranked bank — owner-selected.** Explicit reviewed content and fixed difficulty/version ownership, with Practice unchanged. Maintain a reviewed artifact and adapters instead of inferring Ranked approval from Practice deck names.
2. **Attach Ranked approval directly to Practice cards.** Reuses existing objects, but Practice has overlapping pools and different grouping/sampling rules; equivalent scenarios can have multiple IDs. This was not selected.

## Proposed structure — assistant technical choices for review

- Store the initial content as a versioned JSON artifact under `backend/data/ranked/`, with a small Python loader/validator and unit tests using existing backend tooling. No new packages or database are needed for this milestone. Exact filenames/module boundaries are implementation-plan details.
- Give each scenario a stable descriptive ID based on its meaning, independent of deck membership, language, difficulty or explanation text. E1–H7 remain review-sheet references, not permanent IDs. Include an explicit review-reference mapping so every included record can be traced back to its approved source/copy, preserving the original17 review references.
- A scenario stores normalized base service, state, structured routing meaning, optional destination modifier, approved difficulty/answer, bilingual prompt/explanations, source revision and its content revision. Store leading-zero route components as strings. Distinguish prefix ranges such as025–026 from exact codes such as148 1. Keep destination+1 separate from routing109.
- Bank revision and individual content revision identify immutable published content. Changes produce a new revision, retaining earlier artifacts. The loader returns immutable records and detects duplicate IDs/meaning and conflicting metadata. Source revision identifies the chart authority; it does not itself confer owner approval or substitute for a bank revision.
- One English/Spanish translation pair belongs to the same scenario. Normalize GND/GRD/Ground to one service. Normalize only within an explicit route type: numeric prefix ranges may normalize dash typography, while owner-confirmed exact literals such as `575 3-6` preserve their complete displayed spaces and hyphens. Never infer range endpoints or collapse this literal into `57536`. Preserve leading zeros and exact-code qualifiers. Different services and ordinary versus+1 remain distinct contexts.

## Validation and assignment preparation

Validate every included owner-approved record, legal service/belt/difficulty values, both languages, unique stable IDs/canonical meanings and source/content revisions. Reject unsupported route/modifier shapes instead of guessing. The artifact must not invent combined+1/conflicting2S cases or answers for held broad-NJ CHECK rows. Full-chart coverage requires explicit modeling of wildcard fallback ranges, combined-state rows, named destinations, exact literal codes and routing suffixes as well as ordinary numeric prefix ranges. The owner confirmed Ground NE575 3-6, NV833 9-7, AZ847 2-7, NV864 4-7, NV890 0-0 and AZ922 2-0 as single exact codes, not ranges. Record the literal kind explicitly before matching, normalization or overlap validation; unsupported or genuinely unclarified route forms remain blocked.

A pure selection helper prepares15 questions:five per difficulty, no repeated canonical scenario and no overlapping effective routing ranges for the same service/state/destination context. Exceptions must be represented explicitly; a broad question that includes an answer-changing exception must carry the approved exclusion wording and excluded routing coverage. Unsupported or ambiguous cases fail validation. Test inclusive boundaries and exact-code meaning, not just text equality.

Selection must verify a complete compatible5/5/5 set exists, not merely raw category counts. If none exists, return a clear bank-unavailable error and no partial assignment. The later attempt-start transaction must consume that result before creating an attempt or score. Do not claim that unbuilt transaction is enforced here. The helper returns the chosen IDs/revisions and immutable content needed for a later assignment snapshot; database freezing and restart persistence belong to Issue6 and engine integration.

The owner rejected a17-only bank because it would repeat the same Easy and Medium questions. Expand the population to all usable chart directions while keeping each run at15 questions (five per difficulty). Inventory accounting:283 source rows, four broad NJ CHECK rows held without guessed answers, plus four explicit service-specific+1 contexts =283 review entries before any necessary canonical merges/splits. The17 original approvals are preserved. The full-chart ledger tracks the subsequent approvals and remaining proposals; those live counts must be used rather than treating the initial266 proposals as a frozen pending total. A source row is not automatically a unique executable question. Only approved, unambiguous content can enter the selectable bank; raw count alone cannot satisfy the release gate.

## Verification and limits

Use test-first implementation. Verify literal approved answers/labels/translations, GND/GRD equivalence, translation equivalence, ordinary versus+1 distinction, range overlap/boundaries, exact-code exceptions (including rejection of range interpretation for confirmed hyphenated literals), missing copy, malformed/duplicate/conflicting records, insufficient or incompatible pools, deterministic selection and revision preservation. Exercise real loader/selection code with small independent fixtures. Run the backend and existing frontend/security suites; hosted Windows checks must pass at the resulting PR head.

Do not add public endpoints or import the bank into browser modules. A public repository makes committed content readable; this design does not promise secrecy or prevent memorization. Future API delivery must enforce the already-approved answer/feedback timing. No UI redesign, deployment, database installation, score edits or automatic prize selection is authorized by this design.

After the owner approves this design, prepare a separate tested implementation plan for review. Approval of the selected approach alone does not approve product implementation.
