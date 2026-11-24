// Round 3: #390. MAIN CHART and EXCEPTIONS AND SPECIAL RULES were drawn in
// white at 13px while every other section label in the app is the gold
// .lab-eyebrow. Measured in the running app at 375x812 against main:
//
//   TWILIGHT STUDY GUIDE   rgb(244,189,56)  11px / 900  ls 1.76px
//   MAIN CHART             rgb(255,253,248) 13px / 800  ls 0.91px
//
// So the screen with the most sections was the one where sections did not
// look like sections, and the white caps competed with the row text instead
// of ranking above it. Measured after: both headings match the screen's own
// eyebrow exactly, in night (#f4bd38) and day (#c98a10).

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

test("#390 both chart headings wear the app's eyebrow", () => {
  for (const label of ['Main chart', 'Exceptions and special rules']) {
    assert.match(app, new RegExp(`<h2 class="lab-eyebrow lab-chart-block">\\$\\{esc\\(t\\('${label}'\\)\\)\\}</h2>`),
      `${label} is not an eyebrow`);
  }
});

test('#390 they are still headings, not decorated paragraphs', () => {
  // The eyebrow is how they look; h2 is what they are. A screen reader
  // walking this chart still gets two sections.
  assert.equal((app.match(/<h2 class="lab-eyebrow lab-chart-block">/g) ?? []).length, 2);
});

test('#390 the block class carries spacing only', () => {
  // Its old colour and size would have been dead weight: the .lab-eyebrow
  // rule later in the sheet wins on both. Leaving them would have read as
  // if the heading were still white.
  assert.match(css, /\.lab-chart-block \{ margin: 22px 0 3px; \}/);
  assert.doesNotMatch(css, /\.lab-chart-block \{[^}]*color:/);
  assert.doesNotMatch(css, /\.lab-chart-block \{[^}]*font-size:/);
});

test('#390 the eyebrow rule that wins is the gold one', () => {
  // What makes the headings gold in both themes. If this moves above
  // .lab-chart-block in the sheet, the margin would win instead and the
  // blocks would close up.
  const eyebrowGold = css.indexOf('.lab-eyebrow { color: var(--gold);');
  const chartBlock = css.indexOf('.lab-chart-block { margin:');
  assert.notEqual(eyebrowGold, -1, 'the gold eyebrow rule is gone');
  assert.ok(chartBlock < eyebrowGold, 'the chart block rule must come first for the colour to win');
});
