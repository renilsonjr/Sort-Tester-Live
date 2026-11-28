// The leaderboard, refined (2026-11-27): the player's place first, a podium
// that can be read, and the standings as one card of rows.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

const start = app.indexOf('async function fillLeaderboard');
const board = app.slice(start, app.indexOf('\nfunction showRankedPlaceholder', start));

test('the place leads the screen in a card, not a 10px chip', () => {
  assert.match(board, /const placeCard = board\.your_place \? `/);
  assert.match(board, /<p class="board-mine-place">#\$\{esc\(board\.your_place\)\}<\/p>/);
  assert.ok(board.indexOf('${placeCard}') < board.indexOf('class="board-split'));
  assert.doesNotMatch(board, /tab-chip|placeChip/);
  assert.doesNotMatch(html, /\.tab-chip/);
});

test('points and the gap show only when the player\'s own row was sent', () => {
  assert.match(board, /const mine = board\.rows\.find\(\(row\) => row\.you\);/);
  assert.match(board, /\$\{mine \? `<div class="board-mine-pts">/);
  // The line for a player ranked past the rows shown is still there.
  assert.match(board, /class="board-your-place"/);
});

test('the gap is measured to a player with strictly more points', () => {
  // Two players tied on points are not ranked against each other.
  assert.match(board, /row\.points > mine\.points && \(!best \|\| row\.points < best\.points\)/);
  assert.match(board, /t\('\{n\} behind #\{place\}', \{ n: language\.number\(nextUp\.points - mine\.points\), place: nextUp\.place \}\)/);
  assert.match(i18n, /'\{n\} behind #\{place\}': 'A \{n\} del #\{place\}'/);
});

test('the note about how standings are kept follows them', () => {
  assert.ok(board.lastIndexOf('class="lab-intro tab-intro"') > board.indexOf('class="board-split'));
  assert.match(html, /\n  #board-panel > \.tab-intro \{ margin: 0; \}/);
});

test('the tie and hat markers ride on the tag line, in a gold that can be read', () => {
  const row = board.slice(board.indexOf('const rows = listRows.map'), board.indexOf('const intro ='));
  assert.ok(row.indexOf('board-marker') < row.indexOf('</small>'), 'the marker left the tag line');
  // #7a5200 was about 2:1 on the night card; --gold-ring is bright on night
  // and 5.4:1 on the day cream.
  assert.match(html, /\n  #board-panel \.board-marker \{[^}]*color: var\(--gold-ring\);[^}]*white-space: nowrap; \}/);
});

test('the standings are one card, and its rows are concentric with it', () => {
  assert.match(html, /\n  #board-panel \.board \{ gap: 2px; padding: 6px; border-radius: var\(--r-md\);/);
  assert.match(html, /\n  #board-panel \.board li \{ padding: 9px 10px; border: 0; border-radius: 16px; background: none;/);
  assert.match(html, /\n  #board-panel \.board li\.board-you \{ background: var\(--soft\); \}/);
});

test('podium names and points are no smaller than the body text beside them', () => {
  assert.match(html, /\n  #board-panel \.pname \{ font-size: 13px; \}/);
  assert.match(html, /\n  #board-panel \.ppts \{ font-size: 13px;/);
});
