import { COMMON_CORE, NJ_TWILIGHT } from './questions.js?v=tn-370-brown-20261105';
import { LEVEL_DECKS } from './levels.js?v=tn-370-brown-20261105';

// Every deck here is transcribed from the Saddle Brook primary sort chart with
// the SORT CHANGE sheet applied.
//
// The six familiar decks remain available. The two Common Missorts sets share
// eleven cards but use different NJ examples under one Twilight answer rule.
//
// New York was confirmed correct against the real sheet by the supervisor on
// 2026-09-16. Next Day Air, 2 Day Air and 3 Day Select were unlocked on the
// supervisor's instruction without a row-by-row check, so a wrong belt in
// those three is still possible. The verified flag gates a deck out of the
// picker: set one back to false if a section needs pulling.

const NEW_YORK = [
  {
    id: 'ny-109-gnd-nyc',
    svc: 'GND', state: 'NY', code: '109',
    belt: 'ORANGE',
    confusions: ['YELLOW', 'PINK', 'GOLD'],
    why: 'One code sitting alone between 100-108 YELLOW and 110-119 PINK.',
    tags: ['boundary'],
  },
  {
    id: 'ny-110-119-gnd',
    svc: 'GND', state: 'NY', code: '110-119',
    belt: 'PINK',
    confusions: ['ORANGE', 'GOLD', 'YELLOW'],
    why: 'The only PINK block in the New York run. 109 above it is ORANGE and 120-121 below it is GOLD.',
    tags: ['boundary'],
  },
  {
    id: 'ny-100-108-gnd',
    svc: 'GND', state: 'NY', code: '100-108',
    belt: 'YELLOW',
    confusions: ['ORANGE', 'PINK', 'GOLD'],
    why: 'YELLOW runs only to 108. The single code 109 next to it breaks to ORANGE.',
    tags: ['boundary'],
  },
  {
    id: 'ny-120-121-all',
    svc: 'ALL', state: 'NY', code: '120-121',
    belt: 'GOLD',
    confusions: ['PINK', 'ORANGE', 'YELLOW'],
    why: 'The sort change made 120-121 GOLD on every service. 121 used to sit in the 110-119 PINK zone.',
    tags: ['sort-change', 'boundary'],
  },
  {
    id: 'ny-128-139-gnd',
    svc: 'GND', state: 'NY', code: '128-139',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: 'GOLD on Ground. The new GOLD block at 140-147 continues above it, while 122-127 below it is ORANGE. On Next Day Air the single code 136 is PURPLE.',
    tags: ['boundary'],
  },
  {
    id: 'ny-140-147-gnd',
    svc: 'GND', state: 'NY', code: '140-147',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: 'The recent sort change sends 140-147 to GOLD on Ground, 2 Day Air and 3 Day Select. The next block, 148-149, is ORANGE except 148 1.',
    tags: ['sort-change', 'boundary'],
  },
  {
    id: 'ny-148-149-gnd-nyc',
    svc: 'GND', state: 'NY', code: '148-149',
    belt: 'ORANGE',
    confusions: ['GOLD', 'PURPLE', 'PINK'],
    why: 'ORANGE on Ground, 2 Day Air and 3 Day Select. The preceding 140-147 block is now GOLD, and the single code 148 1 is GOLD too.',
    tags: ['boundary'],
  },
  {
    id: 'ny-148-1-gnd-nyc',
    svc: 'GND', state: 'NY', code: '148 1',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: 'This single code remains GOLD inside the ORANGE 148-149 block. The preceding 140-147 block is also GOLD on Ground, 2 Day Air and 3 Day Select.',
    tags: ['sort-change', 'exception'],
  },
  {
    id: 'ny-136-nda-nyc',
    svc: 'NDA', state: 'NY', code: '136',
    belt: 'PURPLE',
    confusions: ['GOLD', 'ORANGE', 'PINK'],
    why: 'The sort change moved all of 128-139 to GOLD, but the Next Day Air exception for 136 survives it.',
    tags: ['sort-change', 'exception', 'service-split'],
  },
  {
    id: 'ny-140-149-nda-nyc',
    svc: 'NDA', state: 'NY', code: '140-149',
    belt: 'PURPLE',
    confusions: ['ORANGE', 'GOLD', 'PINK'],
    why: 'Next Day Air keeps the whole 140-149 range PURPLE. Ground, 2 Day Air and 3 Day Select now split it: 140-147 GOLD, then 148-149 ORANGE except 148 1 GOLD.',
    tags: ['service-split'],
  },
];

