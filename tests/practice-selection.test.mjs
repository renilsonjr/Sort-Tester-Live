import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ DECKS }, { selectLevelCards }], cleanup } = await loadAppModules([
  'src/decks.js', 'src/levels.js',
]);
after(cleanup);

// A reproducible stream includes many shuffles; edge streams exercise both ends.
function seededRandom(seed) {
  let state = seed;
  return () => {
    state = (Math.imul(1664525, state) + 1013904223) >>> 0;
    return state / 2 ** 32;
  };
}
const streams = [
  ...Array.from({ length: 100 }, (_, seed) => [String(seed), () => seededRandom(seed)]),
  ['all-zero', () => () => 0],
  ['near-one', () => () => 1 - Number.EPSILON],
];
const runSizes = [
  ['level-basic', 15], ['level-medium', 20], ['level-hard', 30],
  ['common-twilight-1', 14], ['common-twilight-2', 14], ['mixed-missorts', 16],
  ['new-york', 10], ['next-day-air', 10], ['two-day-air', 10], ['three-day-select', 10],
];

for (const [id, count] of runSizes) {
  test(`${id} preserves run size, unique cards and service coverage across all random streams`, () => {
    const deck = DECKS.find(deck => deck.id === id);
    const original = JSON.stringify(deck);
    for (const [stream, createRandom] of streams) {
      const picked = selectLevelCards(deck, createRandom());
      const context = `${id}, stream ${stream}`;
      assert.equal(picked.length, count, context);
      assert.equal(new Set(picked.map(card => card.id)).size, count, context);
      assert.ok(picked.every(card => deck.cards.includes(card)), context);
      assert.deepEqual(new Set(picked.map(card => card.svc)), new Set(deck.cards.map(card => card.svc)), context);
      if (deck.questionCount ?? deck.practiceRunSize) {
        for (const belt of new Set(picked.map(card => card.belt))) {
          assert.ok(picked.filter(card => card.belt === belt).length <= Math.ceil(count / 3), `${context}, belt ${belt}`);
        }
      }
      if (id.startsWith('common-twilight-')) {
        assert.ok(picked.some(card => card.destinationModifier === '+1'), `${context}: missing +1`);
      }
    }
    assert.equal(JSON.stringify(deck), original, 'selection must not mutate the candidate pool');
  });
}

test('expanded Common and Mixed pools retain ordinary picker semantics', () => {
  for (const [id, poolSize, runSize] of [
    ['common-twilight-1', 18, 14], ['common-twilight-2', 18, 14], ['mixed-missorts', 17, 16],
  ]) {
    const deck = DECKS.find(deck => deck.id === id);
    assert.equal(deck.cards.length, poolSize);
    assert.equal(deck.practiceRunSize, runSize);
    assert.equal(deck.questionCount, undefined);
  }
});

test('questionCount takes precedence over practiceRunSize', () => {
  const cards = ['BLUE', 'GOLD', 'ORANGE'].map((belt, index) => ({ id: `test-${index}`, svc: 'GND', belt }));
  assert.equal(selectLevelCards({ id: 'sized', cards, questionCount: 2, practiceRunSize: 3 }, () => 0).length, 2);
});

test('unsized service decks return their complete existing card arrays', () => {
  for (const id of ['new-york', 'next-day-air', 'two-day-air', 'three-day-select']) {
    const deck = DECKS.find(deck => deck.id === id);
    assert.equal(deck.practiceRunSize, undefined);
    assert.equal(deck.questionCount, undefined);
    assert.equal(selectLevelCards(deck, () => { throw new Error('unsized decks must not shuffle here'); }), deck.cards);
  }
});

test('plus-one reservation randomly reaches all four candidates', () => {
  for (const id of ['common-twilight-1', 'common-twilight-2']) {
    const deck = DECKS.find(deck => deck.id === id);
    const candidates = deck.cards.filter(card => card.destinationModifier === '+1');
    const reserved = new Set();
    for (const value of [0, 0.25, 0.5, 1 - Number.EPSILON]) {
      const picked = selectLevelCards({ id: 'single-plus-one', cards: candidates, practiceRunSize: 1 }, () => value);
      reserved.add(picked[0].id);
      assert.equal(picked[0].destinationModifier, '+1');
    }
    assert.deepEqual(reserved, new Set([
      'destination-plus-one-gnd', 'destination-plus-one-nda',
      'destination-plus-one-2da', 'destination-plus-one-3ds',
    ]));
  }
});
