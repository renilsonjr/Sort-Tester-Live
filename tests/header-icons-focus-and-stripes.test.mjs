// Round 1 of the interface review: #326 (emoji in the header), #327 (the blue
// focus ring) and #328 (blocks floating with no surface and no eyebrow).
//
// Measured in the running app, 375px and 1440px, night and day, EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

// The comments below explain the very things that were removed, so a plain
// search would match the prose saying they are gone.
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const js = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('#326 the header shows no emoji', () => {
  // The flags, the speaker and the moon. The speaker in particular rendered
  // grey and muddy beside the hand-drawn gold, and every platform draws these
  // differently, so the header looked different on each phone.
  for (const emoji of ['🇺🇸', '🇪🇸', '🔊', '🔇', '🌙', '☀️']) {
    assert.ok(!js.includes(emoji), `${emoji} is back in app.js`);
  }
});

test('#326 the header icons come from the same set as the dock', () => {
  // Not a second icon library and not a separate asset per state: one drawing
  // each, taking its colour from the button through currentColor.
  for (const name of ['soundOn', 'soundOff', 'night', 'day']) {
    assert.match(js, new RegExp(`\\n  ${name}: '<svg viewBox="0 0 24 24">`), `ICONS.${name} is missing`);
  }
  assert.match(js, /function soundIcon\(on\) \{ return on \? ICONS\.soundOn : ICONS\.soundOff; \}/);
  assert.match(js, /function themeIcon\(theme\) \{ return theme === 'day' \? ICONS\.day : ICONS\.night; \}/);
  // The header icons must be in the rule that gives the dock icons their
  // stroke, or they would render as filled black shapes.
  assert.match(css, /\.lab-nav i svg,[^{]*\.lab-btn-ic svg \{[^}]*stroke: currentColor/);
});

test('#326 toggling an icon writes markup, not text', () => {
  // `textContent = '<svg ...>'` would print the SVG source into the button.
  assert.doesNotMatch(js, /button\.textContent = (?:themeIcon|soundIcon)/);
  assert.match(js, /button\.innerHTML = `<span class="lab-btn-ic"[^`]*themeIcon\(next\)/);
  assert.match(js, /button\.innerHTML = `<span class="lab-btn-ic"[^`]*soundIcon\(on\)/);
});

test('#327 no blue is left in a focus ring', () => {
  // Two of them: the token, and a hardcoded #175e94 on the language buttons
  // that the token change alone would have missed.
  assert.doesNotMatch(css, /#6db6ff/);
  // Scoped to the focus rules on purpose: #175e94 is also the colour of
  // `.orb-blue`, a background glow at 0.3 opacity that is not a blue anyone
  // reads as blue. Only the ring was the problem.
  const focusRules = [...css.matchAll(/[^{}]*:focus-visible[^{]*\{[^}]*\}/g)].map(m => m[0]).join('\n');
  assert.ok(focusRules.length, 'the focus rules are gone');
  assert.doesNotMatch(focusRules, /#175e94/);
  assert.doesNotMatch(focusRules, /#6db6ff/);
  // At root the focus ring is the plain gold, now reached through the
  // --gold-ring token it shares with the current-badge ring (#337).
  assert.match(css, /--gold-ring: var\(--gold\);/);
  assert.match(css, /--focus: var\(--gold-ring\);/);
});

test('#327 the day ring is darker than the day gold, and that is deliberate', () => {
  // Measured against the cream page: the day gold is 2.52:1, under the 3:1 a
  // focus ring needs. This deeper brown-gold is 5.05:1. Night uses the plain
  // gold at 10.04:1.
  // #337 gave the current-badge ring the same problem and the same answer,
  // so the value moved behind --gold-ring and --focus points at it. What is
  // checked is unchanged: the day ring resolves to the deeper gold, not to
  // the day --gold.
  const day = css.match(/html\[data-theme="day"\] \{([^}]*)\}/)[1];
  assert.match(day, /--gold-ring: #8a5a12/);
  assert.match(day, /--focus: var\(--gold-ring\)/);
  assert.doesNotMatch(day, /--(?:focus|gold-ring): var\(--gold\)/,
    'the day theme is back on the gold that measured 2.52:1');
});

test('#328 the Shift log is a row in a stripe, like every other block', () => {
  // It was a bare button on the background: no surface, no eyebrow, and it
  // did not read as tappable. It now uses the same row the Leaderboard and
  // See history use -- icon tile, title, line, arrow.
  assert.doesNotMatch(js, /class="lab-log-link"/);
  assert.match(js, /<p class="lab-eyebrow">\$\{esc\(t\('Your sessions'\)\)\}<\/p>\s*\n\s*<button id="viewlog" class="lab-choice"/);
  assert.match(js, /id="viewlog"[\s\S]{0,260}ICONS\.history/);
  assert.match(js, /id="viewlog"[\s\S]{0,400}class="lab-arrow"/);
});

test('#328 the Ranked season line sits on a surface under an eyebrow', () => {
  assert.match(js, /<p class="lab-eyebrow">\$\{esc\(t\('Season'\)\)\}<\/p>\s*\n\s*<p class="rk-note">/);
  const note = css.match(/\n  \.rk-note \{([^}]*)\}/);
  assert.ok(note, '.rk-note has no surface rule');
  assert.match(note[1], /background: var\(--glass-surface-sub\)/);
  assert.match(note[1], /border: 1px solid var\(--glass-border-subtle\)/);
});

test('#328 the disclaimer gets the surface but not an eyebrow', () => {
  // It is the legal small print. A gold heading would announce it above the
  // Practice shortcuts that are the point of the screen.
  const rule = css.match(/\n  \.lab-disclaimer \{ background: var\(--glass-surface-sub\)([^}]*)\}/);
  assert.ok(rule, 'the disclaimer is back to a transparent box');
  // The Home one specifically: it keeps standing on its own, with no stripe
  // and no eyebrow wrapped around it. (Other screens put an eyebrow near a
  // disclaimer for their own reasons; this test is about Home.)
  const home = js.match(/<aside class="lab-disclaimer" aria-label="\$\{esc\(t\('Independent practice'\)\)\}">/);
  assert.ok(home, 'the Home disclaimer moved or was renamed');
  const before = js.slice(0, js.indexOf(home[0])).slice(-200);
  assert.doesNotMatch(before, /lab-eyebrow/, 'the Home disclaimer was given an eyebrow');
});

test('#328 the Profile note is gone, and left no rule behind', () => {
  // #328 gave this note the look of a caption rather than a fourth card,
  // because it explained the four tiles above it. The owner then removed
  // the note itself as one of the sub-labels that say what the screen
  // already shows. There is nothing left to style, so the rule went with
  // it rather than staying as dead CSS.
  assert.doesNotMatch(css, /\.pf-stats-note/);
  assert.doesNotMatch(js, /pf-stats-note/);
});

test('the three new strings have Spanish', () => {
  // The coverage test checks this too, but it only runs in a sandbox on this
  // machine, so the pairs are asserted here where the suite always sees them.
  // Two of the three now: the Shift log's sub-label was removed with the
  // other repeated sub-labels, and its Spanish went with it rather than
  // being left behind for the coverage test to trip over.
  assert.match(i18n, /'Your sessions': 'Tus sesiones'/);
  assert.match(i18n, /'Season': 'Temporada'/);
  assert.doesNotMatch(i18n, /'Your practice results saved on this phone/);
});
