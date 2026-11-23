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

// Was: the shell had to be a card at least 900px wide. The owner chose on
// 2026-11-23 to have the app fill the window instead, so the shell is no
// longer capped at all -- the reading width moved onto the content, where it
// can differ per screen. What still has to hold is that the phone's 430px cap
// is lifted and that a cap exists further in, or a sentence would run the
// whole width of a monitor.
test('the shell fills the window and the reading width moves to the content', () => {
  const desk = desktopBlock();
  assert.match(desk, /#app\.lab-page\s*\{[^}]*max-width:\s*none/,
    'the shell should span the window, not sit in a fixed-width card');

  const col = desk.match(/--desk-col:\s*(\d+)px/);
  assert.ok(col, 'there is no reading-width token for the content');
  assert.ok(Number(col[1]) >= 900, `${col[1]}px is barely wider than a phone`);
  assert.ok(Number(col[1]) <= 1400, `${col[1]}px is too wide to read a sentence across`);

  // The cap has to reach both the header row and the screen, or they stop
  // lining up with each other.
  assert.match(desk, /\.lab-top-row,\s*\.lab-main > \.lab-screen\s*\{[^}]*max-width:\s*var\(--desk-col\)/);
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

// ---------------------------------------------------------------------------
// The five screens that had no desktop layout of their own (2026-11-23). Each
// one follows one of the two rules the approved mock set: lists and panels get
// a second column, forms and quizzes stay narrow and centred.
// ---------------------------------------------------------------------------

test('the sidebar takes its colour from a token, not a literal', () => {
  const desk = desktopBlock();
  const nav = desk.match(/\.lab-nav\s*\{[^}]*\}/);
  assert.ok(nav, 'the sidebar rule is gone');
  // A literal here was a dark brown at 45%, which over the cream day
  // background read as grey. Only a token flips with the theme.
  assert.doesNotMatch(nav[0], /background:\s*rgba?\(/,
    'the sidebar is painting itself with a literal colour again');
  assert.match(nav[0], /background:\s*var\(--/);
});

test('the grid rows stretch, so the sidebar reaches the bottom', () => {
  const desk = desktopBlock();
  const shell = desk.match(/\.lab-shell\s*\{[^}]*\}/);
  assert.ok(shell, 'the shell rule is gone');
  // `align-content: start` packed the rows and left the sidebar ending at the
  // height of the content -- a 501px band of background under it on Practice.
  assert.doesNotMatch(shell[0], /align-content:\s*start/);
  assert.match(shell[0], /min-height:\s*100dvh/);
});

test('Practice puts its two shelves side by side', () => {
  assert.match(app, /class="lab-screen screen-practice"/);
  assert.match(desktopBlock(), /\.screen-practice\s*\{[^}]*grid-template-columns/);
});

test('the chart keeps its controls beside the list', () => {
  assert.match(app, /class="lab-screen screen-chart"/);
  assert.match(app, /class="chart-aside"/);
  // Same trick as .home-split: the group has to dissolve on a phone, or the
  // controls become one flex item and lose .lab-screen's 16px gap.
  assert.match(html, /\.chart-aside \{ display: contents; \}/);
  const desk = desktopBlock();
  assert.match(desk, /\.screen-chart\s*\{[^}]*grid-template-columns/);
  // The list is over 8000px tall; the filters are only useful if they stay.
  assert.match(desk, /\.screen-chart > \.chart-aside\s*\{[^}]*position:\s*sticky/);
});

test('Profile puts the numbers beside the climb', () => {
  assert.match(app, /class="lab-screen screen-profile"/);
  assert.match(desktopBlock(), /\.screen-profile > #profile-panel\s*\{[^}]*grid-template-columns/);
});

test('Owner tools lists its actions in two columns', () => {
  assert.match(app, /class="lab-screen screen-owner"/);
  assert.match(desktopBlock(), /\.screen-owner\s*\{[^}]*grid-template-columns/);
});

test('the promotion screens stay narrow, like the other decisions', () => {
  assert.match(app, /class="lab-screen screen-promo"/);
  const desk = desktopBlock();
  const match = desk.match(/\.lab-main > \.screen-promo\s*\{[^}]*max-width:\s*(\d+)px/);
  // `.lab-main >` is load-bearing: the --desk-col rule is `.lab-main >
  // .lab-screen`, so a bare `.screen-promo` loses on specificity and the
  // screen stayed 1080px wide.
  assert.ok(match, 'the promotion screens are not held to a readable width');
  assert.ok(Number(match[1]) <= 640, `${match[1]}px is too wide for a single decision`);
});
