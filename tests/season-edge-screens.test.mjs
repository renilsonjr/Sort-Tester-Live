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

// Found walking a prize tie-break (#13, 2026-11-21).
test('the podium shows each player\'s real place, so a tie reads as a tie', () => {
  const board = fn('async function fillLeaderboard');
  assert.match(board, /<div class="ppillar">\$\{row\.place\}<\/div>/);
  // no pedestal number that ignores the standings
  assert.doesNotMatch(board, /slot\(top\[\d\], \d,/);
});

test('on the final board a tied player without a hat is told so', () => {
  const board = fn('async function fillLeaderboard');
  assert.match(board, /board\.prizes_final \? 'Tied on points, no hat' : 'Tied on points'/);
});

test('Home stops announcing a season start once that season has ended', () => {
  const callout = fn('async function fillLaunchCallout');
  assert.match(callout, /new Date\(notice\.closes_at\)\.getTime\(\) <= Date\.now\(\)/);
  assert.match(callout, /The official season has ended/);
  // the helper fills the dates; replacing them by hand left them blank
  assert.match(callout, /t\('It ran from \{start\} to \{end\}\.', \{ start: started, end: closes \}\)/);
  assert.match(app, /<h2 id="launch-title">/);
});

test('the selection button stops asking once the right number is chosen', () => {
  const fill = fn('async function fillSelection');
  assert.match(fill, /go\.textContent = go\.disabled \? go\.dataset\.ask : t\('Continue'\)/);
});

test('the tie and season-end sentences exist in Spanish', () => {
  for (const key of [
    'Tied on points',
    'Tied on points, no hat',
    'The official season has ended',
    'It ran from {start} to {end}.',
    'The leaderboard has the results.',
  ]) {
    assert.ok(i18n.includes(`'${key}':`), `no Spanish for: ${key}`);
  }
});

// Third walk (2026-11-22): what a tied player is told, and who stands on
// the final podium.
test('a tie-break player is told their own score once the round has closed', () => {
  assert.match(app, /function lastRoundLine\(last, stillTied\)/);
  assert.match(app, /tie\.last_result \? `<p class="lab-intro" id="tb-last">/);
  assert.match(app, /const last = tie\.last_result \? ` \$\{lastRoundLine\(tie\.last_result, false\)\}` : '';/);
  assert.match(app, /'The tie is still not settled\.'/);
});

test('an excluded Challenger is told why, and a hat is not credited to a quiz the owner decided', () => {
  assert.match(app, /tie\.placement === 'excluded'\) \{\s*return \{ title: t\('The tie-break is settled'\), text: t\('You did not complete the round, so you take no hat this season\./);
  assert.doesNotMatch(app, /The tie-break decided it in your favour/);
});

test('the final podium holds the hat winners, not the first three rows', () => {
  assert.match(app, /const ordered = board\.prizes_final\s*\? \[\.\.\.board\.rows\.filter\(\(row\) => row\.hat\), \.\.\.board\.rows\.filter\(\(row\) => !row\.hat\)\]\s*: board\.rows;/);
  assert.match(app, /const top = ordered\.slice\(0, 3\);/);
  assert.match(app, /const listRows = hasPodium \? ordered\.slice\(3\) : ordered;/);
});

test('Home tells a signed-in player about a tie-break round still to play', () => {
  assert.match(app, /<div id="home-tiebreak" hidden><\/div>/);
  assert.match(app, /if \(signedIn\(\)\) fillTiebreakCallout\(view\.querySelector\('#home-tiebreak'\), \{ onlyToPlay: true \}\);/);
  assert.match(app, /if \(onlyToPlay\) return;/);
});

test('a frozen season says points are final, not results, and one second is singular', () => {
  assert.match(app, /frozen: 'Points are final for this season\.'/);
  assert.match(app, /t\(secondsLeft === 1 \? 'second' : 'seconds'\)/);
});

test('pressing the active tab returns to its first screen', () => {
  assert.doesNotMatch(app, /if \(button\.dataset\.nav === active\) return;/);
});
