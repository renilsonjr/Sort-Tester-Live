// The Handler, refined (2026-11-28). Measured on a 390x844 phone before the
// change: the round's control bar ended 19px behind the dock and the hint
// line was fully behind it, with the page 905px tall; the mode screen was
// 875px, most of it the five rules.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const view = readFileSync(new URL('../src/conveyor/view.js', import.meta.url), 'utf8');
const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function fn(source, head) {
  const from = source.slice(source.indexOf(head));
  return from.slice(0, from.indexOf('\n  }\n'));
}

test('the Handler says when a round is live, and only then', () => {
  assert.match(view, /\n  onRound = \(\) => \{\},/);
  assert.match(fn(view, '  function startCountdown('), /onRound\(true\);/);
  for (const head of ['  function showModes(', '  function showSummary(', '  function showBoard(', '  function unmount(']) {
    assert.match(fn(view, head), /onRound\(false\);/, `${head} must clear it`);
  }
});

test('the dock is taken out of the page for the round, not hidden', () => {
  // #427 does the same for a live attempt: not in the tab order, not read
  // out, and no CSS to beat.
  const hold = fn(app, 'function holdHandlerDock(');
  assert.match(hold, /handlerDock\?\.remove\(\);/);
  assert.match(hold, /shell\.append\(handlerDock\);/);
  assert.match(app, /onRound: \(live\) => holdHandlerDock\(view, live\)/);
  // a fresh mount starts with no kept dock
  assert.match(fn(app, 'function showHandler('), /handlerDock = null;/);
});

test('the round gives back the room the dock left', () => {
  assert.match(html, /\n  #app\.hd-live \.lab-main \{ padding-bottom: calc\(14px \+ env\(safe-area-inset-bottom\)\); \}/);
  // Small beside the title, still a full touch target.
  assert.match(html, /\n  #app\.hd-live \.hd-leave \{ padding: 0 16px; border-radius: 999px;/);
});

test('a mode is one row: the name, and the best score at its end', () => {
  assert.match(view, /<span class="hd-mode-best">\$\{esc\(t\('Your best'\)\)\} <strong>/);
  assert.match(html, /\n  \.hd-mode \{\n    width: 100%; min-height: 58px; display: flex; align-items: center; justify-content: space-between;/);
  assert.match(html, /\n  \.hd-mode-best \{ flex: none;[^}]*white-space: nowrap; \}/);
});

test('the five rules are still there, behind their own heading', () => {
  const modes = fn(view, '  function showModes(');
  assert.match(modes, /<details class="hd-rules">\s*\n\s*<summary>\$\{esc\(t\('How it scores'\)\)\}<\/summary>/);
  assert.equal((modes.match(/<li>\$\{esc\(t\(/g) ?? []).length, 5);
  assert.match(html, /\n  \.hd-rules summary \{ display: flex;[^}]*min-height: 58px;/);
  assert.match(html, /\n  \.hd-rules\[open\] summary::after \{ content: "\\2212"; \}/);
  assert.match(html, /\n  \.hd-rules summary:focus-visible \{ outline: 3px solid var\(--hd-gold\);/);
});

test('the leaderboard is a row like the modes above it', () => {
  assert.match(html, /\n  \.hd-board-open \{ display: flex; align-items: center; justify-content: space-between;[^}]*min-height: 58px;/);
  assert.match(html, /\n  \.hd-board-open::after \{ content: "\\2192";/);
});

test('the mode names are still names, with nothing added under them', () => {
  // The owner asked the per-mode descriptions to go on 2026-11-26.
  const copy = view.slice(view.indexOf('const MODE_COPY'), view.indexOf('let game = null;'));
  for (const key of ['easy', 'medium', 'hard', 'expert']) {
    assert.match(copy, new RegExp(`${key}: \\['[A-Z][a-z]+'\\],`), `${key} gained a second line`);
  }
});
