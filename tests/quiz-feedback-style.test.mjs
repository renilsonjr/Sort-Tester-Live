import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('index.html contains belt-correct and belt-incorrect feedback styles', () => {
  assert.match(html, /\.belt\.belt-correct/);
  assert.match(html, /\.belt\.belt-incorrect/);
  // One keyframe serves both verdicts now: it only fades the ring in, and the
  // colour comes from the rule that plays it. It replaced `correctGlow` and
  // `incorrectSettle`, which grew a `box-shadow` across their frames -- a
  // shadow is painted rather than composited, so every answer repainted the
  // belt on every frame.
  assert.match(html, /@keyframes\s+verdict-ring/);
  // Was `incorrectShake` before that: a half-second sideways slide on every
  // wrong answer during a timed quiz (#347).
  assert.doesNotMatch(html, /@keyframes\s+incorrectShake/);
  assert.doesNotMatch(html, /animation:\s*incorrectShake/);
  // The replaced pair must be gone, not left behind playing nothing.
  assert.doesNotMatch(html, /@keyframes\s+(?:correctGlow|incorrectSettle)/);
});

// The verdict rules that carry a colour each start their own line; the shared
// one that only shapes the ring names both selectors, so it is matched apart.
const verdictRule = (verdict) =>
  html.match(new RegExp(`^  \\.belt\\.belt-${verdict}::after \\{([^}]*)\\}`, 'm'))[1];

test('each feedback rule is declared exactly once', () => {
  // They used to be declared twice, identically, 400 lines apart. The second
  // copy won, so nothing looked wrong; the risk was editing one and leaving
  // the other behind (#350).
  assert.equal(html.match(/@keyframes\s+verdict-ring/g).length, 1);
  assert.equal(html.match(/^  \.belt\.belt-correct::after \{/gm).length, 1);
  assert.equal(html.match(/^  \.belt\.belt-incorrect::after \{/gm).length, 1);
});

test('the ring is composited, not repainted, because it fires on every answer', () => {
  const correct = verdictRule('correct');
  const wrong = verdictRule('incorrect');
  // The shadow is a fixed declaration on the element. If it ever moves back
  // inside the keyframe, the per-frame repaint comes back with it.
  for (const rule of [correct, wrong]) {
    assert.match(rule, /box-shadow:/, 'the ring lost its colour');
    assert.match(rule, /animation: verdict-ring/);
    assert.match(rule, /ease-out/);
    // A curve ending above 1 overshoots and springs back. Up to 30 times in a
    // Hard quiz, that is a bounce the player waits out (#346).
    assert.doesNotMatch(rule, /cubic-bezier\([^)]*1\.\d/, 'the verdict is overshooting again');
  }
  const frame = html.match(/@keyframes\s+verdict-ring\s*\{[^}]*\{[^}]*\}[^}]*\}/)[0];
  // Opacity alone: no movement, no size change, and no painted property.
  assert.doesNotMatch(frame, /translateX|scale\(|box-shadow/);
  assert.match(frame, /opacity: 1/);
});

test('reduced motion stills movement without switching the app off', () => {
  // This block used to be `* { animation: none !important; transition: none
  // !important }`, which took the colour and the press feedback with it. Less
  // motion means less movement, not an app that stops answering the finger.
  // Not the first such query in the file: the boot mark has one of its own,
  // above the stylesheet's tokens. This is the app-wide block, which follows
  // the celebration keyframes.
  const from = html.indexOf('@media (prefers-reduced-motion: reduce)', html.indexOf('@keyframes cheer-spark'));
  assert.ok(from > 0, 'the app-wide reduced-motion block is gone');
  const block = html.slice(from).match(/\{([\s\S]*?)\n  \}/)[1];
  assert.doesNotMatch(block, /\*\s*\{/, 'the blanket rule is back');
  assert.match(block, /\.boot-mark \{ animation: none; \}/);
  assert.match(block, /\.promo-cheer \.cheer-badge/, 'the celebration still plays');
  assert.match(block, /:active[\s\S]*transform: none/, 'controls still travel under a press');
  assert.match(block, /\.lab-choice:hover \{ transform: none; \}/);
});
