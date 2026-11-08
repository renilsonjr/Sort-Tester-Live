# Current route-chart reference for Issue #5

**Owner instruction, November 8, 2026:** use the photo supplied as “Talk with Hasan 2.jpeg” instead of the earlier displayed chart. This approves the reference and the explicit corrections below; it does not approve every application's transcription, Ranked difficulty or a Hard work-methods bank.

**Related:** [[2026-11-07-ranked-question-bank-review]], [[2026-11-07-ranked-decision-record]]. Implementation/review tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

## Source and exact owner corrections

The photo is titled “Saddle Brook Twilight Primary Sort Chart”. Keep its image in the private source project's chart folder, not this public repository or Pages release. Private working copy: `docs/charts/primary-sort-chart-2026-11-08.jpeg`, copied byte-for-byte from the supplied photo. SHA-256: `d54883a35b4556abae22d948a24f8b146509fd649e42a9a7b3e7abcdf5b70a7d`.

Apply this photo with only the owner's stated corrections; do not automatically import older chart/sort-change overrides:

1. **Ground, NY 128–147 → GOLD.** The printed Ground 140–147 ORANGE row is superseded. This correction is Ground-specific; it does not change the photo's 2 Day Air, 3 Day Select or Next Day Air NY rows.
2. **3 Day Select, `* 811–999 → PURPLE`.** This is the cropped bottom row supplied by the owner. “Third day air” in the message refers here to the photo's 3 Day Select column, not 2 Day Air.

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

Perform a full service-specific row/exception/overlap and explanation audit before proposing code corrections. The old shared-East helper applies NY changes across multiple services; owner correction here is Ground only. Existing NJ and Tennessee overrides also need comparison with the new photo rather than assumption. Do not confuse route ranges with single-code exceptions or treat candidate Practice difficulty labels as owner-approved Ranked labels.

## Still pending

- Review the complete transcription and all card explanations against this active reference.
- Propose the minimal data correction plan and appropriate route/deck regression checks before code edits; preserve UI and unrelated Practice behavior.
- Obtain owner-reviewed Easy/Medium/Hard labels, stable canonical scenario/version rules and a separate Hard work-methods pool.
- Re-run the bank inventory after actual corrections; the November 7 counts remain a historical snapshot, not a new approved bank count.

No application, backend or quiz data is modified by this reference record. Issue #5 remains open.
