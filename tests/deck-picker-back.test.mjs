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

test('the picker shows a back control before the title and the list of tests', () => {
  const picker = fn('function showDeckPicker');
  const back = picker.indexOf('id="picker-back"');
  assert.notEqual(back, -1, 'the picker has no back control at the top');
  assert.ok(back < picker.indexOf("t('Pick a test')"), 'back comes before the title');
  assert.ok(back < picker.indexOf('class="decks"'), 'back comes before the list');
});

test('back returns to the Practice screen the player came from', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /#picker-back'\)\.addEventListener\('click', showPractice\)/);
});

test('the back label is a translated word, with Spanish', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /id="picker-back"[^>]*>← \$\{esc\(t\('Back'\)\)\}/);
  assert.match(i18n, /'Back': 'Volver'/);
});

test('the controls under the list stay, for a player who scrolled down', () => {
  const picker = fn('function showDeckPicker');
  assert.match(picker, /id="back"/);
  assert.match(picker, /id="main-page"/);
});
