// The Ranked result, refined (2026-11-27): what the match was worth beside
// the hits, the climb to the next badge, and a way straight into another
// quiz. Every line of the points breakdown stays; that is checked in
// ranked-play.test.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(head) {
  const from = app.slice(app.indexOf(head));
  return from.slice(0, from.indexOf('\n}\n'));
}
const result = fn('function showRankedResult');
const next = fn('async function fillRankedNextStep');

test('the gain is the real change in the balance, not the raw score', () => {
  // After the quit penalty and the cap, so the pill and the last line of
  // the breakdown can never disagree.
  assert.match(result, /const gain = result\.points_after - result\.points_before;/);
  assert.match(result, /class="rq-gain \$\{gainTone\}"/);
  assert.match(result, /gain > 0 \? 'good' : gain < 0 \? 'lost' : 'flat'/);
});

test('the climb is read from the balance the server confirmed', () => {
  assert.match(result, /const now = \{ badge: result\.badge_after, points: result\.points_after \};/);
  assert.match(result, /balanceLine\(now\)/);
  assert.match(result, /badgeArt\(now\.badge\)/);
  // No cap, no meter: Diamond has nothing above it to measure against.
  assert.match(result, /climb === null \? '' :/);
});

test('the breakdown and its notices are all still on the screen', () => {
  assert.match(result, /rankedSum\(result, quit\)/);
  assert.match(result, /id="rq-season-close"/);
  assert.match(result, /id="rq-disconnect"/);
  assert.match(result, /droppedBadge \? boardNotice\(/);
});

test('Play again appears only when the server would start a quiz', () => {
  assert.match(next, /season\.status === 'open' && entry\.mode !== 'promotion'/);
  // A failed read offers nothing rather than a button that will be refused.
  assert.match(next, /Boolean\(season && entry\)/);
  // A read that lands after the player left draws nothing.
  assert.match(next, /if \(!view\.isConnected\) return;/);
  assert.match(next, /startRankedAttempt\('normal'\)/);
  // One tap, one attempt.
  assert.match(next, /event\.currentTarget\.disabled = true;/);
});

test('Back is never relabelled under a thumb', () => {
  // The room for Play again is kept from the first paint, and Back keeps
  // its own place and its own words whatever the reads answer.
  assert.match(result, /<div class="rq-next" id="rq-next-step"><\/div>/);
  assert.match(html, /\n  \.rq-next \{ min-height: 52px; \}/);
  assert.doesNotMatch(next, /rq-done'\)\.textContent/);
  // With no quiz to offer, Back is the main button again.
  assert.match(next, /slot\.remove\(\);\s*view\.querySelector\('#rq-done'\)\.className = 'primary';/);
});

test('Leaderboard and Back share a row, and stack when it gets narrow', () => {
  assert.match(result, /<div class="rq-pair">\s*<button id="rq-board" class="ghost" type="button">/);
  assert.match(result, /'#rq-board'\)\.addEventListener\('click', showLeaderboard\)/);
  assert.match(html, /\n  \.rq-pair \{ display: grid; grid-template-columns: repeat\(auto-fit, minmax\(128px, 1fr\)\); gap: 8px; \}/);
});

test('the day pill does not use the thin status colours for its words', () => {
  assert.match(html, /html\[data-theme="day"\] \.rq-gain\.good \{[^}]*color: #1b6b46;/);
  assert.match(html, /html\[data-theme="day"\] \.rq-gain\.lost \{[^}]*color: #a2362f;/);
});

test('every word on the screen has its Spanish', () => {
  for (const key of ['Play again', 'Your climb', 'Leaderboard', 'Back', 'points']) {
    assert.match(i18n, new RegExp(`'${key}': '`), `${key} has no Spanish`);
  }
});
