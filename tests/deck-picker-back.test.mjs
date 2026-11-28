// The Practice test picker (issue #262). Its only ways out used to sit under
// the whole list of tests, about two screens down on a phone, so a player who
// opened it saw no way back. The back control now comes before the list.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('the list of tests is the Practice tab, so it needs no Back', () => {
  // #262 put a Back before the title because the ways out were under a
  // 1665px list. Since 2026-11-27 the list IS the tab: the dock is on the
  // screen and there is nowhere to go back to.
  const picker = fn('function showDeckPicker');
  assert.doesNotMatch(picker, /backLink\(/);
  assert.match(fn('function showPractice'), /showDeckPicker\(practiceName\)/);
  assert.match(picker, /class="lab-screen screen-practice"/);
});

test('the name screen goes back to the list, and leaves the name alone', () => {
  const name = fn('function showNameEntry');
  assert.match(name, /\$\{backLink\('name-back'\)\}/);
  assert.match(name, /#name-back'\)\.addEventListener\('click', showPractice\)/);
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

test('what was under the list is one line: who is playing, the name, the log', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /id="practice-name" class="practice-link"/);
  assert.match(picker, /id="viewlog" class="practice-link"/);
  assert.match(picker, /#practice-name'\)\.addEventListener\('click', \(\) => showNameEntry\(practiceName\)\)/);
  // "Main page" duplicated the dock's first tab.
  assert.doesNotMatch(picker, /id="main-page"/);
});
