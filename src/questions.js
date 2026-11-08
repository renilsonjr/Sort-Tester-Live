import { ROUTE_REFERENCE_VERSION } from './chart.js?v=chart-destination-20261108-r2';

// Current Twilight cards use only reviewed ranges and listed preload codes.

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
// The +1 destination modifier is separate from both the base service and code.
// Do not author +1 with a conflicting 2S ending until precedence is approved.
//
// Shared common traps from the Twilight chart and confirmed owner rules.
export const COMMON_CORE = [
  {
    id: 'ny-136-nda',
    svc: 'NDA', state: 'NY', code: '136',
    belt: 'PURPLE',
    confusions: ['GOLD', 'ORANGE', 'BLUE'],
    why: 'Next Day Air sends 128-135 and 137-139 to GOLD, but the single code 136 to PURPLE.',
    tags: ['sort-change', 'service-split', 'exception'],
  },
  {
    id: 'ny-148-1-gnd',
    svc: 'GND', state: 'NY', code: '148 1',
    belt: 'GOLD',
    confusions: ['ORANGE', 'PURPLE', 'PINK'],
    why: '148 1 stays GOLD inside the ORANGE 148-149 block on Ground, 2 Day Air and 3 Day Select. The preceding 140-147 block is GOLD on Ground and ORANGE on 2 Day Air and 3 Day Select.',
    tags: ['sort-change', 'exception'],
  },
  {
    id: 'ny-140-149-nda',
    svc: 'NDA', state: 'NY', code: '140-149',
    belt: 'PURPLE',
    confusions: ['ORANGE', 'GOLD', 'PINK'],
    why: 'Next Day Air keeps all of 140-149 PURPLE. Ground sends 140-147 to GOLD; 2 Day Air and 3 Day Select send it to ORANGE. On those three services, 148-149 is ORANGE except 148 1 GOLD.',
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
    why: 'Anything ending 1S goes PURPLE. The ZIP does not matter — PA 150-167 is GREEN on Ground, 2 Day Air and 3 Day Select, but PURPLE on Next Day Air. The same package ending 2S would go BLUE.',
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
  ...[
    ['gnd', 'GND', 'Ground'],
    ['nda', 'NDA', 'Next Day Air'],
    ['2da', '2DA', '2 Day Air'],
    ['3ds', '3DS', '3 Day Select'],
  ].map(([id, svc, service]) => ({
    id: `destination-plus-one-${id}`,
    svc, state: 'NY', code: '109', destinationModifier: '+1',
    belt: 'PURPLE',
    confusions: ['ORANGE', 'BLUE', 'GOLD'],
    why: `The +1 destination indicator sends ${service} to PURPLE. NY 109 without that destination modifier is ORANGE; the routing code stays 109.`,
    tags: ['destination-modifier', 'override'],
  })),
].map(card => ({ ...card, referenceVersion: ROUTE_REFERENCE_VERSION }));

// Twilight NJ cards used across the two Common Missorts sets.
export const NJ_TWILIGHT = [
  {
    id: 'nj-078-4-twilight',
    svc: 'ALL', state: 'NJ', code: '078 4',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'This listed New Jersey preload code goes RED on all four services. Use the preload list; the broad NJ range says CHECK.',
    tags: ['twilight'],
  },
  {
    id: 'nj-082-9-twilight',
    svc: 'ALL', state: 'NJ', code: '082 9',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'This listed New Jersey preload code goes RED on all four services. Use the preload list; the broad NJ range says CHECK.',
    tags: ['twilight'],
  },
  {
    id: 'nj-079-9-twilight',
    svc: 'ALL', state: 'NJ', code: '079 9',
    belt: 'ORANGE',
    confusions: ['RED', 'BLUE', 'CHECK'],
    why: 'The listed New Jersey preload code 079 9 goes ORANGE on all four services.',
    tags: ['twilight', 'exception'],
  },
  {
    id: 'nj-070-3-twilight',
    svc: 'ALL', state: 'NJ', code: '070 3',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'This listed New Jersey preload code goes RED on all four services. Use the preload list; the broad NJ range says CHECK.',
    tags: ['twilight'],
  },
  {
    id: 'nj-083-9-twilight',
    svc: 'ALL', state: 'NJ', code: '083 9',
    belt: 'RED',
    confusions: ['BLUE', 'CHECK', 'ORANGE'],
    why: 'This listed New Jersey preload code goes RED on all four services. Use the preload list; the broad NJ range says CHECK.',
    tags: ['twilight'],
  },
].map(card => ({ ...card, referenceVersion: ROUTE_REFERENCE_VERSION }));
