// Round 5: #427. The Practice quiz hides the app frame on purpose (#382) --
// a dock under a timed run is a way to lose it. The Ranked quiz, which is
// timed AND counts for points, kept the whole dock: measured at 375x812 on
// question 1 of 15, four live tabs at y=750..812.
//
// So the run that costs nothing was protected and the run that costs points
// was not, and the same screen's own "Cancel this attempt" opens a
// confirmation naming its ten points -- while a tab 40px below did the same
// thing with no question asked.
//
// Measured after, at 375x812: no dock on the question, the feedback or the
// quit confirmation; the dock back on the result screen; .lab-main's bottom
// padding 20px instead of 76px during a run, which gives the card that
// space back. At 1440 the dock is the left rail, so its 232px column closes
// too: grid-template-columns goes from "232px 1208px" to one full column,
// and main starts at x=0. The Practice quiz is untouched (quiz-page, no
// dock, as before).

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

test('#427 the dock is never built, not hidden', () => {
  // Never built, so it is not in the tab order or the screen reader either
  // -- and no CSS has to beat `.lab-nav { display: grid !important }`,
  // which is what hiding it would have meant.
  assert.match(app, /const attemptLive = content\.includes\('data-attempt-live'\);/);
  assert.match(app, /\$\{attemptLive \? '' : `<nav class="lab-nav"/);
  assert.doesNotMatch(css, /#app\.attempt-live \.lab-nav \{ display: none/);
});

test('#427 one marker decides the dock and the heartbeat', () => {
  // The same fact about the screen, read once in render().
  const render = app.slice(app.indexOf('function render(node)'), app.indexOf('function languageButtons'));
  assert.match(render, /const attemptLive = Boolean\(node\.querySelector\?\.\('\[data-attempt-live\]'\)\);/);
  assert.match(render, /\+ \(attemptLive \? ' attempt-live' : ''\)/);
  assert.match(render, /if \(!attemptLive\) endLiveAttempt\(\);/);
});

test('#427 the clearance the dock needed goes with it', () => {
  assert.match(css, /#app\.attempt-live \.lab-main \{ padding-bottom: calc\(20px \+ env\(safe-area-inset-bottom\)\); \}/);
});

test('#427 at desktop the rail closes its column', () => {
  // The dock is a 232px left rail there. Removing the element alone would
  // have left 232px of empty page beside a live attempt.
  assert.match(css, /#app\.attempt-live \.lab-shell \{ grid-template-columns: minmax\(0, 1fr\); grid-template-areas: "top" "main"; \}/);
});

test('#427 the way out of a run is still the one that asks', () => {
  // Unchanged on purpose: it names the ten points before anything is sent.
  assert.match(app, /t\('Quit this ranked quiz\?'\)/);
  assert.match(app, /t\('Your current score will count, and 10 points are taken off it\. You cannot resume this attempt\.'\)/);
});
