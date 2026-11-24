// Round 5: #428. The clock reaching zero changed nothing but the ring's
// colour. The four belts stayed enabled and the card sat there until the
// player pressed one -- which is how they learned the question had already
// timed out and taken its points. Sampled once a second in the running app:
//
//   9s: ring=0  belts enabled=4  screen=card
//   12s: ring=0 belts enabled=4  screen=card   (and on, indefinitely)
//
// The press was never going anywhere: the server discards a choice sent
// past the deadline. So zero now does what the press did, without it.
// Sampled again at 150ms after the change:
//
//   ring=1  on=4  "Where does this go?"
//   ring=0  on=0  "Time ran out"  (.over)
//           -> the feedback screen, by itself
//
// An ordinary answer is unchanged: measured at ring=8, one press, and the
// feedback said "Correct +20 points".

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

const play = (() => {
  const start = app.indexOf('async function playRankedAttempt(');
  assert.notEqual(start, -1, 'playRankedAttempt is gone');
  return app.slice(start, app.indexOf('\nfunction showRankedFeedback('));
})();

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#428 zero stops the clock and runs out', () => {
  assert.match(play, /if \(left <= 0\) \{ stopTimer\(\); runOut\(\); \}/);
});

test('#428 the belts go first, then the cue says what happened', () => {
  const fn = play.slice(play.indexOf('function runOut()'), play.indexOf('async function submit('));
  assert.match(fn, /view\.querySelectorAll\('\.belt'\)\.forEach\(\(b\) => \{ b\.disabled = true; \}\);/);
  assert.match(fn, /cue\.textContent = t\('Time ran out'\); cue\.classList\.add\('over'\);/);
  // Order matters: the controls stop before the words change, so nothing is
  // pressable while the screen still says "Where does this go?".
  assert.ok(fn.indexOf('b.disabled = true') < fn.indexOf("t('Time ran out')"));
});

test('#428 it sends no choice, because none was made', () => {
  const fn = play.slice(play.indexOf('function runOut()'), play.indexOf('async function submit('));
  assert.match(fn, /submit\(null, null\);/);
});

test('#428 one submit serves the press and the clock', () => {
  // Not a second copy of the answer path: the same function, so the feedback,
  // the sound and the tally cannot drift between the two ways a question ends.
  assert.match(play, /async function submit\(choice, button\) \{/);
  assert.match(play, /const result = await attempt\.answer\(q\.seq, choice\);/);
  assert.match(play, /showRankedFeedback\(attempt, mode, q, choice, result\.data, nextTally\);/);
});

test('#428 the question can only end once', () => {
  // The clock can reach zero while a press is in flight.
  assert.match(play, /let over = false;/);
  const click = play.slice(play.indexOf("querySelectorAll('.belt').forEach((button) => button.addEventListener('click'"));
  assert.match(click, /if \(over\) return;\s*\n\s*over = true;/);
});

test('#428 the cue stops looking like a prompt', () => {
  assert.match(css, /\.rq-cue\.over \{ color: var\(--bad\); \}/);
  assert.match(css, /\.belts \.belt:disabled \{ opacity: \.5; \}/);
});

test('#428 "Time ran out" already had Spanish', () => {
  // The feedback screen's verdict has used it since before this.
  assert.match(i18n, /'Time ran out': '/);
});