const NEXT_DAY_AIR = [
  {
    id: 'nda-nh-034-0',
    svc: 'NDA', state: 'NH', code: '034 0',
    belt: 'GOLD',
    confusions: ['PURPLE', 'BLUE', 'GREEN'],
    why: 'Both neighbours, 030-033 and 035-049, are PURPLE on Next Day Air. This one code is GOLD.',
    tags: ['boundary', 'exception'],
  },
  {
    id: 'nda-ny-136',
    svc: 'NDA', state: 'NY', code: '136',
    belt: 'PURPLE',
    confusions: ['GOLD', 'ORANGE', 'PINK'],
    why: '128-135 and 137-139 are both GOLD. This single code is PURPLE, and it survived the sort change.',
    tags: ['exception', 'sort-change'],
  },
  {
    id: 'nda-ma-025-026',
    svc: 'NDA', state: 'MA', code: '025-026',
    belt: 'PURPLE',
    confusions: ['BLUE', 'GOLD', 'GREEN'],
    why: 'Ground, 2 Day Air and 3 Day Select all say BLUE here. Next Day Air says PURPLE.',
    tags: ['service-split'],
  },
  {
    id: 'nda-ny-110-119',
    svc: 'NDA', state: 'NY', code: '110-119',
    belt: 'PINK',
    confusions: ['PURPLE', 'GOLD', 'ORANGE'],
    why: 'PINK even on Next Day Air, where most of the board is PURPLE.',
    tags: ['boundary'],
  },
  {
    id: 'nda-ny-109',
    svc: 'NDA', state: 'NY', code: '109',
    belt: 'ORANGE',
    confusions: ['YELLOW', 'PINK', 'PURPLE'],
    why: 'Alone between 100-108 YELLOW and 110-119 PINK, the same as on Ground.',
    tags: ['boundary'],
  },
  {
    id: 'nda-pa-150-167',
    svc: 'NDA', state: 'PA', code: '150-167',
    belt: 'PURPLE',
    confusions: ['GREEN', 'ORANGE', 'BLUE'],
    why: 'Ground, 2 Day Air and 3 Day Select all say GREEN for this range. Only Next Day Air is PURPLE.',
    tags: ['service-split'],
  },
  {
    id: 'nda-pa-168-178',
    svc: 'NDA', state: 'PA', code: '168-178',
    belt: 'GREEN',
    confusions: ['PURPLE', 'ORANGE', 'BLUE'],
    why: 'GREEN on Next Day Air, even though 150-167 immediately below it is PURPLE.',
    tags: ['boundary', 'service-split'],
  },
  {
    id: 'nda-pa-190-194',
    svc: 'NDA', state: 'PA', code: '190-194',
    belt: 'ORANGE',
    confusions: ['GREEN', 'PURPLE', 'BLUE'],
    why: 'GREEN on both sides — 179-189 below and 195-199 above. This block is ORANGE.',
    tags: ['boundary'],
  },
  {
    id: 'nda-nj-078-4',
    svc: 'NDA', state: 'NJ', code: '078 4',
    belt: 'RED',
    confusions: ['CHECK', 'BLUE', 'ORANGE'],
    why: 'New Jersey routes to RED on the current Twilight rule. Only the single code 079 9 goes ORANGE.',
    tags: ['base-rule'],
  },
  {
    id: 'nda-dcmd-200-219',
    svc: 'NDA', state: 'DC, MD', code: '200-219',
    belt: 'GREEN',
    confusions: ['PURPLE', 'YELLOW', 'BLUE'],
    why: 'The last GREEN block on Next Day Air. Everything from 220 up goes PURPLE.',
    tags: ['boundary'],
  },
];

