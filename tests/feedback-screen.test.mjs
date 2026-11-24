// Round 3: #383 (the feedback screen ended two-thirds of the way down) and
// #384 (the sentence that teaches was the only block with no surface).
//
// Measured in the running app at 360x440, 375x812 and 1440x900, night and
// day, EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  // Twice in this review I ended a block of comment prose with a second
  // `*/` after the comment had already closed. The parser then swallows the
  // rule that follows -- once it made the selected chart chip white on
  // white, once it silently dropped these two rules -- and the page still
  // loads, so nothing complains. This catches it.
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  const opens = (style.match(/\/\*/g) ?? []).length;
  const closes = (style.match(/\*\//g) ?? []).length;
  assert.equal(opens, closes, `${opens} "/*" against ${closes} "*/" in the stylesheet`);
  // And no stray close left over once every real comment is removed.
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//,
    'a "*/" survives with no "/*" opening it');
});

test('#383 the feedback screen fills the page', () => {
  // 242px of empty background under Continue at 375x812, while the question
  // screen it alternates with fills the phone since #330.
  assert.match(css, /\.quiz-feedback \{ flex: 1; \}/);
});

test('#383 Continue is pinned to the bottom, and only Continue', () => {
  // The stop panel is a child of this same section, so a descendant
  // selector also caught its "Keep going" button and pushed it to the
  // bottom of that centred panel. Verified in the running app: the three
  // stop-panel buttons sit 12px apart, unchanged.
  assert.match(css, /\.quiz-feedback > \.primary \{ margin-top: auto; \}/);
  assert.doesNotMatch(css, /\.quiz-feedback \.primary \{ margin-top: auto/);
});

test('#384 the explanation gets a surface and a name', () => {
  // It was the only block on the screen with no background and no border,
  // at 13px muted, while the route and the comparison both sat on glass --
  // and it is the one sentence that teaches the chart.
  const rule = css.match(/\.quiz-feedback \.why \{([^}]*)\}/g);
  assert.ok(rule, 'the .why rule is gone');
  const live = rule[rule.length - 1];
  assert.match(live, /background: var\(--glass-surface-sub\)/);
  assert.match(live, /border: 1px solid var\(--glass-border\)/);
  assert.match(live, /color: var\(--ink\)/);
  assert.match(live, /font-size: 14px/);
  assert.doesNotMatch(live, /color: var\(--muted\)/);
});

test('#384 the eyebrow sits over the explanation, and has Spanish', () => {
  assert.match(app, /<p class="lab-eyebrow">\$\{esc\(t\('Why'\)\)\}<\/p>\s*\n\s*<p class="why">/);
  assert.match(i18n, /'Why': 'Por qué'/);
  // It pairs with the one over the comparison.
  assert.match(app, /<p class="lab-eyebrow">\$\{esc\(t\('Answer'\)\)\}<\/p>/);
});
