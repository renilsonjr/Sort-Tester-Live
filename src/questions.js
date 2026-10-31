// The active Saddle Brook practice chart is Twilight. The updated New Jersey
// rule sends NJ to RED except 079 9, which goes ORANGE on every service.

export const SERVICE_LABEL = {
  GND: 'Ground',
  GRD: 'Ground',
  '2DA': '2 Day Air',
  '3DS': '3 Day Select',
  NDA: 'Next Day Air',
  ALL: 'All Services',
};

// The 2S and 1S terminations OVERRIDE the range table: a ZIP ending 2S goes
// BLUE and one ending 1S goes PURPLE, whatever the chart says for that range.
// Every other card in the app shows a bare code, which means no termination.
//
// Eleven common traps from the Twilight chart.
export const COMMON_CORE = [
  {
    id: 'ny-136-nda',
    svc: 'NDA', state: 'NY', code: '136',
    belt: 'PURPLE',
    confusions: ['GOLD', 'ORANGE', 'BLUE'],
    why: 'The sort change moved all of NY 128-139 to GOLD, but 136 on Next Day Air stays PURPLE. Sorting from the new chart alone sends it GOLD.',
    tags: ['sort-change', 'service-split', 'exception'],
  },
  {
    id: 'ny-148-1-gnd',
    svc: 'GND', state: 'NY', code: '148 1',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: 'All of 140-149 is ORANGE on Ground, 2 Day Air and 3 Day Select. The single code 148 1 is the one pulled out to GOLD.',
    tags: ['sort-change', 'exception'],
  },
  {
    id: 'ny-140-149-nda',
    svc: 'NDA', state: 'NY', code: '140-149',
    belt: 'PURPLE',
    confusions: ['ORANGE', 'GOLD', 'PINK'],
    why: 'Ground, 2 Day Air and 3 Day Select all say ORANGE for this whole range. Only Next Day Air is PURPLE.',
    tags: ['service-split'],
  },
  {
    id: 'tn-376-378-grd',
    svc: 'GRD', state: 'TN', code: '376-378',
    belt: 'BLUE',
    confusions: ['BROWN', 'PURPLE', 'ORANGE'],
    why: 'Pulled out of the 370-385 BROWN block by the sort change. Everything around it is still BROWN.',
    tags: ['sort-change', 'boundary'],
  },
  {
    id: 'ms-386-399-2da',
    svc: '2DA', state: 'MS', code: '386-399',
    belt: 'PURPLE',
    confusions: ['BROWN', 'BLUE', 'ORANGE'],
    why: 'Ground and 3 Day Select both say BROWN for this range. 2 Day Air breaks to PURPLE.',
    tags: ['service-split'],
  },
  {
    id: 'nh-034-0-gnd',
    svc: 'GND', state: 'NH', code: '034 0',
    belt: 'GOLD',
    confusions: ['BLUE', 'ORANGE', 'GREEN'],
    why: 'Both neighbours, 030-033 and 035-049, are BLUE. This one code in the middle is GOLD.',
    tags: ['boundary', 'exception'],
  },
  {
    id: 'ma-025-gnd',
    svc: 'GND', state: 'MA', code: '025',
    belt: 'BLUE',
    confusions: ['GOLD', 'PURPLE', 'GREEN'],
    why: 'GOLD on both sides — 010-024 below it and 027-029 above. 025 and 026 are a BLUE island in the middle of the Massachusetts run.',
    tags: ['boundary', 'island'],
  },
  {
    id: 'ma-026-gnd',
    svc: 'GND', state: 'MA', code: '026',
    belt: 'BLUE',
    confusions: ['GOLD', 'PURPLE', 'GREEN'],
    why: 'The second code of the BLUE island. 027 right after it goes back to GOLD, and on Next Day Air this whole range is PURPLE instead.',
    tags: ['boundary', 'island'],
  },
  {
    id: 'suffix-2s-blue',
    svc: 'ALL', state: 'NY', code: '109 2S',
    belt: 'BLUE',
    confusions: ['ORANGE', 'PURPLE', 'YELLOW'],
    why: 'Anything ending 2S goes BLUE. The ZIP does not matter — 109 on its own would be ORANGE, and that is exactly the miss this card catches.',
    tags: ['termination', 'override'],
  },
  {
    id: 'suffix-1s-purple',
    svc: 'ALL', state: 'PA', code: '150 1S',
    belt: 'PURPLE',
    confusions: ['GREEN', 'BLUE', 'ORANGE'],
    why: 'Anything ending 1S goes PURPLE. The ZIP does not matter — PA 150-167 on its own would be GREEN, and the same package ending 2S would go BLUE.',
    tags: ['termination', 'override'],
  },
  {
    id: 'nv-833-9-7-gnd',
    svc: 'GND', state: 'NV', code: '833 9-7',
    belt: 'ORANGE',
    confusions: ['BROWN', 'BLUE', 'PURPLE'],
    why: 'It sits inside the 832-839 BROWN block, but the ground exception table pulls it to ORANGE.',
    tags: ['exception'],
  },
];

// Twilight NJ cards used across the two Common Missorts sets.
export const NJ_TWILIGHT = [
  {
    id: 'nj-078-4-twilight',
    svc: 'ALL', state: 'NJ', code: '078 4',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'New Jersey routes to RED on the current Twilight rule. Only 079 9 breaks to ORANGE.',
    tags: ['twilight'],
  },
  {
    id: 'nj-082-9-twilight',
    svc: 'ALL', state: 'NJ', code: '082 9',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'New Jersey routes to RED on the current Twilight rule. Only 079 9 breaks to ORANGE.',
    tags: ['twilight'],
  },
  {
    id: 'nj-079-9-twilight',
    svc: 'ALL', state: 'NJ', code: '079 9',
    belt: 'ORANGE',
    confusions: ['RED', 'BLUE', 'CHECK'],
    why: '079 9 is the single New Jersey exception: ORANGE instead of RED.',
    tags: ['twilight', 'exception'],
  },
  {
    id: 'nj-070-3-twilight',
    svc: 'ALL', state: 'NJ', code: '070 3',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'New Jersey routes to RED on the current Twilight rule. Only 079 9 breaks to ORANGE.',
    tags: ['twilight'],
  },
  {
    id: 'nj-083-9-twilight',
    svc: 'ALL', state: 'NJ', code: '083 9',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'New Jersey routes to RED on the current Twilight rule. Only 079 9 breaks to ORANGE.',
    tags: ['twilight'],
  },
];