const TWO_DAY_AIR = [
  {
    id: '2da-ms-386-399',
    svc: '2DA', state: 'MS', code: '386-399',
    belt: 'PURPLE',
    confusions: ['BROWN', 'BLUE', 'ORANGE'],
    why: 'Ground and 3 Day Select both say BROWN for this range. 2 Day Air breaks to PURPLE.',
    tags: ['service-split'],
  },
  {
    id: '2da-ky-420',
    svc: '2DA', state: 'KY', code: '420',
    belt: 'PURPLE',
    confusions: ['BROWN', 'ORANGE', 'BLUE'],
    why: '400-419 and 421-429 are both BROWN. This single code is PURPLE.',
    tags: ['boundary', 'exception'],
  },
  {
    id: '2da-fl-320-349',
    svc: '2DA', state: 'FL', code: '320-349',
    belt: 'PURPLE',
    confusions: ['PINK', 'BLUE', 'BROWN'],
    why: 'Ground and 3 Day Select both say PINK for Florida. 2 Day Air says PURPLE.',
    tags: ['service-split'],
  },
  {
    id: '2da-al-350-369',
    svc: '2DA', state: 'AL', code: '350-369',
    belt: 'PURPLE',
    confusions: ['BLUE', 'BROWN', 'PINK'],
    why: 'Ground and 3 Day Select both say BLUE for Alabama. 2 Day Air says PURPLE.',
    tags: ['service-split'],
  },
  {
    id: '2da-tn-370-385',
    svc: '2DA', state: 'TN', code: '370-385',
    belt: 'BROWN',
    confusions: ['PURPLE', 'BLUE', 'ORANGE'],
    why: 'BROWN, sitting between two PURPLE blocks — 350-369 below and 386-399 above.',
    tags: ['boundary'],
  },
  {
    id: '2da-ok-741-9',
    svc: '2DA', state: 'OK', code: '741 9',
    belt: 'ORANGE',
    confusions: ['PURPLE', 'BLUE', 'BROWN'],
    why: '730-740 and 742-749 are both PURPLE. This one code is ORANGE.',
    tags: ['exception', 'boundary'],
  },
  {
    id: '2da-mo-630-639',
    svc: '2DA', state: 'MO', code: '630-639',
    belt: 'BLUE',
    confusions: ['PURPLE', 'ORANGE', 'YELLOW'],
    why: 'BLUE, with ORANGE below it at 609-629 and PURPLE above it from 640 up.',
    tags: ['boundary'],
  },
  {
    id: '2da-il-600-608',
    svc: '2DA', state: 'IL', code: '600-608',
    belt: 'PURPLE',
    confusions: ['YELLOW', 'ORANGE', 'BLUE'],
    why: 'The 2 Day Air chart sends IL 600-619 to PURPLE. Ground and 3 Day Select send 600-608 to YELLOW.',
    tags: ['boundary', 'service-split'],
  },
  {
    id: '2da-ga-300-319',
    svc: '2DA', state: 'GA', code: '300-319',
    belt: 'BLUE',
    confusions: ['PURPLE', 'YELLOW', 'PINK'],
    why: 'BLUE, between YELLOW at 270-299 and PURPLE at 320-349.',
    tags: ['boundary'],
  },
  {
    id: '2da-nh-034-0',
    svc: '2DA', state: 'NH', code: '034 0',
    belt: 'GOLD',
    confusions: ['BLUE', 'PURPLE', 'GREEN'],
    why: 'Both neighbours, 030-033 and 035-049, are BLUE on 2 Day Air. This one code is GOLD.',
    tags: ['boundary', 'exception'],
  },
];

