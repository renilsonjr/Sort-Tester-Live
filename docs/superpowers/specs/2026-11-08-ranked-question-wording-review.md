# Ranked question wording and explanation review

**Status:** proposed English wording and explanations; owner-reviewed answers/difficulty labels are recorded separately. No wording approval is inferred from label approval. Review one group at a time before implementation. Source revision: `twilight-2026-11-08-r2`, including the owner Indiana ORANGE override, pending publication through [PR #32](https://github.com/renilsonjr/Sort-Tester-Live/pull/32).

**Related:** [[2026-11-07-ranked-question-bank-review]], [[2026-11-08-ranked-chart-reference]]. Tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5).

## Proposed shared wording

Question: **Which belt does this go to?** Display the service/destination, state and routing code separately, as in Practice. Answers/explanations below appear only after answering under the later engine's approved feedback rules, not as hints in the prompt. No screen redesign or timing change is proposed here.

Only displayed modifiers apply: ordinary questions have no destination +1 or routing suffix. NY148 1 retains its explicit final digit; +1 is displayed in the destination, never appended to routing109. Review identifiers E1–H7 are document labels, not approved permanent canonical IDs.

## Proposed question sheet

| Review label | Approved difficulty | Service / destination | State | Routing code | Correct belt | Proposed explanation |
| --- | --- | --- | --- | --- | --- | --- |
| E1 | Easy | Ground | MA | 010–024 | GOLD | Ground MA010–024 follows the GOLD chart row. |
| E2 | Easy | Ground | GA | 300–319 | BLUE | Ground GA300–319 follows the BLUE chart row. |
| E3 | Easy | Ground | FL | 320–349 | PINK | Ground FL320–349 follows the PINK chart row. The service matters: 2 Day Air uses PURPLE for this range. |
| E4 | Easy | Ground | VT | 050–059 | GOLD | Ground VT050–059 follows the GOLD chart row. |
| E5 | Easy | Ground | CT | 060–069 | GOLD | Ground CT060–069 follows the GOLD chart row. |
| M1 | Medium | 3 Day Select | TX | 770–784 | BLUE | 3 Day Select TX770–784 goes BLUE. The separately listed TX769 0 and the next range785–799 go PURPLE. |
| M2 | Medium | 2 Day Air | NY | 140–147 | ORANGE | 2 Day Air NY140–147 goes ORANGE. The GOLD change applies to Ground, not this service. |
| M3 | Medium | 3 Day Select | TX | 750–768 | BLUE | 3 Day Select TX750–768 goes BLUE. The following listed TX769 0 goes PURPLE. |
| M4 | Medium | 2 Day Air | FL | 320–349 | PURPLE | 2 Day Air FL320–349 goes PURPLE. Ground and3 Day Select use PINK for this range. |
| M5 | Medium | 3 Day Select | AL | 350–369 | BLUE | 3 Day Select AL350–369 goes BLUE. Do not apply the2 Day Air PURPLE answer to this service. |
| H1 | Hard | 2 Day Air | IL | 600–608 | YELLOW | 2 Day Air IL600–608 goes YELLOW. The next range609–629 goes ORANGE. |
| H2 | Hard | 2 Day Air | IL | 609–629 | ORANGE | 2 Day Air IL609–629 goes ORANGE. The preceding range600–608 goes YELLOW. |
| H3 | Hard | Ground | TN | 376–378 | BLUE | TN376–378 is the Ground BLUE exception inside370–385. The surrounding Ground range is BROWN. |
| H4 | Hard | Ground | NY | 148 1 | GOLD | Ground NY148 1 is the exact-code GOLD exception to the ordinary148–149 ORANGE range. The last digit matters. |
| H5 | Hard | Ground +1 | NY | 109 | PURPLE | The destination indicator +1 goes PURPLE on all four services. Without +1, ordinary Ground NY109 goes ORANGE. The routing code remains109. |
| H6 | Hard | Ground | MA | 025–026 | BLUE | Ground MA025–026 goes BLUE. Next Day Air uses PURPLE for this range; do not apply that service answer to Ground. |
| H7 | Hard | 2 Day Air | IN | 460–479 | ORANGE | The supervisor-confirmed correction sends2 Day Air IN460–479 to ORANGE, superseding the photo PURPLE entry. |

## Remaining review

- [x] Owner approved Easy question wording/explanation style E1–E5 in chat, including the Ground FL versus 2 Day Air service comparison.
- [ ] Owner approves Medium wording/explanations M1–M5.
- [ ] Owner approves Hard wording/explanations H1–H7.
- [ ] Check Spanish wording separately before bilingual Ranked use; existing Practice translation tests do not approve new Ranked copy.
- [ ] Complete canonical identity/overlap/exception handling and immutable bank/assignment versions before implementation.
- [ ] Obtain separate authoritative work-methods questions for tie rounds; this route sheet does not supply them.

Seventeen reviewed labels provide five Easy, five Medium and seven Hard candidates. This is a small initial candidate set, not proof of broad content coverage, fairness, fresh tie sets or an implemented Ranked engine.
