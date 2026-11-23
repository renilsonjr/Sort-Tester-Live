// The desktop shell (issue #273, mock approved 2026-11-23).
//
// One breakpoint. Below it nothing changes: the phone keeps its bottom dock
// and its single column. Above it the dock becomes a left sidebar, the
// column widens, and the screens where width pays get a second column.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

const DESKTOP = '@media (min-width: 900px)';

// Everything inside the desktop media query, which is one block at the end.
function desktopBlock() {
  const at = html.indexOf(DESKTOP);
  assert.notEqual(at, -1, 'there is no desktop media query');
  // walk braces from the query's own opening brace to its match
  const start = html.indexOf('{', at);
  let depth = 0;
  for (let i = start; i < html.length; i += 1) {
    if (html[i] === '{') depth += 1;
    else if (html[i] === '}') {
      depth -= 1;
      if (depth === 0) return html.slice(start, i);
    }
  }
  throw new Error('the desktop media query is never closed');
}

test('there is exactly one desktop breakpoint', () => {
  assert.equal(html.split(DESKTOP).length - 1, 1);
});

test('the desktop wrappers are invisible to the phone', () => {
  // .lab-screen is a flex column with a gap; a wrapper that is laid out would
  // make the stripes it holds a single flex item and swallow that gap
  assert.match(html, /\.home-split, \.board-split \{ display: contents; \}/);
});

test('the phone rules are never touched by it', () => {
  // the block only ever adds; it must not sit inside a max-width query
  const before = html.slice(0, html.indexOf(DESKTOP));
  const openQueries = (before.match(/@media/g) || []).length;
  assert.ok(openQueries > 0, 'expected the phone rules to come first');
  assert.doesNotMatch(desktopBlock(), /@media/, 'no nested query inside the desktop block');
});

test('the dock becomes a sidebar instead of staying fixed to the bottom', () => {
  const desk = desktopBlock();
  assert.match(desk, /\.lab-nav\s*\{[^}]*position:\s*static\s*!important/);
  assert.match(desk, /\.lab-shell\s*\{[^}]*display:\s*grid/);
  // the DOM order is top, main, nav — so the sidebar is placed, not moved
  assert.match(desk, /grid-template-areas/);
  assert.match(desk, /\.lab-nav\s*\{[^}]*grid-area:\s*nav/);
});

test('the column widens past the phone width', () => {
  const desk = desktopBlock();
  const match = desk.match(/#app\.lab-page\s*\{[^}]*max-width:\s*(\d+)px/);
  assert.ok(match, 'the app column keeps its phone width on desktop');
  assert.ok(Number(match[1]) >= 900, `${match[1]}px is barely wider than a phone`);
});

test('nothing clears a dock that is no longer at the bottom', () => {
  assert.match(desktopBlock(), /\.lab-main\s*\{[^}]*padding-bottom/);
});

test('the leaderboard puts the podium and the standings side by side', () => {
  assert.match(app, /class="board-split\$\{rows \? ' board-split-two' : ''\}"/);
  assert.match(desktopBlock(), /\.board-split-two\s*\{[^}]*grid-template-columns/);
});

test('Home puts what you tap beside the hero, not below it', () => {
  assert.match(app, /class="home-split"/);
  assert.match(desktopBlock(), /\.home-split\s*\{[^}]*grid-template-columns/);
});

test('the Ranked quiz stays narrow on purpose', () => {
  const desk = desktopBlock();
  const match = desk.match(/#rq-play\s*\{[^}]*max-width:\s*(\d+)px/);
  assert.ok(match, 'the quiz is not held to a readable width on desktop');
  assert.ok(Number(match[1]) <= 640, `${match[1]}px is too wide for four belts`);
});

test('the keyboard answers the Ranked quiz', () => {
  const play = app.slice(app.indexOf('async function playRankedAttempt'));
  const body = play.slice(0, play.indexOf('\n}\n'));
  assert.match(body, /addEventListener\('keydown'/);
  // 1-4 pick a belt, Escape opens the cancel confirmation
  assert.match(body, /Escape/);
  assert.match(body, /belts\[index\]/);
  // a listener from a question that is gone takes itself off
  assert.match(body, /removeEventListener\('keydown', onKey\)/);
  // and the key is drawn on the button, so nobody has to guess
  assert.match(app, /class="belt-key"/);
});

test('a keyboard user can always see where they are', () => {
  assert.match(desktopBlock(), /:focus-visible\s*\{[^}]*outline/);
});

test('the sidebar labels are the ones already translated', () => {
  // the nav is built from navTabs(), so desktop adds no new text to translate
  assert.match(app, /function navTabs/);
  assert.match(i18n, /'Practice': '/);
});
