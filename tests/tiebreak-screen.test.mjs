// The player's tie-break screens (#24, slice 7). Mostly they hold what the
// screen must and must not say: no feedback, no other player's score, and
// the plain truth that nothing moves the player's season points.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('Ranked shows a callout only when there is a tie to play or read', () => {
  const callout = fn('async function fillTiebreakCallout');
  assert.match(callout, /\/ranked\/tiebreak\/mine/);
  assert.match(callout, /if \(!tie\) return/);
  assert.match(callout, /round\.played/);
});

test('the invite says the quiz changes no points', () => {
  const invite = fn('function showTiebreakInvite');
  assert.match(invite, /changes no points and no badge/i);
  assert.match(invite, /there is no Next/);
  assert.match(invite, /Play once/);
});

test('playing drives the server attempt and never settles it in the page', () => {
  const play = fn('async function playTiebreak');
  assert.match(play, /createAttemptClient/);
  assert.match(play, /attempt\.start\(`\/ranked\/tiebreak\/rounds\//);
  assert.match(play, /attempt\.startHeartbeat\(\)/);
  // the page never asks for a result or a score mid-attempt
  assert.doesNotMatch(play, /\/result|raw_score|points_after/);
});

test('an ended attempt moves to submitted, not to a score', () => {
  const play = fn('async function playTiebreak');
  assert.match(play, /status === 410 \|\| current\.status === 204/);
  assert.match(play, /showTiebreakSubmitted/);
});

test('the question says there is no feedback until the round closes', () => {
  const play = fn('async function playTiebreak');
  assert.match(play, /No feedback: whether you were right stays hidden/);
});

test('belts come from the server’s four options, not a fixed list', () => {
  const play = fn('async function playTiebreak');
  assert.match(play, /q\.options \|\| \[\]/);
});

test('submitted explains why nothing is shown yet', () => {
  const submitted = fn('function showTiebreakSubmitted');
  assert.match(submitted, /Scores stay hidden for everyone until the round closes/);
  // it explains why no score shows; it must not actually show one
  assert.doesNotMatch(submitted, /your score|you got \d|\d\/5|you were (right|wrong)/i);
});

test('the standing a player is shown is their own, never a rival’s', () => {
  const standing = fn('function tiebreakStanding');
  assert.match(standing, /You won a hat/);
  assert.match(standing, /did not take a hat/);
  assert.match(standing, /Waiting on the owner/);
  // nothing about who they were tied with or what anyone scored
  assert.doesNotMatch(standing, /opponent|other player|they scored/i);
});

test('the player screens are styled', () => {
  assert.match(page, /\.tb-bar i \{/);
  assert.match(page, /\.belts \{ display: grid/);
});
