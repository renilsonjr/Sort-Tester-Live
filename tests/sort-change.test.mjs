import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ CHART }, { DECKS }, { BELTS, BELT_STYLE }, quiz, { createLanguage }], cleanup } = await loadAppModules([
  'src/chart.js', 'src/decks.js', 'src/belts.js', 'src/quiz.js', 'src/i18n.js',
]);
after(cleanup);
const previous = JSON.parse(await readFile(new URL('./fixtures/twilight-reference-2026-11-08.json', import.meta.url)));
const updates = [
  ['Ground', 'TX', 750, 779, 'BLACK'],
  ['3 Day Select', 'TX', 770, 779, 'BLACK'],
  ['2 Day Air', 'IL', 600, 619, 'PURPLE'],
  ['Ground', 'NY', 140, 147, 'GOLD'],
  ['3 Day Select', 'NY', 140, 147, 'GOLD'],
  ['2 Day Air', 'NY', 140, 147, 'GOLD'],
];
const matches = (code, prefix) => {
  const range = code.match(/^(\d{3})–(\d{3})$/);
  return range && prefix >= +range[1] && prefix <= +range[2];
};
// Compare every prefix against the frozen prior reference, applying only the
// owner's explicit changes. No production routing helper supplies expectations.
for (const service of Object.keys(CHART)) {
  test(`${service}: all 000–999 base rows retain scope and non-overlap`, () => {
    const old = previous.cases.filter(c => c.service === service && c.kind === 'main');
    for (let prefix = 0; prefix <= 999; prefix++) {
      const before = old.filter(c => matches(c.code, prefix));
      const actual = CHART[service].main.filter(r => matches(r[1], prefix));
      assert.equal(actual.length, before.length, `${service} ${prefix}: coverage`);
      for (const source of before) {
        const update = updates.find(([svc, state, low, high]) => svc === service && state === source.state && prefix >= low && prefix <= high);
        assert.equal(actual.find(r => r[0] === source.state)?.[2], update?.[4] ?? source.expectedBelt, `${service} ${prefix}`);
      }
    }
    assert.deepEqual(CHART[service].exceptions.map(r => JSON.stringify(r.slice(0, 3))).sort(), previous.cases
      .filter(c => c.service === service && c.kind === 'exceptions').map(c => JSON.stringify([c.state, c.code, c.expectedBelt])).sort());
  });
}

test('BLACK cards offer four choices, score correctly, and explain both languages', () => {
  assert.ok(BELTS.includes('BLACK'));
  assert.deepEqual(BELT_STYLE.BLACK, { bg: '#000000', fg: '#ffffff' });
  for (const [svc, code] of [['GND', '750–769'], ['GND', '770–779'], ['3DS', '770–779']]) {
    const card = DECKS.find(d => d.id === 'level-hard').cards.find(c => c.svc === svc && c.code === code);
    assert.equal(card?.belt, 'BLACK');
    const options = quiz.buildOptions(card, () => 0.5);
    assert.equal(new Set(options).size, 4);
    assert.ok(options.includes('BLACK'));
    for (const answer of ['BLACK', 'BLUE']) {
      const run = quiz.createRun({ name: 'Test', cards: [card] });
      const response = quiz.answerCard(run, answer, 1000);
      assert.equal(response.outcome, answer === 'BLACK' ? 'correct' : 'wrong');
      const language = createLanguage();
      for (const lang of ['en', 'es']) {
        language.set(lang);
        assert.match(language.explanation(response), /BLACK/);
      }
    }
  }
  const medium = DECKS.find(d => d.id === 'level-medium');
  assert.ok(medium.cards.some(c => c.belt === 'BLACK'));
  assert.ok(medium.cards.some(c => c.belt !== 'BLACK' && c.confusions.includes('BLACK')));
});
