import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ COMMON_CORE, NJ_TWILIGHT }, { DECKS }, { CHART, ROUTE_REFERENCE_VERSION }], cleanup } = await loadAppModules([
  'src/questions.js', 'src/decks.js', 'src/chart.js',
]);
after(cleanup);

const scenarios = [
  ['destination-plus-one-gnd', 'GND', 'Ground'],
  ['destination-plus-one-nda', 'NDA', 'Next Day Air'],
  ['destination-plus-one-2da', '2DA', '2 Day Air'],
  ['destination-plus-one-3ds', '3DS', '3 Day Select'],
];

test('plus-one cards carry separate destination metadata', () => {
  for (const [id, service] of scenarios) {
    const card = COMMON_CORE.find(card => card.id === id);
    assert.ok(card, `missing ${id}`);
    assert.equal(card.code, '109');
    assert.equal(card.destinationModifier, '+1');
    assert.equal(card.belt, 'PURPLE');
    assert.ok(['GND', 'NDA', '2DA', '3DS'].includes(card.svc));
    assert.equal(card.svc, service);
    assert.equal(card.state, 'NY');
    assert.equal(card.referenceVersion, ROUTE_REFERENCE_VERSION);
    assert.equal(card.confusions.length, 3);
    assert.equal(new Set(card.confusions).size, 3);
    assert.ok(!card.confusions.includes('PURPLE'));
    assert.match(card.why, /destination/i);
    assert.match(card.why, /\+1/);
    assert.match(card.why, /PURPLE/);
    assert.match(card.why, /109.*ORANGE/);
    assert.equal(card.rankedApproved, undefined);
    assert.equal(card.difficulty, undefined);
  }
});

test('NY 109 without a destination modifier stays ORANGE on every base service', () => {
  for (const [, service, serviceName] of scenarios) {
    const control = { svc: service, state: 'NY', code: '109' };
    assert.equal(control.destinationModifier, undefined);
    assert.equal(CHART[serviceName].main.find(([state, code]) => state === control.state && code === control.code)?.[2], 'ORANGE');
  }
});

test('authored cards reject ambiguous destination and routing markers', () => {
  for (const card of [...COMMON_CORE, ...NJ_TWILIGHT, ...DECKS.flatMap(deck => deck.cards)]) {
    assert.ok(!card.code.includes('+1'), `${card.id}: +1 belongs to the destination`);
    if (card.destinationModifier !== undefined) {
      assert.equal(card.destinationModifier, '+1', `${card.id}: unsupported destination modifier`);
      assert.ok(!/2S\s*$/i.test(card.code), `${card.id}: +1 and 2S precedence is unapproved`);
    }
  }
});

test('both Common pools contain all four plus-one services alongside valid routing endings', () => {
  for (const id of ['common-twilight-1', 'common-twilight-2']) {
    const deck = DECKS.find(deck => deck.id === id);
    for (const [cardId] of scenarios) assert.ok(deck.cards.some(card => card.id === cardId), `${id}: ${cardId}`);
    assert.ok(deck.cards.some(card => card.code === '109 2S' && card.belt === 'BLUE'));
    assert.ok(deck.cards.some(card => card.code === '150 1S' && card.belt === 'PURPLE'));
  }
});
