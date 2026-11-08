# Ranked question wording and explanation review

**Status:** owner approved the English question wording/explanations for all17 route scenarios in three separate group reviews, in addition to the previously reviewed answers/difficulty labels. The owner subsequently approved the Spanish translations for all17 scenarios in separate Easy/Medium/Hard reviews. This does not approve a canonical schema, immutable assignments or a usable Ranked bank. Source revision: `twilight-2026-11-08-r2`, including the owner Indiana ORANGE override, pending publication through [PR #32](https://github.com/renilsonjr/Sort-Tester-Live/pull/32).

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

## Spanish wording draft

**Owner-approved style:** prompt “¿A qué color va?”, Ground translated as “Terrestre”, belt names unchanged (GOLD, BLUE, etc.), and concise service-specific feedback. The owner separately approved all three translation groups below; this is explicit content approval, beyond the earlier style approval. Service translations follow existing Practice labels.

Use the same review labels, service/state/routing data, answer and difficulty as the English scenarios. Translation does not create another canonical question or additional assignment slot. This is draft content, not a product implementation.

| Review label | Servicio / destino | Estado | Código de ruta | Respuesta | Explicación propuesta |
| --- | --- | --- | --- | --- | --- |
| E1 | Terrestre | MA | 010–024 | GOLD | En Terrestre, MA 010–024 va a GOLD. |
| E2 | Terrestre | GA | 300–319 | BLUE | En Terrestre, GA 300–319 va a BLUE. |
| E3 | Terrestre | FL | 320–349 | PINK | En Terrestre, FL 320–349 va a PINK. En Aéreo 2 días, este rango va a PURPLE. |
| E4 | Terrestre | VT | 050–059 | GOLD | En Terrestre, VT 050–059 va a GOLD. |
| E5 | Terrestre | CT | 060–069 | GOLD | En Terrestre, CT 060–069 va a GOLD. |
| M1 | Select 3 días | TX | 770–784 | BLUE | En Select 3 días, TX 770–784 va a BLUE. El código cercano TX 769 0 y el rango 785–799 van a PURPLE. |
| M2 | Aéreo 2 días | NY | 140–147 | ORANGE | En Aéreo 2 días, NY 140–147 va a ORANGE. El cambio a GOLD se aplica solo a Terrestre. |
| M3 | Select 3 días | TX | 750–768 | BLUE | En Select 3 días, TX 750–768 va a BLUE. El siguiente código indicado, TX 769 0, va a PURPLE. |
| M4 | Aéreo 2 días | FL | 320–349 | PURPLE | En Aéreo 2 días, FL 320–349 va a PURPLE. En Terrestre y Select 3 días, este rango va a PINK. |
| M5 | Select 3 días | AL | 350–369 | BLUE | En Select 3 días, AL 350–369 va a BLUE. En Aéreo 2 días, el mismo rango va a PURPLE. |
| H1 | Aéreo 2 días | IL | 600–608 | YELLOW | En Aéreo 2 días, IL 600–608 va a YELLOW. El siguiente rango, 609–629, va a ORANGE. |
| H2 | Aéreo 2 días | IL | 609–629 | ORANGE | En Aéreo 2 días, IL 609–629 va a ORANGE. El rango anterior, 600–608, va a YELLOW. |
| H3 | Terrestre | TN | 376–378 | BLUE | En Terrestre, TN 376–378 es la excepción BLUE dentro del rango 370–385, que normalmente va a BROWN. |
| H4 | Terrestre | NY | 148 1 | GOLD | En Terrestre, NY 148 1 es la excepción GOLD a la regla habitual ORANGE de 148–149. El último dígito importa. |
| H5 | Terrestre +1 | NY | 109 | PURPLE | El indicador de destino +1 va a PURPLE en los cuatro servicios. Sin +1, NY 109 en Terrestre va a ORANGE. El código de ruta sigue siendo 109. |
| H6 | Terrestre | MA | 025–026 | BLUE | En Terrestre, MA 025–026 va a BLUE. En Aéreo 1 día, este rango va a PURPLE. |
| H7 | Aéreo 2 días | IN | 460–479 | ORANGE | La corrección confirmada por el supervisor indica que IN 460–479 en Aéreo 2 días va a ORANGE y reemplaza la indicación PURPLE de la foto. |

## Remaining review

- [x] Owner approved Easy question wording/explanation style E1–E5 in chat, including the Ground FL versus 2 Day Air service comparison.
- [x] Owner approved Medium wording/explanations M1–M5 in chat, including the service comparisons and Texas boundary explanations.
- [x] Owner approved Hard wording/explanations H1–H7 in chat, including exact-code exceptions, destination +1 and the Indiana owner override.
- [x] Owner approved the Spanish translation style separately; individual translations still require review.
- [x] Owner approved Spanish Easy translations E1–E5 in chat, including the Florida service comparison.
- [x] Owner approved Spanish Medium translations M1–M5 in chat, including the Texas boundaries and service comparisons.
- [x] Owner approved Spanish Hard translations H1–H7 in chat, including exact-code exceptions, destination +1 and the Indiana correction. Existing Practice translation tests do not approve this new Ranked copy.
- [ ] Complete canonical identity/overlap/exception handling and immutable bank/assignment versions before implementation.
- [ ] **Deferred at the owner’s request:** obtain separate authoritative work-methods questions for tie rounds. Resume this content review later; this route sheet does not supply or replace that bank. Existing tie-break rules and the approved owner-selection fallback remain unchanged pending any explicit new decision.

Seventeen reviewed labels provide five Easy, five Medium and seven Hard candidates. This is a small initial candidate set, not proof of broad content coverage, fairness, fresh tie sets or an implemented Ranked engine.
