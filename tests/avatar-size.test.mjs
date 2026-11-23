// How big the chosen icon is drawn (issue #272, owner's feedback 2026-11-23).
//
// The icon was drawn at the size of the letter it replaces: 18px inside a
// 46px podium disc, leaving most of the circle empty. It now fills the disc,
// and the profile matches the podium.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

// The declaration block of a selector, as written in index.html.
function rule(selector) {
  const at = html.indexOf(`\n  ${selector} {`);
  assert.notEqual(at, -1, `no rule for ${selector}`);
  return html.slice(at, html.indexOf('}', at));
}

function px(selector, property) {
  const match = rule(selector).match(new RegExp(`${property}:\\s*(\\d+(?:\\.\\d+)?)px`));
  assert.ok(match, `${selector} has no ${property}`);
  return Number(match[1]);
}

test('a disc holding an icon says so, so the letter keeps its own size', () => {
  const board = app.slice(app.indexOf('const slot = (row, cls)'));
  assert.match(board, /class="pdisc\$\{/);
  assert.match(board, /has-avatar/);
});

test('the icon fills the podium disc instead of floating in it', () => {
  const disc = px('.pdisc', 'width');
  const glyph = px('.pdisc.has-avatar', 'font-size');
  assert.ok(glyph >= disc * 0.7, `${glyph}px in a ${disc}px disc is still mostly empty`);
  assert.ok(glyph <= disc, `${glyph}px would overflow a ${disc}px disc`);
});

test('first place is bigger, and its icon grows with it', () => {
  const first = px('.pslot.p1 .pdisc', 'width');
  const glyph = px('.pslot.p1 .pdisc.has-avatar', 'font-size');
  assert.ok(first > px('.pdisc', 'width'));
  assert.ok(glyph >= first * 0.7 && glyph <= first);
});

test('the profile icon matches the podium', () => {
  assert.equal(px('.pf-avatar:not(:empty)', 'font-size'), px('.pdisc.has-avatar', 'font-size'));
});

test('the list row carries it, large enough to read', () => {
  const board = app.slice(app.indexOf('const rows = listRows.map'));
  assert.match(board, /class="board-avatar"/);
  assert.ok(px('.board-avatar', 'font-size') >= 20);
});
