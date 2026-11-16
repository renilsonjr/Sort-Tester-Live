import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('index.html contains belt-correct and belt-incorrect animation styles', () => {
  assert.match(html, /\.belt\.belt-correct|\.belt-correct/);
  assert.match(html, /\.belt\.belt-incorrect|\.belt-incorrect/);
  assert.match(html, /@keyframes\s+correctGlow/);
  assert.match(html, /@keyframes\s+incorrectShake/);
});

test('index.html provides prefers-reduced-motion fallback for feedback animations', () => {
  assert.match(html, /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/);
  assert.match(html, /animation:\s*none\s*!important/);
});
