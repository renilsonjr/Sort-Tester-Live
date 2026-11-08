# Current route-chart reference for Issue #5

**Owner instruction, November 8, 2026:** use the photo supplied as “Talk with Hasan 2.jpeg” instead of the earlier displayed chart. This approves the reference and the explicit corrections below; it does not approve every application's transcription, Ranked difficulty or a Hard work-methods bank.

**Related:** [[2026-11-07-ranked-question-bank-review]], [[2026-11-07-ranked-decision-record]]. Implementation/review tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

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

### +1 presentation proposal and remaining scope

Proposed quiz example: destination **Ground +1**, state **NY**, routing code **109**, correct belt **PURPLE**. The route code remains 109; do not rewrite it as “109 +1” or infer this rule from a route ending in +1. Store a separate optional destination modifier while preserving the base service, and carry it through feedback, saved results and export. This is a proposed implementation approach, not working functionality or owner approval of a schema/property name.

The owner is being asked whether new +1 questions should appear in existing Practice as well as the future Ranked bank, or only in the Ranked bank. Do not assume either placement, change Practice quiz length or implement a new question before that scope and the correction plan are reviewed. No precedence for a deliberately combined +1 and conflicting 2S marker has been chosen; keep such ambiguous combinations out of authored questions pending a decision, rather than invent a routing priority.


The previously displayed `primary-sort-chart-2026-09-17.jpeg` was removed from the private working folder at the owner's request. Other old chart/change images remain historical, not active reference sources. No history rewrite or public photo upload is part of this task.

## First conflict resolved at the source level

For **2 Day Air / GA / 300–319**, the new photo says **BLUE**. Therefore the earlier PURPLE conclusion from the superseded chart must not be used. Current `src/chart.js` still says PURPLE while the explicit Mixed Missorts card says BLUE; code changes and regression checks remain pending a reviewed correction plan. The current Practice answer for this scenario is inconsistent across decks.

## Initial additional differences to audit

These are observations against the new source, not a complete comparison or authorization to silently change every quiz:

| Scenario | New active reference | Current app data observation |
| --- | --- | --- |
| Ground NY 128–147 | GOLD, owner correction | Existing shared rows already give GOLD; verify correct service scope in other columns |
| 2 Day Air IL 600–608 | YELLOW in photo | Current main chart and explicit mixed card use PURPLE from the old reference |
| 2 Day Air IL 609–629 | ORANGE in photo | Current chart uses PURPLE through 619, then ORANGE 620–629 |
| 3 Day Select TX 750–768 | BLUE in photo | Current chart uses PURPLE |
| 3 Day Select TX 770–784 | BLUE in photo | Current chart uses PURPLE |
| 3 Day Select `* 811–999` | PURPLE, owner-supplied cropped row | Current chart already contains this row |

Perform a full service-specific row/exception/overlap and explanation audit before proposing code corrections. The old shared-East helper applies NY changes across multiple services; owner correction here is Ground only. Use the explicitly retained NJ/Tennessee/New York/termination overrides above; other unlisted cases still require source-specific review. Do not confuse route ranges with single-code exceptions or treat candidate Practice difficulty labels as owner-approved Ranked labels.

## Still pending

- Review the complete transcription and all card explanations against this active reference.
- Propose the minimal data correction plan and appropriate route/deck regression checks before code edits; preserve UI and unrelated Practice behavior.
- Obtain owner-reviewed Easy/Medium/Hard labels, stable canonical scenario/version rules and a separate Hard work-methods pool.
- Re-run the bank inventory after actual corrections; the November 7 counts remain a historical snapshot, not a new approved bank count.

No application, backend or quiz data is modified by this reference record. Issue #5 remains open.
