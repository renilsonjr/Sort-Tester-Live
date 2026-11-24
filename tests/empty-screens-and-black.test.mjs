// Round 1 of the interface review, last group: #330 (screens ending half-way
// down the phone) and #335 (BLACK disappearing into the night background).
//
// Measured in the running app at 360x440, 375x600, 375x812 and 1440x900,
// night and day.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const belts = readFileSync(join(root, 'src/belts.js'), 'utf8');

// The comments explain the very things that were removed, so a plain search
// would match the prose saying they are gone.
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('#330 the question screen fills the phone, and only the answers grow', () => {
  // Measured at 375x812: buttons 122px -> 231px, the empty band under them
  // 247px -> 28px (the page's own bottom padding), nothing scrolling.
  assert.match(css, /#app\.quiz-page \{ display: flex; flex-direction: column; \}/);
  assert.match(css, /\n  \.quiz-card \{ flex: 1; \}/);
  assert.match(css, /\.quiz-card \.options \{ flex: 1; grid-auto-rows: 1fr; \}/);
  assert.match(css, /\.quiz-card \.belt \{ height: 100%; \}/);
});

test('#330 the column is still packed, not spread', () => {
  // `space-between` would scatter the column, which is exactly what the rule
  // that dropped the stretch was written to stop. Only the answer grid takes
  // the slack; everything above it stays where it was.
  const late = css.slice(css.indexOf('#app.quiz-page { display: flex'));
  assert.doesNotMatch(late, /\.quiz-card \{[^}]*justify-content: space-between/);
  assert.match(css, /\.quiz-card \{ justify-content: flex-start; \}/);
});

test('#330 a screen with no slack is left exactly as it was', () => {
  // The buttons cannot shrink past their own minimum, so at 360x440 the page
  // scrolled by 51px both before and after -- verified by toggling the rules
  // off in the running app. The minimum is what guarantees that.
  assert.match(css, /\.quiz-card \.belt \{ min-height: clamp\(84px, 15dvh, 124px\); \}/);
  assert.match(css, /@media \(max-height: 700px\) \{[\s\S]{0,160}\.quiz-card \.belt \{ min-height: 76px; \}/);
});

test('#335 the BLACK belt colour itself is untouched', () => {
  // Belt colours are routing information. Only how the button is DRAWN
  // changes; the value BELT_STYLE hands to the inline style is the same.
  assert.match(belts, /BLACK:\s+\{ bg: '#000000', fg: '#ffffff' \}/);
  assert.match(app, /return `<button class="belt" data-belt="\$\{belt\}" style="background:\$\{style\.bg\};color:\$\{style\.fg\}">/);
});

test('#335 BLACK gets a border, which is what actually separates it', () => {
  // Measured against the near-black page: the #000 fill is 1.09:1 and the
  // lifted #1f1f1f is 1.17:1 -- the fill cannot do this job at all. The
  // border is 4.67:1 against the page and 4.00:1 against its own fill.
  assert.match(css, /html \.belt\[data-belt="BLACK"\] \{\s*\n\s*border: 2px solid rgba\(255, 255, 255, 0\.42\);/);
  assert.match(css, /html \.belt\[data-belt="BLACK"\] \{[^}]*box-shadow: inset 0 0 0 100px rgba\(255, 255, 255, 0\.12\);/);
});

test('#335 the Ranked button keeps its own highlight and drop shadow', () => {
  // box-shadow replaces, it does not merge, so the Ranked layer's two
  // shadows are restated -- and the 100px fill comes LAST, because the first
  // shadow listed is the one painted on top.
  const rule = css.match(/html \.belts \.belt\[data-belt="BLACK"\] \{([^}]*)\}/)[1];
  assert.match(rule, /inset 0 1px 0 rgba\(255, 255, 255, 0\.22\)/);
  assert.match(rule, /0 10px 20px -12px rgba\(0, 0, 0, 0\.6\)/);
  const lift = rule.indexOf('100px');
  assert.ok(lift > rule.indexOf('0.22') && lift > rule.indexOf('0.6'),
    'the 100px fill must be last or it paints over the highlight');
});

test('#335 the chart chips and the feedback rows are not touched', () => {
  // They carry data-belt too, so the rule is keyed on .belt as well -- and
  // those two are drawn with other classes.
  assert.match(app, /beltChip\(belt, 'lab-belt-chip'\)/);
  assert.match(app, /beltChip\(response\.correctBelt, 'answer'\)/);
  assert.doesNotMatch(app, /beltChip\([^)]*, 'belt'\)/);
  // The unscoped rule that DOES reach all four is the one that was already
  // there -- a 1px ring for the chips and the feedback rows. It stays, and
  // the new rules are scoped to .belt so they never touch it.
  assert.match(css, /\n  \[data-belt="BLACK"\] \{ box-shadow: inset 0 0 0 1px rgba\(255, 255, 255, 0\.55\); \}/);
  for (const m of css.matchAll(/(\S*)\[data-belt="BLACK"\]/g)) {
    assert.ok(m[1] === '' || m[1] === '.belt' || m[1] === 'html[data-theme="day"]',
      `unexpected selector before [data-belt="BLACK"]: ${m[1]}`);
  }
});

test('#335 both themes are drawn the same way, on purpose', () => {
  // The day twin of the pre-existing unscoped rule is
  // `html[data-theme="day"] [data-belt="BLACK"]`, which would outweigh a
  // plain `.belt[...]` rule and give the day theme a different button. The
  // leading `html` is what stops that.
  assert.doesNotMatch(css, /\n  \.belt\[data-belt="BLACK"\] \{/);
  assert.match(css, /\n  html \.belt\[data-belt="BLACK"\] \{/);
});
