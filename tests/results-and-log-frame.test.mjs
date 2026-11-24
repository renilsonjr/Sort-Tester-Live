// Round 3: #382, the practice results and the Shift log threw away the app
// shell -- no header, no dock, and a bare EN/ES pair floating above the
// content. Both are untimed, so there was nothing for them to protect.
//
// Measured in the running app at 320, 375, 820 and 1440, night and day,
// EN and ES: header 67px tall, dock present, no horizontal overflow, and the
// column 560px wide at 1440 instead of the full 1080.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');

const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const js = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

function body(name) {
  const start = js.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} is gone`);
  const next = js.indexOf('\nfunction ', start + 1);
  return js.slice(start, next === -1 ? js.length : next);
}

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#382 both screens are built through the shell', () => {
  // labPage is what draws the header and the dock, so going through it is
  // the whole fix -- not a copy of the header on two more screens.
  for (const name of ['renderResults', 'showLog']) {
    assert.match(body(name), /const view = labPage\(`/, `${name} still builds a bare view`);
    assert.doesNotMatch(body(name), /\n  render\(view\);/, `${name} still calls render directly`);
  }
});

test('#382 both carry the Practice tab mark', () => {
  // Reached from Practice, so the dock marks Practice -- the tab a player
  // presses to get back to its first screen.
  assert.match(body('renderResults'), /`, 'practice', \(\) => renderResults\(summary, saved\)\)/);
  assert.match(body('showLog'), /`, 'practice', showLog\)/);
});

test('#382 the loose EN/ES block is gone from both', () => {
  // The header owns the language pair now. Its old wrapper had exactly two
  // uses, so the CSS for it goes too rather than sitting dead.
  assert.doesNotMatch(js, /quiz-language/);
  assert.doesNotMatch(css, /\.quiz-language/);
});

test('#382 the quiz itself still drops the frame', () => {
  // On purpose: a timed run with a dock is a way to lose it. This is the
  // line between the two screens that keep the shell and the one that does
  // not, so it is pinned here rather than left to be re-decided.
  const quiz = body('showCard');
  assert.match(quiz, /<section class="screen quiz-card">/);
  assert.doesNotMatch(quiz, /labPage\(/);
});

test('#382 desktop keeps a reading measure, not the full column', () => {
  // Inside the shell they became full-column (1080px measured at 1440).
  // `.lab-main >` is load-bearing: the --desk-col rule is two classes.
  assert.match(css, /\.lab-main > \.screen-results, \.lab-main > \.screen-log \{ max-width: 560px; \}/);
  assert.match(body('renderResults'), /<section class="lab-screen screen-results">/);
  assert.match(body('showLog'), /<section class="lab-screen screen-log">/);
});
