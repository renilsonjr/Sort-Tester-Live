# Current route-chart reference for Issue #5

**Owner instruction, November 8, 2026:** use the photo supplied as “Talk with Hasan 2.jpeg” instead of the earlier displayed chart. This approves the reference and the explicit corrections below; it does not approve every application's transcription, Ranked difficulty or a Hard work-methods bank.

**Historical r1 implementation status, before PR #31 merge:** Implemented on `codex/ranked-mode` through application commit `929f189`, locally verified; not live or published. Source provenance is `twilight-2026-11-08-r1`. Owner Ranked difficulty/canonical/version/work-methods approvals remain pending in Issue #5.

**Related:** [[2026-11-07-ranked-question-bank-review]], [[2026-11-07-ranked-decision-record]]. Implementation/review tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

**Current follow-up:** PR #31 was merged and deployed. The subsequent Indiana correction (clause 9) is being prepared on `codex/ranked-mode` for review; it is not live yet. Earlier r1 test/review statements below describe the previous milestone. Follow-up local checks passed: `node --test tests/*.test.mjs` (386 tests), backend unittest discovery (10 tests), and `git diff --check`. The new regression verifies ORANGE accepted/PURPLE rejected, EN/ES feedback, and saved r1 Indiana answers remaining unchanged. No follow-up browser, phone, hosted or live result is claimed by these local checks.

## Source and exact owner corrections

The photo is titled “Saddle Brook Twilight Primary Sort Chart”. Keep its image in the private source project's chart folder, not this public repository or Pages release. Private working copy: `docs/charts/primary-sort-chart-2026-11-08.jpeg`, copied byte-for-byte from the supplied photo. SHA-256: `d54883a35b4556abae22d948a24f8b146509fd649e42a9a7b3e7abcdf5b70a7d`.

Apply this photo with only the owner's stated corrections; do not automatically import older chart/sort-change overrides:

1. **Ground, NY 128–147 → GOLD.** The printed Ground 140–147 ORANGE row is superseded. This correction is Ground-specific; it does not change the photo's 2 Day Air, 3 Day Select or Next Day Air NY rows.
2. **3 Day Select, `* 811–999 → PURPLE`.** This is the cropped bottom row supplied by the owner. “Third day air” in the message refers here to the photo's 3 Day Select column, not 2 Day Air.

3. **NJ preload codes, all four services:** 078 4 → RED; 082 9 → RED; 083 9 → RED; 079 9 → ORANGE. The three RED answers explicitly override the photo's BLUE entries. The app already matches these four specific answers; this confirmation does not by itself classify every unlisted NJ code.
4. **Ground TN 376–378 → BLUE** remains an exception inside the surrounding 370–385 BROWN range.
5. **NY 148 1 → GOLD** remains an exception to 148–149 ORANGE on Ground, 2 Day Air and 3 Day Select. No such override is added to Next Day Air.
6. **NY 120–121 → GOLD on all four services**, retaining the broader rule despite the photo showing only 120 0. The owner clarified the initially ambiguous “yes” and explicitly confirmed this scope.
7. **Routing-code endings 2S → BLUE and 1S → PURPLE**, all four services, overriding ordinary range answers; retained by owner confirmation.
8. **Destination/service indicator +1 → PURPLE**, all four services. Owner clarified that +1 appears where Ground / Next Day Air / the destination service is shown, **not as a routing-code suffix**. Keep it distinct from the route code and the base service. This rule is owner-supplied and not printed on the chart.

9. **2 Day Air IN 460–479 → ORANGE.** Subsequent explicit owner correction supersedes the photo's PURPLE entry. Update Study, generated/manual cards and neighboring Indiana/Ohio/Michigan explanations. Ground/3 Day Select remain ORANGE. Ordinary-route correction does not override destination +1 or routing suffix rules. Source revision becomes `twilight-2026-11-08-r2`; existing saved results retain their original answers and version.

### +1 scope and implemented branch behavior

The owner approved the plan in [[2026-11-08-chart-corrections-and-destination-plus-one]] and coverage in **Practice and the future Ranked bank**. Four explicit NY109 candidates now store optional `destinationModifier: '+1'` separately from unchanged base `svc` and routing `code`; each answer is PURPLE. The destination label shows e.g. **Ground +1 · NY**, while routing code stays **109**. The metadata survives translated questions/feedback, response records, saved results and workbook Service text. Old saved results without metadata retain their historical answers/counts and render normally.

