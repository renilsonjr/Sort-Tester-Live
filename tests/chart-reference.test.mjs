import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const reference = JSON.parse(await readFile(new URL('./fixtures/twilight-reference-2026-11-08.json', import.meta.url)));
const { modules: [chart, { DECKS }, { selectLevelCards }, { createLanguage }], cleanup } = await loadAppModules([
  'src/chart.js', 'src/decks.js', 'src/levels.js', 'src/i18n.js',
]);
after(cleanup);
const { CHART, searchChart } = chart;
const services = Object.keys(CHART);
const names = { GND: 'Ground', GRD: 'Ground', NDA: 'Next Day Air', '2DA': '2 Day Air', '3DS': '3 Day Select' };
const normalized = value => value.replace(/–/g, '-');

// Wrong belts, missing rows and accidental unreviewed additions break this matrix.
for (const item of reference.cases) {
  test(`reference ${item.id} (${item.provenance})`, () => {
    const actual = CHART[item.service][item.kind].find(([state, code]) => state === item.state && code === item.code);
    assert.equal(actual?.[2], item.expectedBelt);
  });
}
for (const service of services) {
  for (const kind of ['main', 'exceptions']) {
    test(`${service} ${kind} contains only reviewed source rows`, () => {
      const expected = reference.cases.filter(item => item.service === service && item.kind === kind)
        .map(item => JSON.stringify([item.state, item.code, item.expectedBelt])).sort();
      assert.deepEqual(CHART[service][kind].map(row => JSON.stringify(row.slice(0, 3))).sort(), expected);
    });
  }
}

test('2DA Georgia uses the owner-selected reference', () => {
  assert.equal(CHART['2 Day Air'].main.find(([state, code]) => state === 'GA' && code === '300–319')?.[2], 'BLUE');
});

// Search endpoints catch wrong inclusive boundaries without reimplementing routing.
for (const [service, state, lower, upper, belt] of [
  ['2 Day Air', 'GA', '300', '319', 'BLUE'],
  ['2 Day Air', 'IN', '460', '479', 'ORANGE'],
  ['2 Day Air', 'IL', '600', '608', 'YELLOW'],
  ['2 Day Air', 'IL', '609', '629', 'ORANGE'],
  ['3 Day Select', 'TX', '750', '768', 'BLUE'],
  ['3 Day Select', 'TX', '770', '784', 'BLUE'],
  ['3 Day Select', 'TX', '785', '799', 'PURPLE'],
  ['3 Day Select', '', '811', '999', 'PURPLE'],
  ['Ground', 'NY', '128', '147', 'GOLD'],
  ['2 Day Air', 'NY', '140', '147', 'ORANGE'],
  ['3 Day Select', 'NY', '140', '147', 'ORANGE'],
]) {
  for (const endpoint of [lower, upper]) test(`${service} ${state} ${endpoint} boundary`, () => {
    assert.ok(searchChart(service, `${state} ${endpoint}`.trim()).main.some(row => row[2] === belt));
  });
}

// Find the independently transcribed ordinary scenario. Range cards describe the
// base row; a listed single-code exception is tested separately above.
function referenceFor(card, service) {
  if (card.destinationModifier !== undefined) {
    const rule = reference.destinationModifierRule;
    return card.destinationModifier === rule.modifier && rule.services.includes(service) ? rule : null;
  }
  if (/ (1S|2S)$/.test(card.code)) return reference.cases.find(item =>
    item.service === service && item.code === `ends ${card.code.slice(-2)}`);
  const candidates = reference.cases.filter(item => item.service === service);
  const sameState = item => item.state === card.state || item.state === '*' ||
    (card.state === 'All states' && item.state === '*') ||
    card.state.split(', ').every(state => item.state.split(', ').includes(state));
  const exact = candidates.find(item => sameState(item) && normalized(item.code) === normalized(card.code));
  if (exact) return exact;
  const cardRange = normalized(card.code).match(/^(\d{3})(?:-(\d{3}))?$/);
  if (!cardRange) return null;
  return candidates.find(item => {
    if (!sameState(item) || item.kind !== 'main') return false;
    const range = normalized(item.code).match(/^(\d{3})-(\d{3})$/);
    return range && Number(cardRange[1]) >= Number(range[1]) && Number(cardRange[2] ?? cardRange[1]) <= Number(range[2]);
  });
}
for (const deck of DECKS) {
  test(`${deck.id} every authored/generated card follows the independent source`, () => {
    for (const card of deck.cards) {
      for (const service of card.svc === 'ALL' ? services : [names[card.svc]]) {
        const source = referenceFor(card, service);
        assert.ok(source, `${card.id}: missing reviewed scenario on ${service}`);
        assert.equal(card.belt, source.expectedBelt, `${card.id} on ${service}`);
        assert.notEqual(source.expectedBelt, 'CHECK', `${card.id}: broad NJ must not become a question`);
      }
    }
  });
}

