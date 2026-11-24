// Round 3: #387. On the results screen the same sentence closed nearly every
// missed row -- "Check the service and the range before choosing a belt."
// Counted in the running app at 375x812: 10 of 12 rows in one run, 11 of 13
// in another. It is advice, not a fact about that route, so the eye learns
// to stop reading -- including on the rows that do say something different.
//
// Spanish never carried it: the same two runs had 12 of 12 distinct endings.
// So English was the outlier, and this also makes the two languages say the
// same thing.

import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const levels = readFileSync(join(root, 'src/levels.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

const ADVICE = 'Check the service and the range before choosing a belt.';

// The browser files are plain .js with query-string imports; this Mac has no
// package.json saying "module", so they load through the shared sandbox.
const { modules: [{ LEVEL_DECKS }], cleanup } = await loadAppModules(['src/levels.js']);
after(cleanup);

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#387 no generated card ends with the advice any more', () => {
  // The real deck data, not a grep: every chart-built card in every level
  // deck. These are the cards that carried the repeat; the hand-written
  // ones in decks.js never did.
  const cards = LEVEL_DECKS.flatMap((deck) => deck.cards ?? []);
  assert.ok(cards.length > 50, `only ${cards.length} cards to check`);
  const repeats = cards.filter((card) => card.why.includes(ADVICE));
  assert.equal(repeats.length, 0, `${repeats.length} cards still end with the advice`);
});

test('#387 every generated card still states its own route', () => {
  // Removing the tail must not have eaten the sentence that carries the
  // fact -- the state, the range and the right belt.
  assert.match(levels, /On the Twilight \$\{service\} chart, \$\{state\} \$\{code\} goes to \$\{belt\}\.`,/);
});

test('#387 the advice is said once, over the list', () => {
  // Under the MISSED heading and above the first row, so it reads as one
  // instruction for the list instead of a tail on each item.
  const start = app.indexOf("<h2>${esc(t('Missed'))}</h2>");
  assert.notEqual(start, -1, 'the Missed heading is gone');
  const block = app.slice(start, app.indexOf('<ul class="missed">', start));
  assert.match(block, new RegExp(`<p class="lab-intro">\\$\\{esc\\(t\\('${ADVICE.replace(/[.]/g, '\\.')}'\\)\\)\\}</p>`));
});

test('#387 the line is said in Spanish too', () => {
  // It had no Spanish at all before, because Spanish never carried the tail.
  // "color", not "faja": the word the rest of the app uses for a belt.
  assert.match(i18n, new RegExp(`'${ADVICE.replace(/[.]/g, '\\.')}': 'Revisa el servicio y el rango antes de elegir un color\\.'`));
});

test('#387 the line sits on the screen gap, not on its own margin', () => {
  // .lab-intro carries an 8px bottom margin for stacked shell screens. Here
  // it landed on top of the column's 12px gap: 12px above the line, 20px
  // below. Measured again after this rule: 12 and 12.
  const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
  assert.match(css, /\.screen-results > \.lab-intro \{ margin-bottom: 0; \}/);
});
