// Practice, regrouped (2026-11-27): the tab is the list of tests. It was a
// screen with two buttons, then a screen for an optional name, then a list
// 1665px tall with a card for each test.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(head) {
  const from = app.slice(app.indexOf(head));
  return from.slice(0, from.indexOf('\n}\n'));
}
const picker = fn('function showDeckPicker');

test('one tap from the tab to a test', () => {
  assert.match(fn('function showPractice'), /showDeckPicker\(practiceName\)/);
  assert.match(picker, /id="study" class="lab-choice"/);
  assert.equal((picker.match(/class="decks decks-card"/g) ?? []).length, 2);
});

test('the name is optional, offered from the list, and kept between tests', () => {
  assert.match(app, /\nlet practiceName = '';/);
  assert.match(picker, /practiceName = name \?\? '';/);
  assert.match(picker, /t\(practiceName \? 'Change name' : 'Add a name'\)/);
  assert.match(picker, /displayName\(practiceName\)/);
  // The run is named from what the list shows, so the Shift log agrees.
  assert.match(picker, /createRun\(\{ name: practiceName, cards: selectLevelCards\(deck\) \}\)/);
  assert.match(fn('function showNameEntry'), /practiceName = nameInput\.value\.trim\(\);/);
});

test('each row says how many, once; a screen reader still gets the sentence', () => {
  const row = fn('function deckRow');
  assert.match(row, /class="lab-choice-meta\$\{count === null \? '' : ' sr-only'\}"/);
  assert.match(row, /<span class="deck-count" aria-hidden="true">\$\{esc\(count\)\}<\/span>/);
  // The seconds are said once above the lists.
  assert.match(picker, /t\('\{seconds\} seconds for each card\.', \{ seconds: CARD_SECONDS \}\)/);
});

test('a test that cannot be played keeps its reason in view', () => {
  assert.match(picker, /count: deck\.verified \? \(deck\.practiceRunSize \?\? deck\.cards\.length\) : null,/);
});

test('each group is one card, and its rows are concentric with it', () => {
  assert.match(html, /\n  \.lab-main \.decks-card \{ gap: 2px; margin: 0; padding: 6px; border-radius: var\(--r-md\);/);
  assert.match(html, /\n  \.lab-main \.decks-card \.lab-choice \{[^}]*padding: 10px; border: 0; border-radius: 16px; background: none;/);
});

test('the two text controls under the list are full touch targets', () => {
  assert.match(html, /\n  \.practice-link \{ min-height: 44px;[^}]*color: var\(--gold-ring\);/);
});

test('on a desktop the chart row and the name line cross both columns', () => {
  const desk = html.slice(html.lastIndexOf('@media (min-width: 900px)'));
  assert.match(desk, /\.screen-practice > \.practice-learn,\s*\.screen-practice > \.practice-who \{ grid-column: 1 \/ -1; \}/);
});

test('the new words have Spanish, and the retired ones are gone', () => {
  for (const key of ['Playing as', 'Add a name', 'Change name', '{seconds} seconds for each card.']) {
    assert.ok(i18n.includes(`'${key}': '`), `no Spanish for: ${key}`);
  }
  for (const gone of ['The chart', 'Take a quiz', 'Test yourself', 'Back to home', 'Edit name (optional)']) {
    assert.ok(!i18n.includes(`'${gone}': '`), `${gone} is still translated but nothing shows it`);
    assert.ok(!app.includes(`t('${gone}')`), `${gone} is still on a screen`);
  }
});
