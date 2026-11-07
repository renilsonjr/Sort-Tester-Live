# Ranked question bank — candidate inventory and owner review

**Status:** Read-only inventory of current Practice sources on November 7, 2026. No answer, difficulty or work-methods content is approved by this inventory. Implementation owner: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5). Policy: [[2026-11-07-ranked-decision-record]]; proposed versioning: [[2026-11-07-ranked-security-operations-design]].

Source snapshot: commit `7c3f7a43c6b9e1e671f08c84539684d9373cc801`; no application source changed during this review. Loaded `src/decks.js` and its imports in an isolated Node VM module context without changing the application. Counts describe full candidate arrays, not the number of questions in a Practice run. Decks overlap; do not add their rows to claim a unique bank.

| Practice deck | Candidate memberships | Distinct IDs within deck | Heuristic route keys within deck |
| --- | --- | --- | --- |
| Basic | 26 | 26 | 26 |
| Medium | 185 | 185 | 185 |
| Hard | 279 | 279 | 279 |
| Common Missorts · Set 1 | 14 | 14 | 14 |
| Common Missorts · Set 2 | 14 | 14 | 14 |
| Common Missorts · Mixed | 16 | 16 | 16 |
| New York | 10 | 10 | 10 |
| Next Day Air | 10 | 10 | 10 |
| 2 Day Air | 10 | 10 | 10 |
| 3 Day Select | 10 | 10 | 10 |

Across decks: **574 memberships, 374 distinct IDs, 291 heuristic route keys**. No ID had conflicting route/answer combinations under this scan. One normalized route key has multiple belt values: **2DA / GA / 300–319 → PURPLE and BLUE**. The chart-derived main row in `src/chart.js` uses PURPLE; the explicit mixed-deck card `2da-ga-300-319` in `src/decks.js` uses BLUE. This is a review flag, not proof either answer is correct: inspect the authoritative chart, exceptions and context before deciding.

The heuristic uses service (`GRD` normalized to `GND`), state and destination-code text with dash/whitespace normalization. It omits exception meaning and is not an approved canonical identity scheme. It can collapse distinct contexts or miss equivalent/overlapping scenarios. Existing Basic/Medium/Hard Practice decks overlap and do not establish disjoint owner-approved Ranked difficulties. Existing verification flags/comments do not replace a current chart check. No reviewed separate Hard sort-work-methods tie-break bank has been demonstrated.

## Owner review gate before Ranked assignment

- [ ] Identify the authoritative current chart/work-method reference and permitted question scope.
- [ ] Resolve the flagged 2DA/GA range using actual source context; check other overlapping ranges and service aliases.
- [ ] For each canonical scenario, approve the answer, explanation, one Easy/Medium/Hard label and version.
- [ ] Verify at least five distinct approved scenarios per difficulty; prevent repeated canonical scenarios across the 15-question assignment.
- [ ] Review and version a separate Hard work-methods pool for shared five-question prize rounds, including fresh sets for additional/outage-replaced rounds.
- [ ] Re-run the inventory and test sampling/version freezing. Insufficient normal content blocks starting Ranked without a score; insufficient fresh tie content invokes the approved owner-selection fallback.

No app content was edited, and Practice remains unchanged. These unchecked items are work in #5, not reasons to invent labels or silently approve answers in this planning PR.
