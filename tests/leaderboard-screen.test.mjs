// The Leaderboard screen (#12, slice 2), built to the screen approved in
// #16. These hold the promises the mockup makes, on the source itself:
// app.js is a browser module with a page behind it, and the rest of this
// suite reads it the same way.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function screen() {
  const start = app.indexOf('async function fillLeaderboard');
  assert.notEqual(start, -1, 'fillLeaderboard is missing');
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('Ranked offers the leaderboard', () => {
  assert.match(app, /id="ranked-board"/);
  assert.match(app, /#ranked-board'\)\.addEventListener\('click', showLeaderboard\)/);
});

test('a Ranked screen that failed to load still offers the leaderboard', () => {
  // The season and the standings are separate requests: one can fail while
  // the other answers, so the error state is not a dead end.
  const fill = app.slice(app.indexOf('async function fillRanked'));
  const failure = fill.slice(0, fill.indexOf('\n  title.textContent = season.phase'));
  assert.match(failure, /Could not load the season/);
  assert.match(failure, /id="ranked-board"/);
  assert.match(failure, /addEventListener\('click', showLeaderboard\)/);
});

test('the screen shows a loading line while the standings are fetched', () => {
  const start = app.slice(app.indexOf('function showLeaderboard'));
  assert.match(start.slice(0, start.indexOf('\n}\n')), /Loading the standings/);
  // a screen reader is told, rather than left on a silent placeholder
  assert.match(start.slice(0, start.indexOf('\n}\n')), /role="status"/);
});

test('a server that cannot be reached says the points are safe', () => {
  const body = screen();
  assert.match(body, /Could not load the standings/);
  assert.match(body, /Your points are safe/);
});

test('an empty board explains itself rather than showing nothing', () => {
  const body = screen();
  assert.match(body, /No standings yet/);
  assert.match(body, /Nobody has completed a Ranked quiz/);
  assert.match(body, /official season has not started/);
});

test('a player with no position is told what it means, without alarm', () => {
  const body = screen();
  assert.match(body, /You are not in the standings/);
  assert.match(body, /count as usual/);
  assert.match(body, /Primary Sort on the Twilight shift/);
  // never phrased as a punishment or a mistake
  assert.doesNotMatch(body, /banned|blocked|disqualif|not allowed|penalt/i);
});

test('tied players are named as tied, never ordered', () => {
  const body = screen();
  assert.match(body, /board-tied/);
  assert.match(body, /Tied on points/);
  // nothing claims one tied player is ahead of the other
  assert.doesNotMatch(body, /ahead|beats|first to reach/i);
});

test('no timestamp reaches the board', () => {
  // The first-reached-score rule was superseded by tie-break quizzes;
  // printing a time here would revive it.
  // The pattern names the date formatters rather than every formatter,
  // because grouping a score is not printing a time. #442 added two more
  // ways to print one -- language.date and language.dateTime -- so the
  // guard names those too; language.number stays allowed.
  const body = screen();
  assert.doesNotMatch(body, /toLocaleTimeString|toLocaleDateString|language\.date|language\.dateTime|new Date|settled_at|reached_at|_at\b/);
});

test('a frozen season says points are final but places are not', () => {
  const body = screen();
  assert.match(body, /points_final/);
  assert.match(body, /Points are final for this season/);
  assert.match(body, /stay provisional/);
});

test('the board shows only what the approved screen shows', () => {
  const body = screen();
  for (const field of ['place', 'username', 'tag', 'points', 'badge']) {
    assert.match(body, new RegExp(`row\\.${field}`), field);
  }
  // nothing private has a place on a screen other players can read
  assert.doesNotMatch(body, /ticket|flag|connection|login_id|account_id/i);
});

test('a username is escaped before it reaches the page', () => {
  const body = screen();
  assert.match(body, /esc\(row\.username\)/);
  assert.match(body, /esc\(row\.tag\)/);
});

test('the row styling keeps a long username from pushing the points off', () => {
  assert.match(page, /\.board-who \{ min-width: 0; \}/);
  assert.match(page, /\.board-who b \{ display: block; overflow-wrap: anywhere; \}/);
});

test('your own row is marked on the board', () => {
  assert.match(screen(), /board-you/);
  assert.match(page, /\.board li\.board-you/);
});

// --- the server caps the rows it sends (audit: server-side list caps) ---

test('a player ranked past the rows sent is told their place in words', () => {
  // Every row carries `you`, so while the whole leaderboard was sent the
  // player's own line was always there to find. With a cap, someone below
  // the cut gets a list their name is not in -- and `your_place` is in the
  // payload precisely for that case, so the screen must use it.
  const body = app.slice(app.indexOf('async function fillLeaderboard'));
  assert.match(body, /board\.rows\.some\(\(row\) => row\.you\)/,
    'the screen must notice when the player is not in the rows shown');
  assert.match(body, /board\.your_place/,
    'the place the server already sends must be used');
});

test('the place line is not shown to a player who is in the list', () => {
  const body = app.slice(app.indexOf('async function fillLeaderboard'));
  // guarded by both conditions: not in the list AND a place to state
  assert.match(body, /!youInList && board\.your_place/);
});

test('the place line has a style of its own', () => {
  assert.match(page, /\.board-your-place\s*\{/);
});

// Pre-Season board (#247, owner decision 2026-11-20).
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

test('the Pre-Season board says it wins no prize and is reset at launch', () => {
  const body = screen();
  assert.match(body, /board\.phase === 'pre_season'/);
  assert.match(body, /These standings win no prize/);
  assert.match(body, /back to 0 points and Iron when the official season starts/);
  // said above an empty board too, not only above a full one
  const empty = body.slice(body.indexOf('board.rows.length === 0'));
  assert.match(empty.slice(0, empty.indexOf('return;')), /preSeasonLine \+ boardNotice/);
});

test('an empty Pre-Season board names Pre-Season, not the official season', () => {
  assert.match(screen(), /Nobody has completed a Ranked quiz in Pre-Season yet/);
});

test('a player missing from the Pre-Season board is not told about approval', () => {
  const body = screen();
  const notice = body.slice(body.indexOf('const notInStandings'));
  const preSeasonBranch = notice.slice(0, notice.indexOf(': boardNotice('));
  assert.match(preSeasonBranch, /Complete one Ranked quiz and you will appear here/);
  assert.doesNotMatch(preSeasonBranch, /Twilight|approved by the owner/);
});

test('every Pre-Season board sentence has a Spanish translation', () => {
  for (const sentence of [
    'These standings win no prize. Everyone goes back to 0 points and Iron when the official season starts.',
    'Nobody has completed a Ranked quiz in Pre-Season yet, so there is nothing to rank.',
    'You are not in the standings yet',
    'Complete one Ranked quiz and you will appear here. Pre-Season needs no approval.',
  ]) {
    assert.ok(app.includes(`'${sentence}'`), `app.js does not use: ${sentence}`);
    assert.ok(i18n.includes(`'${sentence}': '`), `no Spanish for: ${sentence}`);
  }
});
