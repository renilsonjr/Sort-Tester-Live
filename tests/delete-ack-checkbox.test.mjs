// Round 4: #419. The acknowledgement on the delete-account screen was the
// native OS checkbox -- `appearance: auto`, 22x22, merely tinted with
// accent-color -- while the account-creation screen draws its own. The app
// drew every control except the one on its single irreversible action.
//
// Measured after, at 375x812: the input is 0x0 and invisible, the drawn
// .check-box is 22x22 with the gold border, one click on the sentence ticks
// it (no double-toggle from the label's `for`), the fill goes gold and the
// second step reveals.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { screensSource } from './helpers/screens-source.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = screensSource();
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#419 the delete acknowledgement draws the app\'s box', () => {
  assert.match(app, /<label class="delete-ack" for="delete-ack">\s*<input type="checkbox" id="delete-ack">\s*<span class="check-box" aria-hidden="true"><\/span>/);
});

test('#419 the native input is hidden, not merely tinted', () => {
  assert.match(css, /\.check-row input, \.delete-ack input \{ position: absolute; opacity: 0; width: 0; height: 0; \}/);
  assert.doesNotMatch(css, /\.delete-ack input \{[^}]*accent-color/);
});

test('#419 both screens share one set of selectors', () => {
  // So the two boxes cannot drift apart again: checked and focus states are
  // written once for .check-row and .delete-ack together.
  for (const state of ['checked', 'focus-visible']) {
    assert.match(css, new RegExp(`\\.check-row input:${state} \\+ \\.check-box[^{]*, \\.delete-ack input:${state} \\+ \\.check-box`),
      `the ${state} state is not shared`);
  }
});

test('#419 the tick is dark on the gold fill, in both themes', () => {
  // --accent-ink is #fffdf8 at night and the box is gold in BOTH themes, so
  // the tick used to be white on gold: measured 1.70:1. The fill does not
  // follow the theme, so the tick must not either. #38261b is the ink the
  // app already puts on gold: 8.37:1 at night, 4.88:1 by day.
  const box = css.match(/\.check-box::after \{[^}]*\}/)?.[0] ?? '';
  assert.match(box, /color: #38261b;/);
  assert.doesNotMatch(box, /var\(--accent-ink\)/);
});
