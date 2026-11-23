import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('index.html contains belt-correct and belt-incorrect animation styles', () => {
  assert.match(html, /\.belt\.belt-correct|\.belt-correct/);
  assert.match(html, /\.belt\.belt-incorrect|\.belt-incorrect/);
  assert.match(html, /@keyframes\s+correctGlow/);
  // Was `incorrectShake`. It no longer shakes: a half-second sideways slide
  // fired on every wrong answer during a timed quiz, so it is now a 0.2s
  // settle onto the red ring, and the keyframe is named for what it does
  // (#347). The ring, the sound and the feedback screen still carry the
  // result, so nothing was the only signal before or after.
  assert.match(html, /@keyframes\s+incorrectSettle/);
  // Mentions in comments are fine and wanted; what must be gone is any
  // keyframe by the old name, or anything still playing one.
  assert.doesNotMatch(html, /@keyframes\s+incorrectShake/);
  assert.doesNotMatch(html, /animation:\s*incorrectShake/);
});

test('each feedback keyframe is declared exactly once', () => {
  // They used to be declared twice, identically, 400 lines apart. The second
  // copy won, so nothing looked wrong; the risk was editing one and leaving
  // the other behind (#350).
  assert.equal(html.match(/@keyframes\s+correctGlow/g).length, 1);
  assert.equal(html.match(/@keyframes\s+incorrectSettle/g).length, 1);
  assert.equal(html.match(/\.belt\.belt-correct\s*\{/g).length, 1);
});

test('the feedback animations stay quiet, because they fire on every answer', () => {
  const correct = html.match(/\.belt\.belt-correct\s*\{([^}]*)\}/)[1];
  const wrong = html.match(/\.belt\.belt-incorrect\s*\{([^}]*)\}/)[1];
  // A curve ending above 1 overshoots and springs back. Up to 30 times in a
  // Hard quiz, that is a bounce the player waits out (#346).
  assert.doesNotMatch(correct, /cubic-bezier\([^)]*1\.\d/,
    'the correct answer is overshooting again');
  assert.match(correct, /ease-out/);
  assert.match(wrong, /ease-out/);
  // No sideways or scaling movement left in either keyframe.
  const frames = html.match(/@keyframes\s+(?:correctGlow|incorrectSettle)\s*\{[\s\S]*?\n  \}/g).join('');
  assert.doesNotMatch(frames, /translateX/);
  assert.doesNotMatch(frames, /scale\(/);
});

test('index.html provides prefers-reduced-motion fallback for feedback animations', () => {
  assert.match(html, /@media\s*\(\s*prefers-reduced-motion\s*:\s*reduce\s*\)/);
  assert.match(html, /animation:\s*none\s*!important/);
});