Each Common pool expands 14→18 candidates but still selects 14 questions, reserving at least one +1 candidate. Mixed expands 16→17 after the Illinois split but still selects 16; level and service/NY run lengths and picker groups remain unchanged. Practice remains 15 seconds/question. This does not approve Ranked difficulty labels or implement the Ranked engine. No precedence for deliberately combined +1/conflicting 2S markers is approved; none are authored.

The previously displayed `primary-sort-chart-2026-09-17.jpeg` was removed from the private working folder at the owner's request. Other old chart/change images remain historical, not active reference sources. No history rewrite or public photo upload is part of this task.

## Corrected against the active source on the branch

The independent literal fixture contains **283 main/exception rows** transcribed from the photo plus confirmed owner overrides, with source provenance. The full source/card suite checks this matrix, inclusive boundaries and emitted cards; expected answers were not generated from application CHART.

| Scenario | Active reference and implemented branch answer |
| --- | --- |
| 2 Day Air GA300–319 | BLUE; old chart-derived PURPLE conflict resolved |
| Ground NY128–147 | GOLD, owner correction; service scope preserved |
| 2 Day Air / 3 Day Select NY140–147 | ORANGE; Ground override does not leak into these services |
| 2 Day Air IL600–608 | YELLOW |
| 2 Day Air IL609–629 | ORANGE; ambiguous Mixed 600–619 retired and split into 600–608 and 609–619 |
| 3 Day Select TX750–768 / 770–784 | BLUE; TX7690/785–799 stay PURPLE |
| 3 Day Select `* 811–999` | PURPLE, owner-supplied cropped row |
| NJ generic 070–089 | CHECK from the photo; specific confirmed preload exceptions retained; unreviewed broad NJ scenarios excluded from assignment |
| Retained exceptions | TN376–378 Ground BLUE; NY120–121 all-service GOLD; NY1481 GOLD only on Ground/2DA/3DS; NDA136 PURPLE; 1S/2S retained |

Manual cards and English/Spanish explanations were audited alongside generated chart cards. Changed Illinois spans have new IDs; answer-only corrections retain their scenario IDs. `referenceVersion: 'twilight-2026-11-08-r1'` records source provenance, not owner approval of Ranked versions or difficulty.

## Verified evidence and limits

At application commit `929f189`, the final local commands passed: **382 Node tests**, **10 backend tests**, and `pip check` with no broken requirements. `git diff --check` is clean. Reference, destination, deterministic selection, display/history/export and escaping tests are included; backend foundation checks alone would not prove the content correct.

Actual Chrome acceptance on the local branch verified ordinary legacy 5/10 retained after reload and a new Common 14-question run 5/14, with all four +1 services observed. Question/feedback English↔Spanish, wrong/timeout, history and reload retained +1 separately from 109. At 390×844 there was no horizontal page overflow, and basic Tab/Enter worked. No physical-phone test or full accessibility audit is claimed.

The actual 24,401-byte XLSX download was reopened as ZIP/XML and visually viewed with Finder Quick Look on both Results and Missorts: two result rows, 14 missorts, four translated +1 Service rows, code 109/PURPLE, including a timeout. Legacy rows gained no modifier. Microsoft Excel/Numbers and physical Windows UI were not tested. Long existing Test labels can clip at fixed preview widths; underlying values remain. Browser warn/error logs were empty during the flows. Evidence screenshots remain local; no photo or screenshot binary is committed.

The refreshed candidate inventory is **583 memberships / 379 distinct IDs / 292 route-only heuristic keys / 296 destination-aware heuristic keys**, with unchanged playable run lengths. See [[2026-11-07-ranked-question-bank-review]] for per-deck counts and the limits of these heuristics. Neither establishes owner-approved canonical deduplication or a usable Ranked bank.

## Still pending

- Final whole-branch review, PR update and exact-head hosted CI are separate controller-owned gates; local evidence does not claim push, hosted success, merge or publication.
- Owner-reviewed Easy/Medium/Hard labels, canonical duplicate identity and approved scenario/version rules.
- Separate authoritative Hard work-methods content and enough reviewed fresh tie sets, including replacement rounds.

Issue #5 remains open. These branch changes implement Practice corrections and future Ranked candidates, not the Ranked engine/auth/scoring or approval of its bank.
