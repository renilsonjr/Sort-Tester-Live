// Round 3: #388. The player's name sat between the score card and the MISSED
// list on its own -- no label, no eyebrow, no surface. Measured against main
// at 375x812: 335x20, transparent, no border. Every other value on the screen
// says what it is (SCORE under 5/15, TIME under 0:26); this one said nothing.
//
// It is who the result belongs to, so it is the card's first line now, across
// both columns with the hairline under it -- the same shape a Shift log row
// already uses: the name, then the score. Measured after at 375x812: inside
// the card, 313px wide, 10px above the rule and 12px under it, and nothing
// left loose on the page.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

function body(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} is gone`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
}

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#388 the name is the first line inside the score card', () => {
  const results = body('renderResults');
  const card = results.slice(results.indexOf('<div class="score-line">'), results.indexOf('</div>\n      ${summary.deck'));
  assert.match(card, /<div class="score-line">\s*<div class="who">\$\{esc\(displayName\(summary\.name\)\)\}<\/div>/);
});

test('#388 nothing is left floating between the card and the list', () => {
  // The old loose div, and the rule that styled it, both go.
  const results = body('renderResults');
  assert.doesNotMatch(results, /<\/div>\s*<div class="who">/);
  assert.doesNotMatch(css, /\.score-line ~ \.who/);
});

test('#388 it spans both columns and carries the rule', () => {
  assert.match(css, /\.score-line > \.who \{[^}]*grid-column: 1 \/ -1;[^}]*border-bottom: 1px solid var\(--glass-border\);/);
});

test('#388 the divider stays between the two stat cells', () => {
  // `div + div` would now put a left border on the first stat, because the
  // name is the div before it. The cells are named instead.
  assert.match(css, /\.score-line > \.stat \+ \.stat \{ border-left/);
  assert.doesNotMatch(css, /\.score-line > div \+ div/);
  const results = body('renderResults');
  assert.equal((results.match(/<div class="stat">/g) ?? []).length, 2);
});

test('#388 a long ID cannot break the card', () => {
  // The field it comes from has no maxlength and takes an ID as readily as
  // a name. One unbroken 40-character token pushed the page 133px wide at
  // 320 before this; measured 0 after, wrapping to two lines.
  assert.match(css, /\.score-line > \.who \{[^}]*overflow-wrap: anywhere;/);
  assert.doesNotMatch(app, /id="name"[^>]*maxlength/);
});

test('#388 the Shift log row keeps its own name styling', () => {
  // `.score-line ~ .who` never reached the log, and the base .who rule that
  // does is untouched: 18px / 600, measured unchanged.
  assert.match(body('showLog'), /<span class="who">\$\{esc\(displayName\(s\.name\)\)\}<\/span>/);
  assert.match(css, /\n  \.who \{ font-size: 18px; font-weight: 600; \}/);
});