const THREE_DAY_SELECT = [
  {
    id: '3ds-tx-769-0',
    svc: '3DS', state: 'TX', code: '769 0',
    belt: 'PURPLE',
    confusions: ['BLUE', 'ORANGE', 'BROWN'],
    why: '750-768 and 770-784 are both BLUE. This one code is PURPLE.',
    tags: ['exception', 'boundary'],
  },
  {
    id: '3ds-moks-630-674',
    svc: '3DS', state: 'MO, KS', code: '630-674',
    belt: 'BLUE',
    confusions: ['ORANGE', 'BROWN', 'YELLOW'],
    why: 'BLUE up to 674. The short 675-679 block right above it is ORANGE.',
    tags: ['boundary'],
  },
  {
    id: '3ds-ks-675-679',
    svc: '3DS', state: 'KS', code: '675-679',
    belt: 'ORANGE',
    confusions: ['BLUE', 'BROWN', 'YELLOW'],
    why: 'A five-code ORANGE strip cut out of the BLUE Kansas and Missouri run below it.',
    tags: ['boundary'],
  },
  {
    id: '3ds-ne-680-689',
    svc: '3DS', state: 'NE', code: '680-689',
    belt: 'BLUE',
    confusions: ['ORANGE', 'BROWN', 'YELLOW'],
    why: 'BLUE, with ORANGE on both sides — 675-679 below and 690-699 above.',
    tags: ['boundary'],
  },
  {
    id: '3ds-ne-690-699',
    svc: '3DS', state: 'NE', code: '690-699',
    belt: 'ORANGE',
    confusions: ['BLUE', 'BROWN', 'YELLOW'],
    why: 'Nebraska splits: 680-689 is BLUE and 690-699 is ORANGE.',
    tags: ['boundary'],
  },
  {
    id: '3ds-fl-320-349',
    svc: '3DS', state: 'FL', code: '320-349',
    belt: 'PINK',
    confusions: ['PURPLE', 'BLUE', 'BROWN'],
    why: 'PINK on 3 Day Select, the same as Ground. On 2 Day Air the same range is PURPLE.',
    tags: ['service-split'],
  },
  {
    id: '3ds-ms-386-399',
    svc: '3DS', state: 'MS', code: '386-399',
    belt: 'BROWN',
    confusions: ['PURPLE', 'BLUE', 'ORANGE'],
    why: 'BROWN on 3 Day Select, the same as Ground. On 2 Day Air this same range is PURPLE.',
    tags: ['service-split'],
  },
  {
    id: '3ds-tx-785-799',
    svc: '3DS', state: 'TX', code: '785-799',
    belt: 'PURPLE',
    confusions: ['BLUE', 'ORANGE', 'BROWN'],
    why: '770-784 just below it is BLUE. Texas splits again at 785.',
    tags: ['boundary'],
  },
  {
    id: '3ds-il-600-608',
    svc: '3DS', state: 'IL', code: '600-608',
    belt: 'YELLOW',
    confusions: ['ORANGE', 'BLUE', 'BROWN'],
    why: 'YELLOW only to 608. 609-629 right above it is ORANGE.',
    tags: ['boundary'],
  },
  {
    id: '3ds-al-350-369',
    svc: '3DS', state: 'AL', code: '350-369',
    belt: 'BLUE',
    confusions: ['PURPLE', 'PINK', 'BROWN'],
    why: 'BLUE on 3 Day Select, the same as Ground. On 2 Day Air the same range is PURPLE.',
    tags: ['service-split'],
  },
];

const mixed = (id, svc, state, code, belt, confusions, why) => ({
  id: `mixed-${id}`, svc, state, code, belt, confusions, why,
  tags: ['service-split', 'boundary'],
});

