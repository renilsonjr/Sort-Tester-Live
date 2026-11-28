// The Practice test picker (issue #262). Its only ways out used to sit under
// the whole list of tests, about two screens down on a phone, so a player who
// opened it saw no way back. The back control now comes before the list.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { screensSource } from './helpers/screens-source.mjs';

const app = screensSource();
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('the picker shows a back control before the title and the list of tests', () => {
  const picker = fn('function showDeckPicker');
  // The markup moved into the shared backLink() helper in #331, so the app
  // has one Back rather than a copy per screen. What this test is about is
  // unchanged: the picker's way out comes before the title and the list.
  const back = picker.indexOf("backLink('picker-back')");
  assert.notEqual(back, -1, 'the picker has no back control at the top');
  assert.ok(back < picker.indexOf("t('Pick a test')"), 'back comes before the title');
  assert.ok(back < picker.indexOf('class="decks"'), 'back comes before the list');
});

test('back returns to the Practice screen the player came from', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /#picker-back'\)\.addEventListener\('click', showPractice\)/);
});

test('the back label is a translated word, with Spanish', () => {
  const helper = fn('function backLink');
  assert.match(helper, /id="\$\{id\}" class="lab-back"/);
  assert.match(helper, /<span aria-hidden="true">←<\/span> \$\{esc\(t\('Back'\)\)\}/);
  assert.match(i18n, /'Back': 'Volver'/);
});

test('the Profile sub-screens use the same Back, not a second one', () => {
  // Both places had their own full-width ghost button, which is the shape of
  // a primary action above content it should be subordinate to (#331).
  assert.match(app, /backLink\('profile-back'\)/);
  assert.doesNotMatch(app, /back\.textContent = `← \$\{t\('Back'\)\}`/,
    'the Profile built its own Back again');
});

test('the controls under the list stay, for a player who scrolled down', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /id="back"/);
  assert.match(picker, /id="main-page"/);
});
