// Profile, regrouped (2026-11-27): one card says who the player is and where
// they stand, then three figures in a row. The points used to be a tile and
// again the line under the badges; the badge was drawn twice.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

const show = app.slice(app.indexOf('function showProfile('), app.indexOf('\n// The name and tag come from'));
const overview = app.slice(app.indexOf('async function fillOverview'), app.indexOf('\nasync function fillHistory'));

test('the name and the standing share one card, on the overview only', () => {
  assert.match(show, /<div class="home-spot pf-hero">\s*<div class="pf-ident">/);
  assert.match(show, /<div class="pf-standing" id="profile-standing"><\/div>/);
  // Settings and history still have a title of their own and no card.
  assert.ok(show.indexOf('pf-hero') > show.indexOf("tab !== 'overview' ? `"));
});

test('the balance, the climb line and the five badges are in that card', () => {
  const fill = overview.slice(overview.indexOf('standing.innerHTML'), overview.lastIndexOf('panel.innerHTML'));
  assert.match(fill, /t\('Your balance'\)/);
  assert.match(fill, /language\.number\(entry\.points\)/);
  assert.match(fill, /balanceLine\(entry\)/);
  assert.match(fill, /badgeTrail\(entry\.badge\)/);
  assert.match(fill, /progress === null \? '' :/);
});

test('the points are said once', () => {
  const panel = overview.slice(overview.lastIndexOf('panel.innerHTML'));
  assert.doesNotMatch(panel, /statCell\(language\.number\(entry\.points\)/);
  assert.doesNotMatch(panel, /balanceLine|badgeTrail|Your climb/);
  // and the badge name is not appended to the tag line any more
  assert.doesNotMatch(overview, /tagEl\.textContent = /);
});

test('a failed balance read leaves the card as a name, not an empty box', () => {
  assert.match(html, /\n  \.pf-standing:empty \{ display: none; \}/);
  assert.match(overview, /if \(standing\) \{/);
});

test('three figures in a row, the label over the figure', () => {
  assert.match(overview, /<div class="pf-stat"><small>\$\{esc\(label\)\}<\/small><b/);
  assert.match(html, /\n  \.pf-stats \{ grid-template-columns: repeat\(3, minmax\(0, 1fr\)\); gap: 8px; \}/);
  // Sentence case at 11px: the 10px capitals were the smallest text in the app.
  assert.match(html, /\n  \.pf-stat small \{ margin: 0; font-size: 11px; letter-spacing: 0; text-transform: none;/);
});

test('under 360px the three become rows, so no Spanish word breaks', () => {
  const narrow = html.slice(html.indexOf('@media (max-width: 359px) {\n    .pf-stats'));
  assert.match(narrow, /\.pf-stats \{ grid-template-columns: minmax\(0, 1fr\); \}/);
  assert.match(narrow, /\.pf-stat \{ flex-direction: row; align-items: center;/);
});

test('the card is the Ranked one, so the name has no card of its own', () => {
  assert.match(html, /\n  \.pf-hero \.pf-ident \{ padding: 0; border: 0; border-radius: 0; background: none; box-shadow: none; \}/);
  assert.doesNotMatch(html, /\.pf-climb/);
});

test('on a desktop the figures cross the whole panel', () => {
  const desk = html.slice(html.lastIndexOf('@media (min-width: 900px)'));
  assert.match(desk, /#profile-panel > \.home-stripe,\s*\.screen-profile > #profile-panel > \.profile-promo \{ grid-column: 1 \/ -1; \}/);
});