// A fixed mixed set for the routes selected by the supervisor. Service is part
// of every card because the same state/range can change belt by service.
const MIXED_MISSORTS = [
  mixed('in-2da', '2DA', 'IN', '460-479', 'PURPLE', ['ORANGE', 'BLUE', 'GOLD'],
    'Indiana is ORANGE on Ground, but PURPLE on 2 Day Air.'),
  mixed('oh-2da', '2DA', 'OH', '430-459', 'ORANGE', ['PURPLE', 'YELLOW', 'BROWN'],
    'Ohio stays ORANGE on 2 Day Air; do not carry Indiana’s PURPLE rule across the state line.'),
  mixed('mi-2da', '2DA', 'MI', '480-497', 'ORANGE', ['PURPLE', 'YELLOW', 'BROWN'],
    'Michigan stays ORANGE on 2 Day Air, while Indiana immediately before it is PURPLE.'),
  mixed('il-600-619-2da', '2DA', 'IL', '600-619', 'PURPLE', ['YELLOW', 'ORANGE', 'BLUE'],
    'Illinois 600-619 is PURPLE on 2 Day Air. Ground and 3 Day Select use different belts within this span.'),
  mixed('il-620-629-2da', '2DA', 'IL', '620-629', 'ORANGE', ['PURPLE', 'YELLOW', 'BLUE'],
    'Illinois changes from PURPLE to ORANGE at 620 on 2 Day Air.'),
  mixed('ny-128-139-gnd', 'GND', 'NY', '128-139', 'GOLD', ['ORANGE', 'PURPLE', 'PINK'],
    'NY 128-139 is GOLD on Ground. Next Day Air has a single-code PURPLE exception at 136.'),
  mixed('ny-136-nda', 'NDA', 'NY', '136', 'PURPLE', ['GOLD', 'ORANGE', 'PINK'],
    'NY 136 stays PURPLE on Next Day Air inside the surrounding GOLD range.'),
  mixed('ny-140-147-gnd', 'GND', 'NY', '140-147', 'GOLD', ['ORANGE', 'PURPLE', 'PINK'],
    'The recent sort change moved NY 140-147 to GOLD on Ground, 2 Day Air and 3 Day Select.'),
  mixed('ny-140-147-nda', 'NDA', 'NY', '140-147', 'PURPLE', ['GOLD', 'ORANGE', 'PINK'],
    'Next Day Air keeps NY 140-149 PURPLE, including 140-147.'),
  mixed('ma-025-gnd', 'GND', 'MA', '025', 'BLUE', ['GOLD', 'PURPLE', 'GREEN'],
    'MA 025 and 026 are BLUE on Ground, between GOLD ranges.'),
  mixed('ma-026-gnd', 'GND', 'MA', '026', 'BLUE', ['GOLD', 'PURPLE', 'GREEN'],
    'MA 026 is the second BLUE code in this Ground block; Next Day Air sends it PURPLE.'),
  mixed('ca-900-935-gnd', 'GND', 'CA', '900-935', 'RED', ['BROWN', 'PURPLE', 'ORANGE'],
    'California stays RED through 935 on Ground. The BROWN range begins at 936.'),
  mixed('ca-936-961-gnd', 'GND', 'CA', '936-961', 'BROWN', ['RED', 'PURPLE', 'ORANGE'],
    'California changes to BROWN at 936 on Ground; 935 is still RED.'),
  mixed('nh-030-033-gnd', 'GND', 'NH', '030-033', 'BLUE', ['GOLD', 'PURPLE', 'ORANGE'],
    'NH 030-033 is BLUE on Ground. The next listed code, 034 0, is GOLD.'),
  mixed('nh-034-0-gnd', 'GND', 'NH', '034 0', 'GOLD', ['BLUE', 'PURPLE', 'ORANGE'],
    'NH 034 0 is GOLD between BLUE ranges on Ground.'),
  mixed('nh-030-033-nda', 'NDA', 'NH', '030-033', 'PURPLE', ['BLUE', 'GOLD', 'ORANGE'],
    'Next Day Air sends NH 030-033 to PURPLE, while Ground sends it BLUE.'),
];

export const DECKS = [
  ...LEVEL_DECKS,
  {
    id: 'common-twilight-1',
    name: 'Common Missorts · Set 1',
    sort: 'Twilight',
    blurb: 'The usual traps, including the updated New Jersey rule',
    verified: true,
    cards: [...COMMON_CORE, ...NJ_TWILIGHT.slice(0, 3)],
  },
  {
    id: 'common-twilight-2',
    name: 'Common Missorts · Set 2',
    sort: 'Twilight',
    blurb: 'A second familiar set with different New Jersey examples',
    verified: true,
    cards: [...COMMON_CORE, NJ_TWILIGHT[2], ...NJ_TWILIGHT.slice(3)],
  },
  {
    id: 'mixed-missorts',
    name: 'Common Missorts · Mixed',
    sort: 'Twilight',
    blurb: '2 Day IN/OH/MI/IL, NY 128-147, MA 025-026, CA 900-935/936-961, and NH',
    verified: true,
    cards: MIXED_MISSORTS,
  },
  {
    id: 'new-york',
    name: 'New York',
    sort: 'Twilight',
    blurb: 'Every New York range and where the lines fall',
    verified: true,
    cards: NEW_YORK,
  },
  {
    id: 'next-day-air',
    name: 'Next Day Air',
    sort: 'Twilight',
    blurb: 'The service that breaks the most rules',
    verified: true,
    cards: NEXT_DAY_AIR,
  },
  {
    id: 'two-day-air',
    name: '2 Day Air',
    sort: 'Twilight',
    blurb: 'Where 2 Day splits away from Ground',
    verified: true,
    cards: TWO_DAY_AIR,
  },
  {
    id: 'three-day-select',
    name: '3 Day Select',
    sort: 'Twilight',
    blurb: 'Boundaries and the long middle blocks',
    verified: true,
    cards: THREE_DAY_SELECT,
  },
];

// The sort and set stay in each new shift-log and Excel label. Older saved
// results keep their historical labels and are not rewritten.
export function deckLabel(deck) {
  return deck.sort ? `${deck.name} \u00b7 ${deck.sort}` : deck.name;
}

export function deckById(id) {
  return DECKS.find((deck) => deck.id === id) ?? null;
}

export function availableDecks() {
  return DECKS.filter((deck) => deck.verified);
}
