import test from 'node:test';
import assert from 'node:assert/strict';

import { readFileSync } from 'node:fs';

// The repo has no "type": "module", so a .js file is CommonJS to Node even
// though the browser loads it as a module. Every other test here loads src
// the same way.
const source = readFileSync(new URL('../src/idle.js', import.meta.url), 'utf8');
const { idleVerdict, IDLE_LIMIT_MS, IDLE_WARNING_MS } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
);

const MINUTE = 60 * 1000;

test('the window the owner chose is fifteen minutes, warned a minute ahead', () => {
  assert.equal(IDLE_LIMIT_MS, 15 * MINUTE);
  assert.equal(IDLE_WARNING_MS, MINUTE);
});

test('a phone in use is active', () => {
  const now = 1_000_000;
  assert.equal(idleVerdict(now, now), 'active');
  assert.equal(idleVerdict(now, now - 5 * MINUTE), 'active');
  assert.equal(idleVerdict(now, now - 13 * MINUTE), 'active');
});

test('the warning comes with a minute left, not before', () => {
  const now = 1_000_000;
  assert.equal(idleVerdict(now, now - (14 * MINUTE - 1)), 'active');
  assert.equal(idleVerdict(now, now - 14 * MINUTE), 'warn');
  assert.equal(idleVerdict(now, now - (15 * MINUTE - 1)), 'warn');
});

test('at the limit the session is out', () => {
  const now = 1_000_000;
  assert.equal(idleVerdict(now, now - 15 * MINUTE), 'out');
});

// A backgrounded tab throttles its timers, so the check cannot count ticks.
test('a tab that was away far past the limit is out, not merely warned', () => {
  const now = 1_000_000;
  assert.equal(idleVerdict(now, now - 4 * 60 * MINUTE), 'out');
});

test('a clock that jumps backwards does not sign anybody out', () => {
  const now = 1_000_000;
  assert.equal(idleVerdict(now, now + 30 * MINUTE), 'active');
});

test('the window can be set shorter for a test without touching the rule', () => {
  assert.equal(idleVerdict(1000, 0, 500, 100), 'out');
  assert.equal(idleVerdict(450, 0, 500, 100), 'warn');
  assert.equal(idleVerdict(300, 0, 500, 100), 'active');
});
