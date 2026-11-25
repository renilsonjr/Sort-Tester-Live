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
  assert.match(auth, /assets\/manual\/sortquiz-manual-\$\{forgotText\('How to play'\) === 'How to play' \? 'en' : 'es'\}\.pdf\?v=\$\{MANUAL_VERSION\}/);
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

test('the manual keeps part 5, the ZIP chart built from the Ranked bank', () => {
  // 2026-11-25: part 5 was pushed after #455 merged and never reached main.
  for (const language of ['en', 'es']) {
    const text = readFileSync(new URL(`../docs/player-manual/manual.${language}.md`, import.meta.url), 'utf8');
    assert.match(text, /^## 5\. /m, `${language} manual has no part 5`);
    assert.match(text, /^<!-- ZIP-TABLE -->$/m);
  }
  const build = readFileSync(new URL('../docs/player-manual/build_pdf.py', import.meta.url), 'utf8');
  assert.match(build, /def zip_tables\(language\)/);
  assert.match(build, /routes-v1\.json/);
});
