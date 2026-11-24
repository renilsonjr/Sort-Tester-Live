// Round 4: #418. The Settings chip in the Profile sub-header was 90x33 while
// the language and theme buttons directly above it are 44x44 and the dock
// buttons below are 86x46. Measured in the running app at 375x812.
//
// Growing the chip itself would have pushed the sub-header down on every
// Profile screen, so the hit area is extended with a pseudo-element and the
// chip is unchanged to look at. Measured after: visible 33px at y=63..96,
// hit area 45px at 58..101, header still 108px tall, and the nearest other
// control (the theme button) ends at y=55 -- 2px clear, no overlap.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#418 the chip reaches the touch minimum through a pseudo-element', () => {
  assert.match(css, /\.lab-settings-btn \{ position: relative; \}/);
  assert.match(css, /\.lab-settings-btn::after \{ content: ""; position: absolute; inset: -6px 0; \}/);
});

test('#418 the chip itself did not grow', () => {
  // The point of the pseudo-element: no min-height, no taller padding, so
  // the sub-header is the same height on every screen that shows it.
  const rule = css.match(/\n  \.lab-settings-btn \{[^}]*flex: none;[^}]*\}/)?.[0] ?? '';
  assert.notEqual(rule, '', 'the chip rule is gone');
  assert.doesNotMatch(rule, /min-height/);
  assert.match(rule, /padding: 7px 13px/);
});

test('#418 the extension is vertical only', () => {
  // The chip is already 90px wide. Widening it sideways would have reached
  // under the site line beside it, which is not a control but is text the
  // player may try to select.
  assert.match(css, /\.lab-settings-btn::after \{[^}]*inset: -6px 0;/);
});
