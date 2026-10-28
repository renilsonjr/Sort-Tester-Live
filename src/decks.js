import { COMMON_CORE, NJ_PRELOAD, NJ_TWILIGHT } from './questions.js';

// Every deck here is transcribed from the Saddle Brook primary sort chart with
// the SORT CHANGE sheet applied.
//
// Common Missorts ships twice, once per sort. The eleven core cards are shared;
// only the New Jersey set differs, because NJ is the one place the preload and
// twilight sorts send the same code to different belts. Every deck states which
// sort it is asking about, and that label follows the result into the shift log
// and the Excel export.
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
    why: 'GOLD on Ground, with ORANGE on both sides. On Next Day Air the single code 136 breaks out to PURPLE.',
    tags: ['boundary'],
  },
  {
    id: 'ny-140-147-gnd',
    svc: 'GND', state: 'NY', code: '140-147',
    belt: 'ORANGE',
    confusions: ['GOLD', 'PURPLE', 'PINK'],
    why: 'ORANGE, and 148-149 above it is ORANGE too. The whole run to 149 is one belt apart from a single code.',
    tags: ['sort-change', 'boundary'],
  },
  {
    id: 'ny-148-149-gnd-nyc',
    svc: 'GND', state: 'NY', code: '148-149',
    belt: 'ORANGE',
    confusions: ['GOLD', 'PURPLE', 'PINK'],
    why: 'ORANGE on Ground, 2 Day Air and 3 Day Select, the same as 140-147 below it. Only the single code 148 1 breaks out.',
    tags: ['boundary'],
  },
  {
    id: 'ny-148-1-gnd-nyc',
    svc: 'GND', state: 'NY', code: '148 1',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: 'The one code the sort change pulled out of the ORANGE 140-149 run. Everything around it, 148-149 included, is still ORANGE.',
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
    why: 'Ground, 2 Day Air and 3 Day Select all say ORANGE across 140-149. Next Day Air takes the whole range PURPLE.',
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
    id: 'nda-nj-070-089',
    svc: 'NDA', state: 'NJ', code: '070-089',
    belt: 'CHECK',
    confusions: ['RED', 'BLUE', 'ORANGE'],
    why: 'New Jersey is CHECK on every service. The preload list and the 080-084 sort change override it for specific codes.',
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
    belt: 'YELLOW',
    confusions: ['ORANGE', 'BLUE', 'PURPLE'],
    why: 'YELLOW only to 608. 609-629 right above it is ORANGE.',
    tags: ['boundary'],
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

export const DECKS = [
  {
    id: 'common-preload',
    name: 'Common Missorts',
    sort: 'Preload',
    blurb: 'The usual traps, with New Jersey read off the preload list',
    verified: true,
    cards: [...COMMON_CORE, ...NJ_PRELOAD],
  },
  {
    id: 'common-twilight',
    name: 'Common Missorts',
    sort: 'Twilight',
    blurb: 'The same traps, with New Jersey read off the twilight chart',
    verified: true,
    cards: [...COMMON_CORE, ...NJ_TWILIGHT],
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

// "Common Missorts · Preload" — what a deck is called wherever it is recorded.
export function deckLabel(deck) {
  return deck.sort ? `${deck.name} \u00b7 ${deck.sort}` : deck.name;
}

export function deckById(id) {
  return DECKS.find((deck) => deck.id === id) ?? null;
}

export function availableDecks() {
  return DECKS.filter((deck) => deck.verified);
}
