// #451: the login screen links to the player manual, a PDF per language.
import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';

const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');

test('the login screen has a How to play link that opens the manual in a new tab', () => {
  assert.match(auth, /<a id="auth-howto" class="auth-howto" href="\$\{manualHref\(\)\}" target="_blank" rel="noopener">/);
  assert.match(auth, /forgotText\('How to play'\)/);
});

test('the link follows the chosen language', () => {
  assert.match(auth, /assets\/manual\/sortquiz-manual-\$\{forgotText\('How to play'\) === 'How to play' \? 'en' : 'es'\}\.pdf/);
  assert.match(auth, /'How to play':\s*'Cómo jugar'/);
  assert.match(auth, /'Sign up, play, and how to win a hat\.':\s*'[^']+'/);
});

test('both manual PDFs exist where the link points', () => {
  for (const language of ['en', 'es']) {
    const pdf = new URL(`../assets/manual/sortquiz-manual-${language}.pdf`, import.meta.url);
    assert.ok(existsSync(pdf), `missing ${language} manual`);
    assert.equal(readFileSync(pdf).subarray(0, 5).toString(), '%PDF-');
  }
});
