// The selected language chip was the hardest thing in the header to read.
//
// Measured in the running app at 375x812, in both themes: the pressed chip
// painted near-white ink (#fffdf8) on the cream fill (#f7eac7) it inherits
// from an earlier skin layer -- 1.18:1, against 4.5:1. The chip that says
// which language you ARE in was less legible than the one you are not, on
// every screen of the app, because the header carries it everywhere.
//
// The cause is the layering: "Language toggle as glass" restyled the
// unpressed chips and set the pressed one's ink, but never cleared the
// older background, so the two rules combined into cream-on-white.
//
// After: the gold tint, the gold border and gold ink, which composites to
// 7.94:1 over the header at night and reads as the deeper gold by day.

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

test('the selected language chip sets its own fill, not just its ink', () => {
  // The last rule wins, and it has to name the background: naming only the
  // colour is exactly how this broke.
  const rules = [...css.matchAll(/\.lab-language button\[aria-pressed="true"\] \{([^}]*)\}/g)].map(m => m[1]);
  assert.ok(rules.length > 0, 'the pressed rule is gone');
  const last = rules[rules.length - 1];
  assert.match(last, /background:/, 'the winning rule must set the fill it paints on');
  assert.match(last, /color:/);
});

test('selected is marked the way the rest of the app marks it', () => {
  const rules = [...css.matchAll(/\.lab-language button\[aria-pressed="true"\] \{([^}]*)\}/g)].map(m => m[1]);
  const last = rules[rules.length - 1];
  assert.match(last, /color: var\(--gold\)/);
  assert.match(last, /background: var\(--soft\)/);
  assert.match(last, /border-color: var\(--gold\)/);
});

test('the cream fill is no longer what the selected chip ends up with', () => {
  // #f7eac7 may still be set by an older layer; what must not happen is a
  // later rule leaving it as the painted background under light ink.
  const rules = [...css.matchAll(/\.lab-language button\[aria-pressed="true"\] \{([^}]*)\}/g)].map(m => m[1]);
  const last = rules[rules.length - 1];
  assert.doesNotMatch(last, /#f7eac7/);
  assert.doesNotMatch(last, /color: var\(--ink\)/);
});
