// #440: the two character icons that are not tiles, left out of #404 on
// purpose because each needed its own measuring.
//
// Measured in the running app at 375x812, playing a real practice question
// and with a hat holder forced onto the podium:
//
//   .rq-mark   a 22px glyph in a 48px circle, 16.8px of ink. The issue said
//              26px; that is the base rule, and nothing renders it -- both
//              call sites sit inside .rq-head or .quiz-verdict, which set
//              22px. Corrected on the issue.
//   .pcrown    16px, 9.6px of ink.
//   .pdisc     the same crown AGAIN, 18px in a 46-56px circle: 10.8px of
//              ink, where the two players who did not win show a 20.3px
//              initial or a 36px avatar. The winner had the emptiest disc
//              on the podium. That third site was not in the issue; it is
//              the same glyph on the same row.
//
// The font is Nunito, which has none of these characters. The feedback
// mark is the one that matters most: it is the app's answer to "did I get
// it right", on both Ranked and Practice, drawn by whatever font the
// device happens to fall back to.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#440 neither glyph is left in the app', () => {
  for (const glyph of ['✓', '✕', '♛']) {
    assert.doesNotMatch(app, new RegExp(glyph), `${glyph} is still in app.js`);
    const hex = glyph.codePointAt(0).toString(16).padStart(4, '0');
    assert.ok(!app.includes(`\\u${hex}`), `${glyph} is still there as an escape`);
  }
});

test('#440 both feedback screens draw the verdict', () => {
  // Ranked (showRankedFeedback) and Practice (the quiz feedback screen)
  // share the component, so they must not drift apart.
  const marks = app.match(/class="rq-mark \$\{right \? 'good' : 'bad'\}" aria-hidden="true">\$\{right \? ICONS\.verdictGood : ICONS\.verdictBad\}/g) ?? [];
  assert.equal(marks.length, 2, 'expected the Ranked and Practice verdict marks');
});

test('#440 the crown is drawn, and #443 left it in one place', () => {
  // #440 found the crown in THREE places -- floating above the winner's
  // disc, inside the disc where everyone else shows an avatar, and below
  // the podium where it replaced the place number -- and drew all three.
  // #443 then took two of them away: a mark that displaces the identity it
  // is marking is worse than one that sits beside it. What #440 was really
  // guarding was that the crown is drawn rather than typed, and that holds.
  assert.match(app, /<div class="pcrown" aria-hidden="true">\$\{ICONS\.prizeHolder\}<\/div>/);
  assert.equal((app.match(/ICONS\.prizeHolder/g) ?? []).length, 1);
  // and the two it was taken out of show what every other player shows
  assert.match(app, /<div class="pdisc\$\{avatarEmoji\(row\.avatar\) \? ' has-avatar' : ''\}">\$\{avatarEmoji\(row\.avatar\) \|\| esc\(row\.username\.slice\(0, 1\)\.toUpperCase\(\)\)\}<\/div>/);
  assert.match(app, /<span class="board-place">\$\{row\.place\}<\/span>/);
});

test('#440 the badge marks are heavier than the list icons', () => {
  // Each replaces a font-weight 900 glyph. At 22px a 2 stroke reads thin
  // for a verdict; 2.8 reads clumsy. Compared at all three weights against
  // the real screen before picking 2.4.
  assert.match(css, /\.rq-mark svg, \.pcrown svg \{[^}]*stroke-width: 2\.4;/);
  assert.match(css, /\.lab-nav i svg,[^}]*stroke-width: 2;/);
});

test('#440 the verdict mark follows the font-size its screen declares', () => {
  // Three contexts already declare one -- 26px on the unused base, 22px in
  // .rq-head and .quiz-verdict. `em` means they go on deciding, and a
  // fourth context would need no new rule.
  assert.match(css, /\.rq-mark svg, \.pcrown svg \{[^}]*width: 1em; height: 1em;/);
  assert.match(css, /\.rq-head \.rq-mark \{[^}]*font-size: 22px;/);
  assert.match(css, /\.quiz-verdict \.rq-mark \{[^}]*font-size: 22px;/);
});

test('#443 nothing sizes a mark inside the disc any more', () => {
  // #440 gave .pdisc its own 28/36px overrides, because `em` there is 18px
  // and the crown it had to show was 10.8px of ink in a 56px circle. #443
  // took the crown out of the disc, so those overrides size nothing and
  // are gone rather than left behind to confuse the next reader.
  assert.doesNotMatch(css, /\.pdisc svg/);
  assert.doesNotMatch(css, /\.board-place svg/);
});

test('#440 the marks take their colour from the state, not from the drawing', () => {
  // currentColor is what lets one drawing serve good, bad, the gold crown
  // and both themes. An inline fill or stroke would freeze it.
  for (const name of ['verdictGood', 'verdictBad', 'prizeHolder']) {
    const line = app.match(new RegExp(`^  ${name}: '(.*)',$`, 'm'));
    assert.ok(line, `${name} is gone from ICONS`);
    assert.match(line[1], /^<svg viewBox="0 0 24 24">/, `${name} is off the shared grid`);
    assert.doesNotMatch(line[1], /\b(?:fill|stroke|style)=/, `${name} paints itself`);
  }
  assert.match(css, /\.rq-mark\.good \{ color: var\(--good\);/);
  assert.match(css, /\.rq-mark\.bad \{ color: var\(--bad\);/);
  assert.match(css, /\.pcrown \{ font-size: 16px; color: var\(--gold\);/);
});
