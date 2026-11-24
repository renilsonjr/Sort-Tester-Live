// Round 1 of the interface review, second group: #329 (the balance line
// repeated its own number), #336 (empty Profile tiles showed a dash that
// reads as an error) and #337 (the climb row did not show which badge is
// yours).
//
// Measured in the running app on a brand-new account, 375px / 820px /
// 1440px, night and day, EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

// The comments explain the very things that were removed, so a plain search
// would match the prose saying they are gone.
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const js = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('#329 the balance line no longer says the number twice', () => {
  // It read "Iron - 1,000 points to the cap (1,000)". The parenthetical was
  // the cap, which the sentence had already given.
  assert.doesNotMatch(js, /points to the cap'\)/, "the old 'points to the cap' line is back");
  assert.doesNotMatch(i18n, /^\s*'points to the cap':/m, 'the dead Spanish entry is back');
  // "Iron - 0 / 1,000 to Bronze"
  assert.match(js, /const progress = `\$\{entry\.points\.toLocaleString\(\)\} \/ \$\{cap\.toLocaleString\(\)\}`/);
  assert.match(js, /return `\$\{entry\.badge\} \\u00b7 \$\{progress\} \$\{t\('to'\)\} \$\{next\}`/);
  assert.match(i18n, /'to': 'para'/);
});

test('#329 Challenger and the cap keep their own wording', () => {
  // Challenger has no cap, and being AT a cap is what makes promotion
  // available -- neither can be folded into a progress line.
  assert.match(js, /if \(cap === undefined\) return `\$\{entry\.badge\} \\u00b7 \$\{t\('no cap'\)\}`/);
  assert.match(js, /if \(entry\.points >= cap\) return `\$\{entry\.badge\} \\u00b7 \$\{t\('at the cap'\)\}/);
  assert.match(js, /a negative total stays in Iron/);
});

test('the five badge names are written out once, not twice', () => {
  // BADGE_ORDER and nextBadgeName existed twice, 1,600 lines apart: a
  // derived list beside BADGES and a hand-written copy by the quiz screen.
  assert.equal((js.match(/const BADGE_ORDER\b/g) ?? []).length, 1);
  assert.equal((js.match(/function nextBadgeName\b/g) ?? []).length, 1);
  assert.match(js, /const BADGE_ORDER = \[\.\.\.BADGES\]\.map\(\(\[name\]\) => name\)\.reverse\(\);/);
  assert.doesNotMatch(js, /\['Iron', 'Bronze', 'Silver', 'Gold', 'Challenger'\]/,
    'the hand-written copy of the ladder is back');
});

test('#336 an empty Ranked tile says so in words', () => {
  assert.match(js, /stats\.best_ranked \? `\$\{stats\.best_ranked\.correct\}\/\$\{stats\.best_ranked\.total\}`\s*\n?\s*: t\('Not yet'\)/);
  assert.match(js, /stats\.place != null \? `#\$\{stats\.place\}` : t\('Not yet'\)/);
  assert.match(i18n, /'Not yet': 'Todavía no'/);
});

test('#336 a FAILED read still shows the dash', () => {
  // "We could not fetch your place" and "you have no place yet" are
  // different facts. Only the second one is "Not yet".
  assert.match(js, /const bestRanked = !stats \? DASH/);
  assert.match(js, /const place = !stats \? DASH/);
});

test('#336 a worded tile gets its own size and the four stay level', () => {
  // "Todavia no" at the 26px / weight-900 number size overflows a
  // quarter-width tile. Measured after the change: all four tiles 89px tall
  // at 375, 820 and 1440, and nothing clipped in either language.
  assert.match(css, /\.pf-stat b\.words \{[^}]*font-size: 15px/);
  assert.match(js, /value === t\('Not yet'\) \? ' class="words"' : ''/);
  // Every tile goes through the one cell helper, so they cannot drift.
  assert.doesNotMatch(js, /<div class="pf-stat"><b>/, 'a tile is being built by hand again');
  assert.equal((js.match(/\$\{statCell\(/g) ?? []).length, 4);
});

test('#337 the climb row has three states, not two', () => {
  assert.match(js, /const state = i === at \? 'now' : i < at \? 'done' : 'off';/);
  // "done" is a badge already earned: full colour, so it deliberately has no
  // rule. Only "off" is dimmed.
  assert.doesNotMatch(css, /\.pf-badges img\.done/);
  assert.match(css, /\.pf-badges img\.off \{ opacity: 0\.32; filter: grayscale\(1\); \}/);
});

test('#337 the current badge carries a mark of its own', () => {
  // Dimming the others was the only mark, and it is invisible when the
  // current artwork is grey metal (Iron, Silver). Measured on a new
  // account before the change: the Iron badge really was opacity 1 with no
  // filter, and still looked like the four dimmed ones.
  assert.match(css, /\.pf-badges img\.now \{ outline: 2px solid var\(--gold-ring\); outline-offset: 2px;/);
  // An outline is not announced, so the same fact is in the alt text.
  assert.match(js, /const mark = i === at \? ` \(\$\{t\('Your badge'\)\}\)` : '';/);
  assert.match(i18n, /'Your badge': 'Tu insignia'/);
});

test('#337 the day ring is the deeper gold, not the day gold', () => {
  // Same measurement as the focus ring in #327: the day gold is 2.52:1 on
  // the cream page, under the 3:1 a ring that carries meaning needs. The
  // deeper brown-gold is 5.05:1. Night keeps the plain gold at 10.04:1.
  assert.match(css, /--gold-ring: var\(--gold\);/);
  assert.match(css, /--focus: var\(--gold-ring\);/);
  const day = css.match(/html\[data-theme="day"\] \{([^}]*)\}/)[1];
  assert.match(day, /--gold-ring: #8a5a12;/);
  assert.doesNotMatch(day, /--gold-ring: var\(--gold\)/,
    'the day ring is back on the gold that measured 2.52:1');
});
