// The pause between an answer's verdict on the belt and the feedback screen
// is one number, shared by Ranked and Practice.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');

test('the feedback pause is 250 ms', () => {
  assert.match(app, /const FEEDBACK_PAUSE_MS = 250;/);
});

test('Ranked and Practice both wait the shared pause, and nothing else', () => {
  const uses = app.match(/\}, FEEDBACK_PAUSE_MS\);/g) || [];
  assert.equal(uses.length, 2);
  const ranked = app.slice(app.indexOf('async function submit(choice, button)'));
  assert.match(ranked.slice(0, 900), /showRankedFeedback\([^)]*\);\s*\}, FEEDBACK_PAUSE_MS\);/);
  const practice = app.slice(app.indexOf("button.classList.add('belt-incorrect');\n        playIncorrectSfx();\n      }\n      setTimeout"));
  assert.match(practice.slice(0, 400), /showFeedback\([\s\S]*?\}, FEEDBACK_PAUSE_MS\);/);
});

test('no hand-written pause is left beside it', () => {
  assert.doesNotMatch(app, /\}, (450|550)\);/);
});
