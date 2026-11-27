// Round 3: #385 (the Leaderboard still had the old full-width Back) and
// #386 (a routine message was set like an alarm).
//
// Measured in the running app at 320, 375 and 1440, night and day, EN and ES.

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

test('the stylesheet has no unbalanced comment', () => {
  // Twice in this review I ended comment prose with a second `*/` after the
  // comment had already closed; the parser then swallows the next rule and
  // nothing complains.
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#385 the Leaderboard uses the app\'s one Back, at the top', () => {
  // 335x52 before -- the heaviest control on the screen, and the second
  // kind of Back in an app that was given one in #331. Measured after:
  // 77x44 in English, 88x44 in Spanish, at 320, 375 and 1440.
  const screen = js.slice(js.indexOf('function showLeaderboard'));
  const body = screen.slice(0, screen.indexOf('\n}\n'));
  assert.match(body, /\$\{backLink\('board-back'\)\}/);
  assert.doesNotMatch(body, /<button id="board-back" class="ghost">/);
  // Before the eyebrow, like the picker and the Profile sub-screens: the
  // controls under a list are out of sight on a phone (#262).
  assert.ok(body.indexOf("backLink('board-back')") < body.indexOf("t('Ranked')"),
    'the Back is no longer the first thing in the screen');
});

test('#385 the Back on a Ranked RESULT screen is left alone', () => {
  // Those are not sub-screens: "Back to Ranked" is the only way forward
  // after a quiz, so it is that screen's primary action and a full-width
  // button is right. #385 is about a way OUT of a screen you opened to
  // look at something.
  assert.match(js, /<button id="rq-done" class="ghost">\$\{esc\(t\('Back'\)\)\}<\/button>/);
});

test('#386 a notice heading is a title, not an enlarged eyebrow', () => {
  // The app's base h2 is eyebrow styling -- uppercase, 0.12em tracking --
  // which reads as a label at 12px. The notice blew it to 16px and weight
  // 900 while keeping the caps, so "You are not in the standings" shouted
  // over two lines beside a 24px page title. Measured after: 15px, weight
  // 800, sentence case, one line of 22px.
  const rule = css.match(/\.board-notice h2 \{([^}]*)\}/g);
  assert.ok(rule, 'the notice heading rule is gone');
  const live = rule[rule.length - 1];
  assert.match(live, /text-transform: none/);
  assert.match(live, /font-size: 15px/);
  assert.match(live, /font-weight: 800/);
  assert.doesNotMatch(live, /text-transform: uppercase/);
});

test('#386 bad news still reads as bad news', () => {
  // The red-tinted surface is the channel that should carry that, not
  // capital letters on every notice in the app. Verified in the running
  // app by rendering a .board-notice-bad beside the plain one.
  assert.match(css, /\.board-notice-bad \{[^}]*border-color: rgba\(240, 138, 138/);
  assert.match(css, /\.board-notice-bad \{[^}]*background: rgba\(240, 138, 138/);
});
