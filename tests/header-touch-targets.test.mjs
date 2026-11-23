// The header controls (EN, ES, sound, theme) are drawn at 40x38 so the compact
// header stays compact, but a finger needs 44x44. The tappable box is pushed
// out with a pseudo-element instead of by growing the buttons.
//
// Growing them is not an option worth reopening: four 44px buttons plus their
// gaps add 16px to a row that already ends 18px from the edge of a 375px
// screen, and the app name sits beside it.
//
// Measured in the running app after the change, at 375px and 1440px, in both
// themes: hit box 44x44 on every one of them, a point 1.5px outside the drawn
// edge hit-tests to the button on all four sides, and no two hit areas touch
// (the buttons sit 6-7px apart, and 2px of growth each leaves 2-3px).

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

const HIT = /\.lab-language button::after,\s*\.lab-theme-btn::after\s*\{([^}]*)\}/;

// The rule carries a long comment that names the very things these tests
// assert are absent, so the declarations have to be read without it.
function declarations() {
  const match = html.match(HIT);
  assert.ok(match, 'the hit-area pseudo-element is gone');
  return match[1].replace(/\/\*[\s\S]*?\*\//g, '');
}

test('the header controls carry a 44x44 hit area', () => {
  const body = declarations();
  assert.match(body, /width:\s*44px/);
  assert.match(body, /height:\s*44px/);
  assert.match(body, /position:\s*absolute/);
});

test('the hit area is sized outright, not with a negative inset', () => {
  const body = declarations();
  // An absolutely positioned child resolves its offsets against the padding
  // box, which has already had the 1px border and the 2px padding taken off.
  // `inset: -3px -2px` measured 40x40 in the browser, not the 44x44 it reads
  // like. Centring a box of a stated size does not care about either.
  assert.doesNotMatch(body, /inset:/,
    'a negative inset silently under-sizes this; state the size and centre it');
  assert.match(body, /transform:\s*translate\(-50%,\s*-50%\)/);
});

test('the buttons keep their drawn size, so the header stays compact', () => {
  // Measured before and after: header 61px either way, nothing moved.
  assert.match(html, /\.lab-language button, \.lab-theme-btn \{ width: 40px; min-height: 38px;/);
});

test('the hit area is invisible', () => {
  const body = declarations();
  assert.doesNotMatch(body, /background/, 'this is a hit area, not something to look at');
  assert.match(body, /content:\s*""/);
});

test('the containing block exists, or the hit area lands on the page', () => {
  assert.match(html, /\.lab-language button, \.lab-theme-btn \{ position: relative; \}/);
});

test('the quiz header draws the controls at the same width as everywhere else', () => {
  // It drew them at 38px, which made the hit area 42px wide on that screen
  // alone and the one measurement that matters inconsistent between screens.
  assert.match(html, /\.quiz-topline \.lab-language button \{ width: 40px; \}/);
});
