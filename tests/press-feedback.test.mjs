// Nothing but the quiz belts responded to a finger: Continue, Start Ranked
// quiz, Log in, the Practice cards, the Home shortcuts and the dock all stayed
// completely still under a press. On a phone that small give is the only
// confirmation a player gets before the screen changes (#345).
//
// 0.96 exactly, on every control: below 0.95 the press reads as exaggerated,
// and the belts used a value of their own (0.97) before this.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

test('every tappable control gives way when pressed', () => {
  for (const selector of ['.primary', '.ghost', '.lab-choice', '.home-short', '.lab-nav button', '.belt']) {
    assert.ok(
      html.includes(`${selector}:active`),
      `${selector} still does not respond to a press`,
    );
  }
  assert.match(html, /\.belts \.belt:active \{ transform: scale\(\.96\); \}/);
  // `.belt` is listed separately from `.belts .belt`: the Ranked quiz draws
  // its belts inside `.belts`, the Practice quiz inside `.options`, so the
  // Ranked-only pair never reached the Practice belts and the two quizzes
  // felt different under the same finger. Found by measuring, not reading.
});

test('the press is 0.96 everywhere, never smaller', () => {
  const presses = [...html.matchAll(/:active[^{]*\{[^}]*transform:\s*scale\(([.\d]+)\)/g)]
    .map(m => Number(m[1]));
  assert.ok(presses.length >= 2, 'the press feedback rules are gone');
  for (const value of presses) {
    assert.ok(value >= 0.95, `scale(${value}) is below 0.95 and reads as exaggerated`);
    assert.equal(value, 0.96, `scale(${value}) should be the shared 0.96`);
  }
});

test('the press transition names its properties instead of animating all', () => {
  const rule = html.match(/\.primary, \.ghost, \.lab-choice, \.home-short, \.lab-nav button, \.belt \{([^}]*)\}/);
  assert.ok(rule, 'the press transition rule is gone');
  assert.match(rule[1], /transition-property:\s*transform/);
  assert.doesNotMatch(rule[1], /transition:\s*all/);
});

test('a disabled button does not pretend to respond', () => {
  assert.match(html, /\.primary:disabled:active, \.ghost:disabled:active \{ transform: none; \}/);
});
