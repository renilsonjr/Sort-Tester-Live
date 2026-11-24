// #404: the last icons in the app drawn from a text character.
//
// Measured on the owner menu at 375x812 before the change, with a range
// around each glyph's own text node: the six marks were 7.5, 9.6, 9.6, 9.6,
// 12.2 and 12.2 CSS pixels of ink inside identical 44px tiles -- a 63%
// spread down one column. The declared font is Nunito, which has none of
// these characters, so each device picks its own fallback and the column
// looks different on every phone. Every drawn icon in the app measures
// 19x19 with a 2px stroke.
//
// None of them carried aria-hidden either, so a screen reader read the
// decoration out: "tick, Prize eligibility".
//
// Nine call sites, eight marks: Prize selection and the player's prize
// tie-break are the two ends of the same thing and share one, and the two
// Create ticket rows (the live button and the locked row) share another.
//
// Also here, and wider than the issue asked: the Settings chip's gear.
// It is not a tile, but it is a U+2699 drawn at 8.4px of ink in the
// sub-header of every screen, which makes it the one the player sees most.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#404 no icon tile is drawn from a text character', () => {
  // The guard that matters: every .lab-choice-icon in the app takes its
  // contents from ICONS. A new row with a glyph in it fails here.
  const tiles = app.match(/<span class="lab-choice-icon"[^>]*>(.*?)<\/span>/g) ?? [];
  assert.ok(tiles.length >= 9, `expected the icon tiles to still be here, found ${tiles.length}`);
  for (const tile of tiles) {
    // deckRow's tile is the one that carries data rather than decoration:
    // the level number, "01".."10", or the quiz mark for a service deck.
    // Digits are in Nunito, so that one has no fallback to fall into.
    if (tile.includes('${icon}')) continue;
    assert.match(tile, /\$\{ICONS\.[A-Za-z]+\}/, `tile is not a drawn icon: ${tile}`);
  }
  assert.match(app, /const icon = index === null \? ICONS\.quiz : `0\$\{index \+ 1\}`;/);
});

test('#404 every icon tile is hidden from a screen reader', () => {
  // The tile repeats the label beside it, so announcing it is noise.
  const tiles = app.match(/<span class="lab-choice-icon"[^>]*>/g) ?? [];
  for (const tile of tiles) {
    assert.match(tile, /aria-hidden="true"/, `tile is announced: ${tile}`);
  }
});

test('#404 the eight new marks exist and are drawn on the shared grid', () => {
  // Same viewBox and no inline colour or stroke: the single CSS rule gives
  // all of them 19x19, stroke 2 and currentColor, which is what makes the
  // day theme and the gold recolour them for free.
  const marks = ['prizeEligibility', 'accessRecovery', 'recoveryMessages',
    'caseReview', 'accounts', 'createTicket', 'tiebreak', 'settings'];
  for (const name of marks) {
    const line = app.match(new RegExp(`^  ${name}: '(.*)',$`, 'm'));
    assert.ok(line, `${name} is gone from ICONS`);
    assert.match(line[1], /^<svg viewBox="0 0 24 24">/, `${name} is off the 24x24 grid`);
    assert.doesNotMatch(line[1], /\b(?:fill|stroke|style)=/, `${name} hardcodes its own paint`);
  }
});

test('#404 the tie-break mark serves both ends of the tie-break', () => {
  // "Prize selection -- ties the rules send to you" is the owner's side of
  // the tie-break the player is invited to on Ranked. One idea, one mark.
  assert.equal((app.match(/\$\{ICONS\.tiebreak\}/g) ?? []).length, 2);
  const owner = app.indexOf("id=\"owner-select\"");
  assert.notEqual(owner, -1, 'the Prize selection row is gone');
  assert.match(app.slice(owner, owner + 260), /\$\{ICONS\.tiebreak\}/);
});

test('#404 both Create ticket rows carry the same mark', () => {
  // The live button and the locked row from #421 are the same offer in two
  // states, so they must not drift apart.
  assert.equal((app.match(/\$\{ICONS\.createTicket\}/g) ?? []).length, 2);
});

test('#404 the Settings chip is drawn, and sized for 12px text', () => {
  assert.doesNotMatch(app, /\\u2699|⚙/);
  assert.match(app, /<span class="lab-btn-ic" aria-hidden="true">\$\{ICONS\.settings\}<\/span> \$\{esc\(t\('Settings'\)\)\}/);
  assert.match(css, /\.lab-settings-btn \.lab-btn-ic svg \{ width: 15px; height: 15px; \}/);
});

test('#404 the Settings mark is not a second day-theme sun', () => {
  // A gear at 15px is a ring with short rays, and the day icon -- a ring
  // with eight rays -- sits two chips away in the same header. Sliders
  // instead, which share nothing with it.
  const gear = app.match(/^  settings: '(.*)',$/m)[1];
  const day = app.match(/^  day: '(.*)',$/m)[1];
  assert.doesNotMatch(gear, /<circle cx="12" cy="12"/);
  assert.match(day, /<circle cx="12" cy="12"/);
});

test('#404 no retired glyph came back to an icon tile', () => {
  // The three glyphs this issue listed that exist nowhere else in the app.
  // The other three survive outside the menus, in two places found while
  // doing this and filed separately rather than swept in here: .rq-mark
  // (the tick and cross on the Ranked feedback screen) and .pcrown (the
  // leaderboard's hat holder). Both need their own measuring.
  for (const glyph of ['↺', '✉', '◇']) {
    assert.doesNotMatch(app, new RegExp(glyph), `${glyph} is still in app.js`);
  }
  const tiles = (app.match(/<span class="lab-choice-icon"[^>]*>(.*?)<\/span>/g) ?? []).join('');
  for (const glyph of ['✓', '♛', '✕']) {
    assert.ok(!tiles.includes(glyph), `${glyph} is back in an icon tile`);
  }
});

// #444 closed this family. The glyphs #404 listed went in #404, the two
// badge marks went in #440, and the points diamond -- the last one, and
// the only one that was inline with text rather than in a tile or a badge
// -- goes here.

test('#444 no text glyph is left doing an icon\'s job', () => {
  // Measured in place before removing it: U+25C6 drew 7.6px of ink at
  // 10.5px, in Nunito, which does not have it, beside a digit of 6.3px
  // from the real font.
  assert.doesNotMatch(app, /◆/, 'the points diamond is back');
  // The whole family, in one sweep, so a new screen cannot quietly add one.
  for (const glyph of ['✓', '✕', '♛', '↺', '✉', '◇', '⚙', '◆']) {
    assert.doesNotMatch(app, new RegExp(glyph), `${glyph} is back in app.js`);
  }
});

test('#444 the arrows stay, for the reason they stayed in #404', () => {
  // They are fallback glyphs too, but they are the same mark on every row,
  // so a device drawing them its own way draws them consistently -- there
  // is no mixed-weight column the way the owner menu had. Pinned so that
  // "no glyphs" above is read as the deliberate line it is, not as an
  // oversight waiting to be tidied.
  assert.match(app, /<span class="lab-arrow" aria-hidden="true">→<\/span>/);
});

test('#444 the podium shows points the way the list does', () => {
  // The reason it was dropped rather than drawn: two rows below, the same
  // quantity was already shown with no mark, so one screen was showing
  // points two ways.
  assert.match(app, /<div class="ppts">\$\{language\.number\(row\.points\)\}<\/div>/);
  assert.match(app, /<b class="board-points">\$\{language\.number\(row\.points\)\}<\/b>/);
});
