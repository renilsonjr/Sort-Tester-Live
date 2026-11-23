// Coming back to a Ranked match after leaving the tab (issue #269).
//
// The server ends a match whose page went quiet, 15 seconds after the last
// heartbeat, and refuses a new one until that window has passed. The page
// used to print the server's own English phrase, "Active attempt exists", on
// a dead-end screen, so a player who switched apps could neither carry on nor
// start again, and was never told why. It now says what is happening, waits
// out the window and offers to try again.
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

const spanish = (key) => new RegExp(`'${key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}': '`);

test('what the player reads is always a translated sentence, never the server’s phrase', () => {
  const start = fn('async function startRankedAttempt');
  const shown = start.slice(start.indexOf('const reason ='), start.indexOf('comingSoon('));
  // the server's `detail` may be compared against, never used as the text
  assert.doesNotMatch(shown, /detail(?!\s*===)/);
  for (const branch of shown.split('?').slice(1)) {
    assert.match(branch.trim(), /^t\(/, `a reason that is not translated: ${branch.trim().slice(0, 40)}`);
  }
});

test('a match still closing leads to its own screen, not a dead end', () => {
  const start = fn('async function startRankedAttempt');
  assert.match(start, /'Active attempt exists'/);
  assert.match(start, /showPreparingNextMatch\(mode\)/);
});

test('that screen says what is happening and offers to try again', () => {
  const screen = fn('function showPreparingNextMatch');
  assert.match(screen, /t\('Preparing your next match'\)/);
  assert.match(screen, /t\('Your last match is still closing\. This takes a few seconds\.'\)/);
  assert.match(screen, /id="rq-retry"/);
  assert.match(screen, /startRankedAttempt\(mode\)/);
});

test('it also tries again by itself once the closing window has passed', () => {
  const screen = fn('function showPreparingNextMatch');
  assert.match(screen, /setTimeout\(/);
  assert.match(screen, /GRACE_RETRY_MS/);
  // only while the player is still looking at it
  assert.match(screen, /view\.isConnected/);
  assert.match(app, /const GRACE_RETRY_MS = 16000;/);
});

test('the other refusals are translated too, never printed raw', () => {
  const start = fn('async function startRankedAttempt');
  for (const detail of ['No open season', 'Promotion required', 'Promotion not available']) {
    assert.match(start, new RegExp(`'${detail}'`), `${detail} is not handled`);
  }
  assert.match(start, /t\('You are at the cap, so the next Ranked quiz is a promotion\.'\)/);
  assert.match(start, /t\('Promotion needs you at the cap\. Play ordinary Ranked to get there\.'\)/);
});

test('a match the server closed on its own says so on the result screen', () => {
  const result = fn('function showRankedResult');
  assert.match(result, /final_outcome === 'disconnect'/);
  assert.match(result, /t\('The app lost contact with the server, so the match was closed\. Questions already answered counted; one left unanswered counted as a timeout\.'\)/);
});

test('every new sentence has Spanish', () => {
  for (const key of [
    'Preparing your next match',
    'Your last match is still closing. This takes a few seconds.',
    'Try again',
    'You are at the cap, so the next Ranked quiz is a promotion.',
    'Promotion needs you at the cap. Play ordinary Ranked to get there.',
    'The app lost contact with the server, so the match was closed. Questions already answered counted; one left unanswered counted as a timeout.',
  ]) {
    assert.match(i18n, spanish(key), `no Spanish for ${key}`);
  }
});