test('Mixed replaces the ambiguous Illinois span and keeps 16-question runs', () => {
  const deck = DECKS.find(deck => deck.id === 'mixed-missorts');
  assert.ok(!deck.cards.some(card => card.id === 'mixed-il-600-619-2da'));
  for (const [id, belt] of [['mixed-il-600-608-2da', 'YELLOW'], ['mixed-il-609-619-2da', 'ORANGE']]) {
    assert.equal(deck.cards.find(card => card.id === id)?.belt, belt);
  }
  assert.equal(deck.cards.length, 17);
  assert.equal(deck.practiceRunSize, 16);
  assert.equal(deck.questionCount, undefined, 'Mixed stays in the ordinary picker group');
  for (const rand of [() => 0, () => 0.5, () => 0.999]) {
    const picked = selectLevelCards(deck, rand);
    assert.equal(picked.length, 16);
    assert.equal(new Set(picked.map(card => card.id)).size, 16);
    assert.ok(picked.every(card => deck.cards.includes(card)));
  }
});

test('existing deck run lengths are retained', () => {
  const counts = [15, 20, 30, 14, 14, 16, 10, 10, 10, 10];
  assert.deepEqual(DECKS.map(deck => selectLevelCards(deck, () => 0.5).length), counts);
});

test('current cards carry route provenance without claiming Ranked approval', () => {
  assert.equal(chart.ROUTE_REFERENCE_VERSION, 'twilight-2026-11-08-r2');
  for (const deck of DECKS) for (const card of deck.cards) {
    assert.equal(card.referenceVersion, 'twilight-2026-11-08-r2', card.id);
    assert.equal(card.rankedApproved, undefined);
  }
});

test('NJ Spanish feedback teaches the specific reviewed code without a blanket rule', () => {
  const language = createLanguage(); language.set('es');
  for (const code of ['078 4', '082 9', '083 9']) {
    const text = language.explanation({ svc: 'ALL', state: 'NJ', code, correctBelt: 'RED' });
    assert.ok(text.includes(code));
    assert.ok(text.includes('RED'));
    assert.ok(!text.includes('Solo 079 9'));
  }
});

// The owner correction must reach quiz scoring, not just the Study chart.
test('2DA Indiana accepts ORANGE and rejects the superseded PURPLE answer', async () => {
  const { modules: [{ createRun, answerCard }], cleanup: cleanQuiz } = await loadAppModules(['src/quiz.js']);
  try {
    const card = DECKS.find(deck => deck.id === 'mixed-missorts').cards.find(card => card.id === 'mixed-in-2da');
    assert.ok(card);
    assert.ok(!card.confusions.includes('ORANGE'), 'correct belt must not appear among distractors');
    for (const [answer, expected] of [['ORANGE', 'correct'], ['PURPLE', 'wrong']]) {
      const run = createRun({ name: 'Fictional correction test', cards: [card] });
      const response = answerCard(run, answer, 1000);
      assert.equal(response.outcome, expected);
      assert.equal(response.correctBelt, 'ORANGE');
      assert.equal(response.referenceVersion, 'twilight-2026-11-08-r2');
    }
    const language = createLanguage();
    for (const lang of ['en', 'es']) {
      language.set(lang);
      const text = language.explanation({ ...card, correctBelt: card.belt });
      assert.match(text, /ORANGE/);
      assert.ok(!text.includes('PURPLE'), 'feedback must not teach the superseded Indiana belt');
    }
  } finally { await cleanQuiz(); }
});
