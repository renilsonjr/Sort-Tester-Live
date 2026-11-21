// The screens at the edges of a season (#13, end-to-end walk of
// 2026-11-21): a quiz in progress when the official season launches, and
// the Ranked screen once the season stops admitting attempts.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('a question on screen leaves by itself when the attempt is gone', () => {
  const play = fn('async function playRankedAttempt');
  assert.match(play, /attempt\.onGone\(/);
  // only the question screen reacts: feedback for the last answer is also
  // shown after the attempt ended, and must stay until Next is pressed
  assert.match(play, /view\.isConnected/);
});

test('an attempt ended by the launch says so instead of showing a balance', () => {
  const result = fn('function showRankedResult');
  assert.match(result, /final_outcome === 'launch_reset'/);
  assert.ok(
    result.indexOf("'launch_reset'") < result.indexOf("mode === 'promotion'"),
    'a promotion attempt ended by the launch gets the same screen',
  );
  const ended = fn('function showEndedAtLaunch');
  assert.match(ended, /The official season has started/);
  assert.match(ended, /This attempt ended when the season started\. No score was applied\./);
  assert.match(ended, /Everyone began again at 0 points and Iron\./);
  assert.doesNotMatch(ended, /points_after|rankedSum/);
  assert.match(ended, /showRanked/);
});

test('Ranked offers a new quiz only while the season is open', () => {
  const filled = fn('async function fillRanked');
  assert.match(filled, /const open = season\.status === 'open'/);
  assert.match(filled, /\$\{open \? `\s*<button id="ranked-start"/);
  assert.match(filled, /t\(open \? 'Closes' : 'Closed'\)/);
});

test('a refused start explains a closed season and offers the way back', () => {
  const start = fn('async function startRankedAttempt');
  assert.match(start, /No open season/);
  assert.match(start, /The season is closed, so no new Ranked quiz can start\./);
  assert.match(start, /showRanked/);
});

test('the new sentences exist in Spanish', () => {
  for (const key of [
    'This attempt ended when the season started. No score was applied.',
    'The season is closed, so no new Ranked quiz can start.',
    'Closed',
  ]) {
    assert.ok(i18n.includes(`'${key}':`), `no Spanish for: ${key}`);
  }
});
