// #443: the hat winner was marked three times at once, and the costliest
// of the three took away the thing the disc exists for.
//
// Measured at 375x812 with a hat holder on the board:
//
//   .pcrown  16x16 floating above the disc
//   .pdisc   the SAME crown inside it, 36x36 after #440 -- where the two
//            players who did not win show a 20.3px initial or a 36px avatar
//   the gold ring and glow the leader's disc already has
//
// Two identical crowns, 20px apart, in the same gold. They read as a
// rendering fault rather than as emphasis. And on the one screen where you
// look to see WHO won, the winner was the only person without a face.
//
// Below the podium the same swap replaced the player's place -- the one
// number that column is for -- on a row that already says "Hat winner" in
// words and is drawn in gold.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

function body(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} is gone`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
}

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#443 every podium disc shows the same kind of thing', () => {
  // The branch on row.hat is gone from the disc entirely: avatar, else
  // initial, for the winner exactly as for everyone else.
  const board = body('fillLeaderboard');
  assert.match(board, /<div class="pdisc\$\{avatarEmoji\(row\.avatar\) \? ' has-avatar' : ''\}">\$\{avatarEmoji\(row\.avatar\) \|\| esc\(row\.username\.slice\(0, 1\)\.toUpperCase\(\)\)\}<\/div>/);
  assert.doesNotMatch(board, /pdisc[^>]*\$\{!?row\.hat/);
});

test('#443 the has-avatar class no longer depends on winning', () => {
  // It used to read `!row.hat && avatarEmoji(...)`, because a winner's disc
  // held a crown rather than an avatar and must not be sized like one.
  const board = body('fillLeaderboard');
  assert.doesNotMatch(board, /!row\.hat && avatarEmoji/);
});

test('#443 the crown is left in exactly one place', () => {
  assert.equal((app.match(/ICONS\.prizeHolder/g) ?? []).length, 1);
  assert.match(app, /\$\{row\.hat \? `<div class="pcrown" aria-hidden="true">\$\{ICONS\.prizeHolder\}<\/div>` : ''\}/);
});

test('#443 the list row shows the place again, and still says it in words', () => {
  const board = body('fillLeaderboard');
  assert.match(board, /<span class="board-place">\$\{row\.place\}<\/span>/);
  // The two marks that were never the problem stay: the words and the gold.
  assert.match(board, /board-marker board-marker-hat">\$\{esc\(t\('Hat winner'\)\)\}/);
  assert.match(board, /\$\{row\.hat \? ' board-hat' :/);
  assert.match(css, /\.board li\.board-hat \{/);
});

test('#443 the leader keeps the ring that says first, which is a different fact', () => {
  // The ring says "first place", the crown says "took a hat". A player can
  // hold a hat without being first once a tie-break or a backfill lands,
  // which is why both exist and only the duplicate crown went.
  assert.match(css, /\.pslot\.p1 \.pdisc \{[^}]*border-color: var\(--gold\);/);
});

test('#443 the CSS that sized a mark inside the disc is gone with it', () => {
  assert.doesNotMatch(css, /\.pdisc svg/);
  assert.doesNotMatch(css, /\.board-place svg/);
  // and the rule the crown still needs is still there
  assert.match(css, /\.rq-mark svg, \.pcrown svg \{/);
});
