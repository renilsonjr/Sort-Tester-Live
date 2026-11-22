import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createLanguage } from '../src/i18n.js';

// The app is English and Spanish. A sentence passed to t() with no Spanish
// entry is shown in English to a Spanish reader, silently. On 2026-11-22
// that was 216 sentences: nearly all of Ranked, the tie-break and the owner
// tools. This reads every literal key out of app.js and asks the real
// dictionary for it.
const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');

function literalKeys() {
  const keys = new Set();
  const read = (raw) => new Function(`return '${raw}'`)();
  const direct = /\bt\(\s*'((?:[^'\\]|\\.)*)'/g;
  for (const m of source.matchAll(direct)) keys.add(read(m[1]));
  // t(condition ? 'one' : 'other')
  const chosen = /\bt\(\s*[^'"`)][^)]*?\?\s*'((?:[^'\\]|\\.)*)'\s*:\s*'((?:[^'\\]|\\.)*)'/gs;
  for (const m of source.matchAll(chosen)) { keys.add(read(m[1])); keys.add(read(m[2])); }
  return [...keys];
}

// Words that are the same in both languages, on purpose.
const SAME = new Set(['Twilight', 'Ranked ID']);

test('every sentence app.js shows has a Spanish entry', () => {
  const es = createLanguage(null);
  es.set('es');
  const keys = literalKeys();
  assert.ok(keys.length > 300, `expected to find the app's sentences, found ${keys.length}`);
  const missing = keys.filter((key) => /[A-Za-z]{2}/.test(key) && !SAME.has(key) && es.text(key) === key);
  assert.deepEqual(missing, []);
});

test('placeholders survive translation', () => {
  const es = createLanguage(null);
  es.set('es');
  assert.equal(es.text('You scored {score} of 5 in round {round}.', { score: 3, round: 2 }), 'Acertaste 3 de 5 en la ronda 2.');
  assert.equal(es.text('You did not play round {round}.', { round: 1 }), 'No jugaste la ronda 1.');
});
