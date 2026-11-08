# Expanded Ranked question wording review

**Status:** original17 bilingual approvals are preserved, and eight expanded entries are now bilingual-approved (25 total). All283 difficulty labels remain settled. The next 188 standard-feedback drafts are proposed for joint English/Spanish review; 70 focused cases remain for separate wording/coverage review. No product code or executable bank is created here.

**Related:** [[2026-11-08-ranked-full-chart-review]], [[2026-11-08-ranked-full-chart-review.json]], [[2026-11-08-ranked-question-wording-review]], [[2026-11-08-ranked-chart-reference]], [[2026-11-08-curated-ranked-bank-design]]. Tracker: [#5](https://github.com/renilsonjr/Sort-Tester-Live/issues/5), [PR #32](https://github.com/renilsonjr/Sort-Tester-Live/pull/32).

Shared prompts retain the approved style: **Which belt does this go to?** / **¿A qué color va?** Service/destination, state and routing code remain separate. This review approves feedback wording only; it does not approve unbuilt assignment behavior.

## Ground — first four expanded entries

| Review reference | Route | Approved English feedback | Approved Spanish feedback |
| --- | --- | --- | --- |
| G01 | Ground · MA, RI · 027–029 | Ground MA/RI 027–029 goes to GOLD. | En Terrestre, MA/RI 027–029 va a GOLD. |
| G02 | Ground · NH · 030–033 | Ground NH 030–033 goes to BLUE. | En Terrestre, NH 030–033 va a BLUE. |
| G03 | Ground · NH · 034 0 | Ground NH 034 0 goes to GOLD. The final digit matters. | En Terrestre, NH 034 0 va a GOLD. El último dígito importa. |
| G04 | Ground · NH, ME · 035–049 | Ground NH/ME 035–049 goes to BLUE. | En Terrestre, NH/ME 035–049 va a BLUE. |

Source review mapping (not permanent canonical IDs):

- G01: `ground-main-mari-027-029`.
- G02: `ground-main-nh-030-033`.
- G03: `ground-main-nh-0340`.
- G04: `ground-main-nhme-035-049`.

- [x] Owner approved these four English explanations in chat.
- [x] Owner approved these four Spanish explanations separately in chat. Both languages are now approved for G01–G04.
- [ ] Complete wording/explanation review for the remaining expanded entries and verify exceptions/coverage.

## Ground — G05–G08 (approved)

These rows already have approved answers/difficulty labels. The owner approved both English and Spanish feedback below in chat.

| Review reference | Route | Approved English feedback | Approved Spanish feedback |
| --- | --- | --- | --- |
| G05 | Ground · NY · 100–108 | Ground NY 100–108 goes to YELLOW. | En Terrestre, NY 100–108 va a YELLOW. |
| G06 | Ground · NY · 109 | Ground NY 109 goes to ORANGE. A destination marked +1 goes to PURPLE. | En Terrestre, NY 109 va a ORANGE. Un destino marcado +1 va a PURPLE. |
| G07 | Ground · NY · 110–119 | Ground NY 110–119 goes to PINK. | En Terrestre, NY 110–119 va a PINK. |
| G08 | Ground · NY · 120–121 | Ground NY 120–121 goes to GOLD. Both 120 and 121 are included. | En Terrestre, NY 120–121 va a GOLD. Se incluyen tanto 120 como 121. |

Source review mapping (not permanent canonical IDs):

- G05: `ground-main-ny-100-108`.
- G06: `ground-main-ny-109`.
- G07: `ground-main-ny-110-119`.
- G08: `ground-main-ny-120-121`.

- [x] Owner approved English explanations G05–G08.
- [x] Owner approved Spanish explanations G05–G08.

## Standard-route feedback batch — proposed (188 entries)

This batch applies the already-reviewed feedback style to ordinary numeric chart directions and listed RED NJ preload codes. English uses “SERVICE STATE CODE goes to BELT.” Spanish uses “En SERVICE, STATE CODE va a BELT.” Codes, leading zeros, service-specific answers and difficulty labels come unchanged from the reviewed source ledger. The original25 bilingual-approved entries are excluded from this batch and are not reopened.

These are feedback drafts pending explicit owner approval in both languages. Service/destination, state and routing code stay separate in the future question display; only the feedback sentence is reviewed here. This grouping is conservative editorial triage, not an executable overlap validator or a new competition rule. Cases with wildcard/qualifier/suffix/exact-code explanation needs, or possible answer-changing exception overlap, remain in the focused queue below. Approving this batch does not approve unbuilt canonical/assignment behavior.

### Ground — 52 proposed explanations

| Review reference | Route | Answer | Proposed English feedback | Proposed Spanish feedback |
| --- | --- | --- | --- | --- |
| G09 | NY 122–127 | ORANGE | Ground NY 122–127 goes to ORANGE. | En Terrestre, NY 122–127 va a ORANGE. |
| G10 | NY 128–139 | GOLD | Ground NY 128–139 goes to GOLD. | En Terrestre, NY 128–139 va a GOLD. |
| G11 | NY 140–147 | GOLD | Ground NY 140–147 goes to GOLD. | En Terrestre, NY 140–147 va a GOLD. |
| G13 | PA 150–167 | GREEN | Ground PA 150–167 goes to GREEN. | En Terrestre, PA 150–167 va a GREEN. |
| G14 | PA 168–178 | GREEN | Ground PA 168–178 goes to GREEN. | En Terrestre, PA 168–178 va a GREEN. |
| G15 | PA 179–189 | GREEN | Ground PA 179–189 goes to GREEN. | En Terrestre, PA 179–189 va a GREEN. |
| G16 | PA 190–194 | ORANGE | Ground PA 190–194 goes to ORANGE. | En Terrestre, PA 190–194 va a ORANGE. |
| G17 | PA, DE 195–199 | GREEN | Ground PA/DE 195–199 goes to GREEN. | En Terrestre, PA/DE 195–199 va a GREEN. |
| G18 | DC, MD 200–219 | GREEN | Ground DC/MD 200–219 goes to GREEN. | En Terrestre, DC/MD 200–219 va a GREEN. |
| G19 | VA 220–238 | YELLOW | Ground VA 220–238 goes to YELLOW. | En Terrestre, VA 220–238 va a YELLOW. |
| G20 | VA, WV 239–269 | YELLOW | Ground VA/WV 239–269 goes to YELLOW. | En Terrestre, VA/WV 239–269 va a YELLOW. |
| G21 | NC, SC 270–299 | YELLOW | Ground NC/SC 270–299 goes to YELLOW. | En Terrestre, NC/SC 270–299 va a YELLOW. |
| G22 | AL 350–369 | BLUE | Ground AL 350–369 goes to BLUE. | En Terrestre, AL 350–369 va a BLUE. |
| G24 | MS 386–399 | BROWN | Ground MS 386–399 goes to BROWN. | En Terrestre, MS 386–399 va a BROWN. |
| G25 | KY 400–429 | BROWN | Ground KY 400–429 goes to BROWN. | En Terrestre, KY 400–429 va a BROWN. |
| G26 | OH 430–459 | ORANGE | Ground OH 430–459 goes to ORANGE. | En Terrestre, OH 430–459 va a ORANGE. |
| G27 | IN 460–479 | ORANGE | Ground IN 460–479 goes to ORANGE. | En Terrestre, IN 460–479 va a ORANGE. |
| G28 | MI 480–497 | ORANGE | Ground MI 480–497 goes to ORANGE. | En Terrestre, MI 480–497 va a ORANGE. |
| G30 | MT 590–599 | ORANGE | Ground MT 590–599 goes to ORANGE. | En Terrestre, MT 590–599 va a ORANGE. |
| G31 | IL 600–608 | YELLOW | Ground IL 600–608 goes to YELLOW. | En Terrestre, IL 600–608 va a YELLOW. |
| G32 | IL 609–619 | ORANGE | Ground IL 609–619 goes to ORANGE. | En Terrestre, IL 609–619 va a ORANGE. |
| G33 | IL 620–629 | ORANGE | Ground IL 620–629 goes to ORANGE. | En Terrestre, IL 620–629 va a ORANGE. |
| G34 | MO, KS 630–674 | BLUE | Ground MO/KS 630–674 goes to BLUE. | En Terrestre, MO/KS 630–674 va a BLUE. |
| G35 | KS 675–679 | ORANGE | Ground KS 675–679 goes to ORANGE. | En Terrestre, KS 675–679 va a ORANGE. |
| G36 | NE 680–689 | BLUE | Ground NE 680–689 goes to BLUE. | En Terrestre, NE 680–689 va a BLUE. |
| G37 | NE 690–699 | ORANGE | Ground NE 690–699 goes to ORANGE. | En Terrestre, NE 690–699 va a ORANGE. |
| G38 | LA, AR 700–729 | BLUE | Ground LA/AR 700–729 goes to BLUE. | En Terrestre, LA/AR 700–729 va a BLUE. |
| G39 | OK 730–734 | ORANGE | Ground OK 730–734 goes to ORANGE. | En Terrestre, OK 730–734 va a ORANGE. |
| G40 | OK 735–749 | ORANGE | Ground OK 735–749 goes to ORANGE. | En Terrestre, OK 735–749 va a ORANGE. |
| G41 | TX 750–779 | BLUE | Ground TX 750–779 goes to BLUE. | En Terrestre, TX 750–779 va a BLUE. |
| G42 | TX 780–784 | BLUE | Ground TX 780–784 goes to BLUE. | En Terrestre, TX 780–784 va a BLUE. |
| G43 | TX 785–799 | ORANGE | Ground TX 785–799 goes to ORANGE. | En Terrestre, TX 785–799 va a ORANGE. |
| G44 | CO, WY 800–831 | ORANGE | Ground CO/WY 800–831 goes to ORANGE. | En Terrestre, CO/WY 800–831 va a ORANGE. |
| G49 | NV 893–899 | ORANGE | Ground NV 893–899 goes to ORANGE. | En Terrestre, NV 893–899 va a ORANGE. |
| G51 | CA 936–961 | BROWN | Ground CA 936–961 goes to BROWN. | En Terrestre, CA 936–961 va a BROWN. |
| G52 | HI 967–968 | ORANGE | Ground HI 967–968 goes to ORANGE. | En Terrestre, HI 967–968 va a ORANGE. |
| G53 | OR, WA 970–994 | BROWN | Ground OR/WA 970–994 goes to BROWN. | En Terrestre, OR/WA 970–994 va a BROWN. |
| G54 | AK 995–999 | BROWN | Ground AK 995–999 goes to BROWN. | En Terrestre, AK 995–999 va a BROWN. |
| G58 | NJ 070 3 | RED | Ground NJ 070 3 goes to RED. | En Terrestre, NJ 070 3 va a RED. |
| G59 | NJ 070 9 | RED | Ground NJ 070 9 goes to RED. | En Terrestre, NJ 070 9 va a RED. |
| G60 | NJ 075 9 | RED | Ground NJ 075 9 goes to RED. | En Terrestre, NJ 075 9 va a RED. |
| G61 | NJ 076 9 | RED | Ground NJ 076 9 goes to RED. | En Terrestre, NJ 076 9 va a RED. |
| G62 | NJ 077 0 | RED | Ground NJ 077 0 goes to RED. | En Terrestre, NJ 077 0 va a RED. |
| G63 | NJ 078 4 | RED | Ground NJ 078 4 goes to RED. | En Terrestre, NJ 078 4 va a RED. |
| G64 | NJ 078 9 | RED | Ground NJ 078 9 goes to RED. | En Terrestre, NJ 078 9 va a RED. |
| G66 | NJ 081 9 | RED | Ground NJ 081 9 goes to RED. | En Terrestre, NJ 081 9 va a RED. |
| G67 | NJ 082 9 | RED | Ground NJ 082 9 goes to RED. | En Terrestre, NJ 082 9 va a RED. |
| G68 | NJ 083 9 | RED | Ground NJ 083 9 goes to RED. | En Terrestre, NJ 083 9 va a RED. |
| G69 | NJ 086 0 | RED | Ground NJ 086 0 goes to RED. | En Terrestre, NJ 086 0 va a RED. |
| G70 | NJ 087 1 | RED | Ground NJ 087 1 goes to RED. | En Terrestre, NJ 087 1 va a RED. |
| G71 | NJ 088 9 | RED | Ground NJ 088 9 goes to RED. | En Terrestre, NJ 088 9 va a RED. |
| G72 | NJ 089 9 | RED | Ground NJ 089 9 goes to RED. | En Terrestre, NJ 089 9 va a RED. |

### 3 Day Select — 52 proposed explanations

| Review reference | Route | Answer | Proposed English feedback | Proposed Spanish feedback |
| --- | --- | --- | --- | --- |
| S01 | MA 010–024 | GOLD | 3 Day Select MA 010–024 goes to GOLD. | En Select 3 días, MA 010–024 va a GOLD. |
| S02 | MA 025–026 | BLUE | 3 Day Select MA 025–026 goes to BLUE. | En Select 3 días, MA 025–026 va a BLUE. |
| S03 | MA, RI 027–029 | GOLD | 3 Day Select MA/RI 027–029 goes to GOLD. | En Select 3 días, MA/RI 027–029 va a GOLD. |
| S04 | NH 030–033 | BLUE | 3 Day Select NH 030–033 goes to BLUE. | En Select 3 días, NH 030–033 va a BLUE. |
| S06 | NH, ME 035–049 | BLUE | 3 Day Select NH/ME 035–049 goes to BLUE. | En Select 3 días, NH/ME 035–049 va a BLUE. |
| S07 | VT 050–059 | GOLD | 3 Day Select VT 050–059 goes to GOLD. | En Select 3 días, VT 050–059 va a GOLD. |
| S08 | CT 060–069 | GOLD | 3 Day Select CT 060–069 goes to GOLD. | En Select 3 días, CT 060–069 va a GOLD. |
| S09 | NY 100–108 | YELLOW | 3 Day Select NY 100–108 goes to YELLOW. | En Select 3 días, NY 100–108 va a YELLOW. |
| S10 | NY 109 | ORANGE | 3 Day Select NY 109 goes to ORANGE. | En Select 3 días, NY 109 va a ORANGE. |
| S11 | NY 110–119 | PINK | 3 Day Select NY 110–119 goes to PINK. | En Select 3 días, NY 110–119 va a PINK. |
| S12 | NY 120–121 | GOLD | 3 Day Select NY 120–121 goes to GOLD. | En Select 3 días, NY 120–121 va a GOLD. |
| S13 | NY 122–127 | ORANGE | 3 Day Select NY 122–127 goes to ORANGE. | En Select 3 días, NY 122–127 va a ORANGE. |
| S14 | NY 128–139 | GOLD | 3 Day Select NY 128–139 goes to GOLD. | En Select 3 días, NY 128–139 va a GOLD. |
| S15 | NY 140–147 | ORANGE | 3 Day Select NY 140–147 goes to ORANGE. | En Select 3 días, NY 140–147 va a ORANGE. |
| S17 | PA 150–167 | GREEN | 3 Day Select PA 150–167 goes to GREEN. | En Select 3 días, PA 150–167 va a GREEN. |
| S18 | PA 168–178 | GREEN | 3 Day Select PA 168–178 goes to GREEN. | En Select 3 días, PA 168–178 va a GREEN. |
| S19 | PA 179–189 | GREEN | 3 Day Select PA 179–189 goes to GREEN. | En Select 3 días, PA 179–189 va a GREEN. |
| S20 | PA 190–194 | ORANGE | 3 Day Select PA 190–194 goes to ORANGE. | En Select 3 días, PA 190–194 va a ORANGE. |
| S21 | PA, DE 195–199 | GREEN | 3 Day Select PA/DE 195–199 goes to GREEN. | En Select 3 días, PA/DE 195–199 va a GREEN. |
| S22 | DC, MD 200–219 | GREEN | 3 Day Select DC/MD 200–219 goes to GREEN. | En Select 3 días, DC/MD 200–219 va a GREEN. |
| S23 | VA 220–238 | YELLOW | 3 Day Select VA 220–238 goes to YELLOW. | En Select 3 días, VA 220–238 va a YELLOW. |
| S24 | VA, WV 239–269 | YELLOW | 3 Day Select VA/WV 239–269 goes to YELLOW. | En Select 3 días, VA/WV 239–269 va a YELLOW. |
| S25 | NC, SC 270–299 | YELLOW | 3 Day Select NC/SC 270–299 goes to YELLOW. | En Select 3 días, NC/SC 270–299 va a YELLOW. |
| S26 | GA 300–319 | BLUE | 3 Day Select GA 300–319 goes to BLUE. | En Select 3 días, GA 300–319 va a BLUE. |
| S27 | FL 320–349 | PINK | 3 Day Select FL 320–349 goes to PINK. | En Select 3 días, FL 320–349 va a PINK. |
| S28 | TN 370–385 | BROWN | 3 Day Select TN 370–385 goes to BROWN. | En Select 3 días, TN 370–385 va a BROWN. |
| S30 | KY 400–429 | BROWN | 3 Day Select KY 400–429 goes to BROWN. | En Select 3 días, KY 400–429 va a BROWN. |
| S31 | OH 430–459 | ORANGE | 3 Day Select OH 430–459 goes to ORANGE. | En Select 3 días, OH 430–459 va a ORANGE. |
| S32 | IN 460–479 | ORANGE | 3 Day Select IN 460–479 goes to ORANGE. | En Select 3 días, IN 460–479 va a ORANGE. |
| S33 | MI 480–497 | ORANGE | 3 Day Select MI 480–497 goes to ORANGE. | En Select 3 días, MI 480–497 va a ORANGE. |
| S36 | IL 600–608 | YELLOW | 3 Day Select IL 600–608 goes to YELLOW. | En Select 3 días, IL 600–608 va a YELLOW. |
| S37 | IL 609–629 | ORANGE | 3 Day Select IL 609–629 goes to ORANGE. | En Select 3 días, IL 609–629 va a ORANGE. |
| S38 | MO, KS 630–674 | BLUE | 3 Day Select MO/KS 630–674 goes to BLUE. | En Select 3 días, MO/KS 630–674 va a BLUE. |
| S39 | KS 675–679 | ORANGE | 3 Day Select KS 675–679 goes to ORANGE. | En Select 3 días, KS 675–679 va a ORANGE. |
| S40 | NE 680–689 | BLUE | 3 Day Select NE 680–689 goes to BLUE. | En Select 3 días, NE 680–689 va a BLUE. |
| S41 | NE 690–699 | ORANGE | 3 Day Select NE 690–699 goes to ORANGE. | En Select 3 días, NE 690–699 va a ORANGE. |
| S43 | OK 735–749 | ORANGE | 3 Day Select OK 735–749 goes to ORANGE. | En Select 3 días, OK 735–749 va a ORANGE. |
| S46 | CO 800–810 | ORANGE | 3 Day Select CO 800–810 goes to ORANGE. | En Select 3 días, CO 800–810 va a ORANGE. |
| S48 | NJ 070 3 | RED | 3 Day Select NJ 070 3 goes to RED. | En Select 3 días, NJ 070 3 va a RED. |
| S49 | NJ 070 9 | RED | 3 Day Select NJ 070 9 goes to RED. | En Select 3 días, NJ 070 9 va a RED. |
| S50 | NJ 075 9 | RED | 3 Day Select NJ 075 9 goes to RED. | En Select 3 días, NJ 075 9 va a RED. |
| S51 | NJ 076 9 | RED | 3 Day Select NJ 076 9 goes to RED. | En Select 3 días, NJ 076 9 va a RED. |
| S52 | NJ 077 0 | RED | 3 Day Select NJ 077 0 goes to RED. | En Select 3 días, NJ 077 0 va a RED. |
| S53 | NJ 078 4 | RED | 3 Day Select NJ 078 4 goes to RED. | En Select 3 días, NJ 078 4 va a RED. |
| S54 | NJ 078 9 | RED | 3 Day Select NJ 078 9 goes to RED. | En Select 3 días, NJ 078 9 va a RED. |
| S56 | NJ 081 9 | RED | 3 Day Select NJ 081 9 goes to RED. | En Select 3 días, NJ 081 9 va a RED. |
| S57 | NJ 082 9 | RED | 3 Day Select NJ 082 9 goes to RED. | En Select 3 días, NJ 082 9 va a RED. |
| S58 | NJ 083 9 | RED | 3 Day Select NJ 083 9 goes to RED. | En Select 3 días, NJ 083 9 va a RED. |
| S59 | NJ 086 0 | RED | 3 Day Select NJ 086 0 goes to RED. | En Select 3 días, NJ 086 0 va a RED. |
| S60 | NJ 087 1 | RED | 3 Day Select NJ 087 1 goes to RED. | En Select 3 días, NJ 087 1 va a RED. |
| S61 | NJ 088 9 | RED | 3 Day Select NJ 088 9 goes to RED. | En Select 3 días, NJ 088 9 va a RED. |
| S62 | NJ 089 9 | RED | 3 Day Select NJ 089 9 goes to RED. | En Select 3 días, NJ 089 9 va a RED. |

### 2 Day Air — 48 proposed explanations

| Review reference | Route | Answer | Proposed English feedback | Proposed Spanish feedback |
| --- | --- | --- | --- | --- |
| D01 | MA 010–024 | GOLD | 2 Day Air MA 010–024 goes to GOLD. | En Aéreo 2 días, MA 010–024 va a GOLD. |
| D02 | MA 025–026 | BLUE | 2 Day Air MA 025–026 goes to BLUE. | En Aéreo 2 días, MA 025–026 va a BLUE. |
| D03 | MA, RI 027–029 | GOLD | 2 Day Air MA/RI 027–029 goes to GOLD. | En Aéreo 2 días, MA/RI 027–029 va a GOLD. |
| D04 | NH 030–033 | BLUE | 2 Day Air NH 030–033 goes to BLUE. | En Aéreo 2 días, NH 030–033 va a BLUE. |
| D06 | NH, ME 035–049 | BLUE | 2 Day Air NH/ME 035–049 goes to BLUE. | En Aéreo 2 días, NH/ME 035–049 va a BLUE. |
| D07 | VT 050–059 | GOLD | 2 Day Air VT 050–059 goes to GOLD. | En Aéreo 2 días, VT 050–059 va a GOLD. |
| D08 | CT 060–069 | GOLD | 2 Day Air CT 060–069 goes to GOLD. | En Aéreo 2 días, CT 060–069 va a GOLD. |
| D09 | NY 100–108 | YELLOW | 2 Day Air NY 100–108 goes to YELLOW. | En Aéreo 2 días, NY 100–108 va a YELLOW. |
| D10 | NY 109 | ORANGE | 2 Day Air NY 109 goes to ORANGE. | En Aéreo 2 días, NY 109 va a ORANGE. |
| D11 | NY 110–119 | PINK | 2 Day Air NY 110–119 goes to PINK. | En Aéreo 2 días, NY 110–119 va a PINK. |
| D12 | NY 120–121 | GOLD | 2 Day Air NY 120–121 goes to GOLD. | En Aéreo 2 días, NY 120–121 va a GOLD. |
| D13 | NY 122–127 | ORANGE | 2 Day Air NY 122–127 goes to ORANGE. | En Aéreo 2 días, NY 122–127 va a ORANGE. |
| D14 | NY 128–139 | GOLD | 2 Day Air NY 128–139 goes to GOLD. | En Aéreo 2 días, NY 128–139 va a GOLD. |
| D16 | PA 150–167 | GREEN | 2 Day Air PA 150–167 goes to GREEN. | En Aéreo 2 días, PA 150–167 va a GREEN. |
| D17 | PA 168–178 | GREEN | 2 Day Air PA 168–178 goes to GREEN. | En Aéreo 2 días, PA 168–178 va a GREEN. |
| D18 | PA 179–189 | GREEN | 2 Day Air PA 179–189 goes to GREEN. | En Aéreo 2 días, PA 179–189 va a GREEN. |
| D19 | PA 190–194 | ORANGE | 2 Day Air PA 190–194 goes to ORANGE. | En Aéreo 2 días, PA 190–194 va a ORANGE. |
| D20 | PA, DE 195–199 | GREEN | 2 Day Air PA/DE 195–199 goes to GREEN. | En Aéreo 2 días, PA/DE 195–199 va a GREEN. |
| D21 | DC, MD 200–219 | GREEN | 2 Day Air DC/MD 200–219 goes to GREEN. | En Aéreo 2 días, DC/MD 200–219 va a GREEN. |
| D22 | VA 220–238 | YELLOW | 2 Day Air VA 220–238 goes to YELLOW. | En Aéreo 2 días, VA 220–238 va a YELLOW. |
| D23 | VA, WV 239–269 | YELLOW | 2 Day Air VA/WV 239–269 goes to YELLOW. | En Aéreo 2 días, VA/WV 239–269 va a YELLOW. |
| D24 | NC, SC 270–299 | YELLOW | 2 Day Air NC/SC 270–299 goes to YELLOW. | En Aéreo 2 días, NC/SC 270–299 va a YELLOW. |
| D25 | GA 300–319 | BLUE | 2 Day Air GA 300–319 goes to BLUE. | En Aéreo 2 días, GA 300–319 va a BLUE. |
| D26 | AL 350–369 | PURPLE | 2 Day Air AL 350–369 goes to PURPLE. | En Aéreo 2 días, AL 350–369 va a PURPLE. |
| D27 | TN 370–385 | BROWN | 2 Day Air TN 370–385 goes to BROWN. | En Aéreo 2 días, TN 370–385 va a BROWN. |
| D28 | MS 386–399 | PURPLE | 2 Day Air MS 386–399 goes to PURPLE. | En Aéreo 2 días, MS 386–399 va a PURPLE. |
| D29 | KY 400–419 | BROWN | 2 Day Air KY 400–419 goes to BROWN. | En Aéreo 2 días, KY 400–419 va a BROWN. |
| D30 | KY 420 | PURPLE | 2 Day Air KY 420 goes to PURPLE. | En Aéreo 2 días, KY 420 va a PURPLE. |
| D31 | KY 421–429 | BROWN | 2 Day Air KY 421–429 goes to BROWN. | En Aéreo 2 días, KY 421–429 va a BROWN. |
| D32 | OH 430–459 | ORANGE | 2 Day Air OH 430–459 goes to ORANGE. | En Aéreo 2 días, OH 430–459 va a ORANGE. |
| D33 | MI 480–497 | ORANGE | 2 Day Air MI 480–497 goes to ORANGE. | En Aéreo 2 días, MI 480–497 va a ORANGE. |
| D35 | MO 630–639 | BLUE | 2 Day Air MO 630–639 goes to BLUE. | En Aéreo 2 días, MO 630–639 va a BLUE. |
| D37 | OK 730–740 | PURPLE | 2 Day Air OK 730–740 goes to PURPLE. | En Aéreo 2 días, OK 730–740 va a PURPLE. |
| D39 | OK 742–749 | PURPLE | 2 Day Air OK 742–749 goes to PURPLE. | En Aéreo 2 días, OK 742–749 va a PURPLE. |
| D42 | NJ 070 3 | RED | 2 Day Air NJ 070 3 goes to RED. | En Aéreo 2 días, NJ 070 3 va a RED. |
| D43 | NJ 070 9 | RED | 2 Day Air NJ 070 9 goes to RED. | En Aéreo 2 días, NJ 070 9 va a RED. |
| D44 | NJ 075 9 | RED | 2 Day Air NJ 075 9 goes to RED. | En Aéreo 2 días, NJ 075 9 va a RED. |
| D45 | NJ 076 9 | RED | 2 Day Air NJ 076 9 goes to RED. | En Aéreo 2 días, NJ 076 9 va a RED. |
| D46 | NJ 077 0 | RED | 2 Day Air NJ 077 0 goes to RED. | En Aéreo 2 días, NJ 077 0 va a RED. |
| D47 | NJ 078 4 | RED | 2 Day Air NJ 078 4 goes to RED. | En Aéreo 2 días, NJ 078 4 va a RED. |
| D48 | NJ 078 9 | RED | 2 Day Air NJ 078 9 goes to RED. | En Aéreo 2 días, NJ 078 9 va a RED. |
| D50 | NJ 081 9 | RED | 2 Day Air NJ 081 9 goes to RED. | En Aéreo 2 días, NJ 081 9 va a RED. |
| D51 | NJ 082 9 | RED | 2 Day Air NJ 082 9 goes to RED. | En Aéreo 2 días, NJ 082 9 va a RED. |
| D52 | NJ 083 9 | RED | 2 Day Air NJ 083 9 goes to RED. | En Aéreo 2 días, NJ 083 9 va a RED. |
| D53 | NJ 086 0 | RED | 2 Day Air NJ 086 0 goes to RED. | En Aéreo 2 días, NJ 086 0 va a RED. |
| D54 | NJ 087 1 | RED | 2 Day Air NJ 087 1 goes to RED. | En Aéreo 2 días, NJ 087 1 va a RED. |
| D55 | NJ 088 9 | RED | 2 Day Air NJ 088 9 goes to RED. | En Aéreo 2 días, NJ 088 9 va a RED. |
| D56 | NJ 089 9 | RED | 2 Day Air NJ 089 9 goes to RED. | En Aéreo 2 días, NJ 089 9 va a RED. |

### Next Day Air — 36 proposed explanations

| Review reference | Route | Answer | Proposed English feedback | Proposed Spanish feedback |
| --- | --- | --- | --- | --- |
| N01 | MA 010–024 | GOLD | Next Day Air MA 010–024 goes to GOLD. | En Aéreo 1 día, MA 010–024 va a GOLD. |
| N02 | MA 025–026 | PURPLE | Next Day Air MA 025–026 goes to PURPLE. | En Aéreo 1 día, MA 025–026 va a PURPLE. |
| N03 | MA, RI 027–029 | GOLD | Next Day Air MA/RI 027–029 goes to GOLD. | En Aéreo 1 día, MA/RI 027–029 va a GOLD. |
| N04 | NH 030–033 | PURPLE | Next Day Air NH 030–033 goes to PURPLE. | En Aéreo 1 día, NH 030–033 va a PURPLE. |
| N06 | NH, ME 035–049 | PURPLE | Next Day Air NH/ME 035–049 goes to PURPLE. | En Aéreo 1 día, NH/ME 035–049 va a PURPLE. |
| N07 | VT 050–059 | GOLD | Next Day Air VT 050–059 goes to GOLD. | En Aéreo 1 día, VT 050–059 va a GOLD. |
| N08 | CT 060–069 | GOLD | Next Day Air CT 060–069 goes to GOLD. | En Aéreo 1 día, CT 060–069 va a GOLD. |
| N09 | NY 100–108 | YELLOW | Next Day Air NY 100–108 goes to YELLOW. | En Aéreo 1 día, NY 100–108 va a YELLOW. |
| N10 | NY 109 | ORANGE | Next Day Air NY 109 goes to ORANGE. | En Aéreo 1 día, NY 109 va a ORANGE. |
| N11 | NY 110–119 | PINK | Next Day Air NY 110–119 goes to PINK. | En Aéreo 1 día, NY 110–119 va a PINK. |
| N12 | NY 120–121 | GOLD | Next Day Air NY 120–121 goes to GOLD. | En Aéreo 1 día, NY 120–121 va a GOLD. |
| N13 | NY 122–127 | ORANGE | Next Day Air NY 122–127 goes to ORANGE. | En Aéreo 1 día, NY 122–127 va a ORANGE. |
| N14 | NY 128–135 | GOLD | Next Day Air NY 128–135 goes to GOLD. | En Aéreo 1 día, NY 128–135 va a GOLD. |
| N15 | NY 136 | PURPLE | Next Day Air NY 136 goes to PURPLE. | En Aéreo 1 día, NY 136 va a PURPLE. |
| N16 | NY 137–139 | GOLD | Next Day Air NY 137–139 goes to GOLD. | En Aéreo 1 día, NY 137–139 va a GOLD. |
| N17 | NY 140–149 | PURPLE | Next Day Air NY 140–149 goes to PURPLE. | En Aéreo 1 día, NY 140–149 va a PURPLE. |
| N18 | PA 150–167 | PURPLE | Next Day Air PA 150–167 goes to PURPLE. | En Aéreo 1 día, PA 150–167 va a PURPLE. |
| N19 | PA 168–178 | GREEN | Next Day Air PA 168–178 goes to GREEN. | En Aéreo 1 día, PA 168–178 va a GREEN. |
| N20 | PA 179–189 | GREEN | Next Day Air PA 179–189 goes to GREEN. | En Aéreo 1 día, PA 179–189 va a GREEN. |
| N21 | PA 190–194 | ORANGE | Next Day Air PA 190–194 goes to ORANGE. | En Aéreo 1 día, PA 190–194 va a ORANGE. |
| N22 | PA, DE 195–199 | GREEN | Next Day Air PA/DE 195–199 goes to GREEN. | En Aéreo 1 día, PA/DE 195–199 va a GREEN. |
| N23 | DC, MD 200–219 | GREEN | Next Day Air DC/MD 200–219 goes to GREEN. | En Aéreo 1 día, DC/MD 200–219 va a GREEN. |
| N27 | NJ 070 3 | RED | Next Day Air NJ 070 3 goes to RED. | En Aéreo 1 día, NJ 070 3 va a RED. |
| N28 | NJ 070 9 | RED | Next Day Air NJ 070 9 goes to RED. | En Aéreo 1 día, NJ 070 9 va a RED. |
| N29 | NJ 075 9 | RED | Next Day Air NJ 075 9 goes to RED. | En Aéreo 1 día, NJ 075 9 va a RED. |
| N30 | NJ 076 9 | RED | Next Day Air NJ 076 9 goes to RED. | En Aéreo 1 día, NJ 076 9 va a RED. |
| N31 | NJ 077 0 | RED | Next Day Air NJ 077 0 goes to RED. | En Aéreo 1 día, NJ 077 0 va a RED. |
| N32 | NJ 078 4 | RED | Next Day Air NJ 078 4 goes to RED. | En Aéreo 1 día, NJ 078 4 va a RED. |
| N33 | NJ 078 9 | RED | Next Day Air NJ 078 9 goes to RED. | En Aéreo 1 día, NJ 078 9 va a RED. |
| N35 | NJ 081 9 | RED | Next Day Air NJ 081 9 goes to RED. | En Aéreo 1 día, NJ 081 9 va a RED. |
| N36 | NJ 082 9 | RED | Next Day Air NJ 082 9 goes to RED. | En Aéreo 1 día, NJ 082 9 va a RED. |
| N37 | NJ 083 9 | RED | Next Day Air NJ 083 9 goes to RED. | En Aéreo 1 día, NJ 083 9 va a RED. |
| N38 | NJ 086 0 | RED | Next Day Air NJ 086 0 goes to RED. | En Aéreo 1 día, NJ 086 0 va a RED. |
| N39 | NJ 087 1 | RED | Next Day Air NJ 087 1 goes to RED. | En Aéreo 1 día, NJ 087 1 va a RED. |
| N40 | NJ 088 9 | RED | Next Day Air NJ 088 9 goes to RED. | En Aéreo 1 día, NJ 088 9 va a RED. |
| N41 | NJ 089 9 | RED | Next Day Air NJ 089 9 goes to RED. | En Aéreo 1 día, NJ 089 9 va a RED. |

- [ ] Owner approves the standard-feedback batch in English.
- [ ] Owner approves the standard-feedback batch in Spanish.

## Focused wording queue — 70 entries

These entries are not included in the standard batch. Possible prefix overlap is only a reason to review; it does not establish that a different-state exception actually applies. Confirm coverage before adding exclusions. No new wording approval is inferred here.

| Review reference | Service | Source state / code | Answer | Review need |
| --- | --- | --- | --- | --- |
| G12 | Ground | NY 148–149 | ORANGE | Conservative prefix-overlap hold for H4: verify actual state/context applicability before drafting exclusions. |
| G23 | Ground | TN 370–385 | BROWN | Conservative prefix-overlap hold for H3: verify actual state/context applicability before drafting exclusions. |
| G29 | Ground | * 498–589 | BROWN | Wildcard or named destination: review its scope and any explicit exception wording. |
| G45 | Ground | ID 832–839 | BROWN | Conservative prefix-overlap hold for G74: verify actual state/context applicability before drafting exclusions. |
| G46 | Ground | UT 840–849 | ORANGE | Conservative prefix-overlap hold for G75: verify actual state/context applicability before drafting exclusions. |
| G47 | Ground | AZ, NM 850–884 | BLUE | Conservative prefix-overlap hold for G76: verify actual state/context applicability before drafting exclusions. |
| G48 | Ground | NV 889–891 | BLUE | Conservative prefix-overlap hold for G77: verify actual state/context applicability before drafting exclusions. |
| G50 | Ground | CA 900–935 | RED | Conservative prefix-overlap hold for G78: verify actual state/context applicability before drafting exclusions. |
| G55 | Ground | MEX MEXICO | GREEN | Exact code or named destination: review wording that preserves the source meaning. |
| G56 | Ground | CAN CANADA | PURPLE | Exact code or named destination: review wording that preserves the source meaning. |
| G57 | Ground | PRI PR | PINK | Exact code or named destination: review wording that preserves the source meaning. |
| G65 | Ground | NJ 079 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| G73 | Ground | NE 575 3-6 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| G74 | Ground | NV 833 9-7 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| G75 | Ground | AZ 847 2-7 | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| G76 | Ground | NV 864 4-7 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| G77 | Ground | NV 890 0-0 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| G78 | Ground | AZ 922 2-0 | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| G79 | Ground | Any state ends 2S | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| G80 | Ground | Any state ends 1S | PURPLE | Specific exception or suffix: review its explanatory wording separately. |
| S05 | 3 Day Select | NH 034 0 | GOLD | Exact code or named destination: review wording that preserves the source meaning. |
| S16 | 3 Day Select | NY 148–149 | ORANGE | Conservative prefix-overlap hold for S79: verify actual state/context applicability before drafting exclusions. |
| S29 | 3 Day Select | MS 386–399 | BROWN | Conservative prefix-overlap hold for S63: verify actual state/context applicability before drafting exclusions. |
| S34 | 3 Day Select | * 498–566 | BROWN | Wildcard or named destination: review its scope and any explicit exception wording. |
| S35 | 3 Day Select | * 567–599 | BLUE | Wildcard or named destination: review its scope and any explicit exception wording. |
| S42 | 3 Day Select | * 700–734 | BLUE | Wildcard or named destination: review its scope and any explicit exception wording. |
| S44 | 3 Day Select | TX 769 0 | PURPLE | Exact code or named destination: review wording that preserves the source meaning. |
| S45 | 3 Day Select | TX 785–799 | PURPLE | Conservative prefix-overlap hold for S68, S69, S70, S71: verify actual state/context applicability before drafting exclusions. |
| S47 | 3 Day Select | * 811–999 | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| S55 | 3 Day Select | NJ 079 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S63 | 3 Day Select | MS 395 0 | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| S64 | 3 Day Select | SD 511 9 | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| S65 | 3 Day Select | SD 571 9 | BROWN | Specific exception or suffix: review its explanatory wording separately. |
| S66 | 3 Day Select | ND 581 9 | BROWN | Specific exception or suffix: review its explanatory wording separately. |
| S67 | 3 Day Select | ND 582 0 | BROWN | Specific exception or suffix: review its explanatory wording separately. |
| S68 | 3 Day Select | TX 786 4 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S69 | 3 Day Select | TX 787 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S70 | 3 Day Select | TX 796 0 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S71 | 3 Day Select | TX 799 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S72 | 3 Day Select | CO 811 3 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S73 | 3 Day Select | CO 812 0 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S74 | 3 Day Select | CO 813 7 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S75 | 3 Day Select | CO 816 0 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S76 | 3 Day Select | CO 816 1 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S77 | 3 Day Select | WY 820 0 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S78 | 3 Day Select | WY 820 1 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| S79 | 3 Day Select | NY 148 1 | GOLD | Specific exception or suffix: review its explanatory wording separately. |
| S80 | 3 Day Select | Any state ends 2S | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| S81 | 3 Day Select | Any state ends 1S | PURPLE | Specific exception or suffix: review its explanatory wording separately. |
| D05 | 2 Day Air | NH 034 0 | GOLD | Exact code or named destination: review wording that preserves the source meaning. |
| D15 | 2 Day Air | NY 148–149 | ORANGE | Conservative prefix-overlap hold for D57: verify actual state/context applicability before drafting exclusions. |
| D34 | 2 Day Air | * 498–599 | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| D36 | 2 Day Air | * 640–729 | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| D38 | 2 Day Air | OK 741 9 | ORANGE | Exact code or named destination: review wording that preserves the source meaning. |
| D40 | 2 Day Air | * 750–999 | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| D41 | 2 Day Air | * WORLD | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| D49 | 2 Day Air | NJ 079 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| D57 | 2 Day Air | NY 148 1 | GOLD | Specific exception or suffix: review its explanatory wording separately. |
| D58 | 2 Day Air | Any state ends 2S | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| D59 | 2 Day Air | Any state ends 1S | PURPLE | Specific exception or suffix: review its explanatory wording separately. |
| N05 | Next Day Air | NH 034 0 | GOLD | Exact code or named destination: review wording that preserves the source meaning. |
| N24 | Next Day Air | * 220–999 | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| N25 | Next Day Air | * WORLD | PURPLE | Wildcard or named destination: review its scope and any explicit exception wording. |
| N26 | Next Day Air | * ALL 1DA EAM | PURPLE | Service qualifier: review EAM destination presentation with separate routing field. |
| N34 | Next Day Air | NJ 079 9 | ORANGE | Specific exception or suffix: review its explanatory wording separately. |
| N42 | Next Day Air | Any state ends 2S | BLUE | Specific exception or suffix: review its explanatory wording separately. |
| N43 | Next Day Air | Any state ends 1S | PURPLE | Specific exception or suffix: review its explanatory wording separately. |
| N44 | Next Day Air | NY 109 | PURPLE | Destination modifier: review field separation and global scope. |
| D60 | 2 Day Air | NY 109 | PURPLE | Destination modifier: review field separation and global scope. |
| S82 | 3 Day Select | NY 109 | PURPLE | Destination modifier: review field separation and global scope. |

## Current wording counts

Including the original17:25 English and25 Spanish explanations are approved, with258 pending in each language. Twenty-five entries have both languages approved. Of the remaining258, 188 have standard-feedback drafts and 70 remain in focused wording review. All283 answers/difficulty labels are unchanged; no original approval is reopened. Only work-methods tie-question content is deferred; other tie-break policies remain unchanged.
