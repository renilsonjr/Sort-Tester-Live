// Versus, refined (2026-11-28): the duel's answers reach the bottom and
// Leave sits beside the clock; the standings and the result read like the
// Ranked ones they sit beside.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const screens = readFileSync(new URL('../src/versus/screens.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

const duel = screens.slice(screens.indexOf('async function playQuiz'), screens.indexOf('function showWaiting'));

test('Leave is a pill beside the clock, never under the belts', () => {
  // The trap #504 took off the Ranked question: a full-width button right
  // where a racing thumb lands.
  assert.match(duel, /<div class="rq-top-end">\s*\$\{leaveButton\(\{ compact: true \}\)\}/);
  const afterQuestion = duel.slice(duel.indexOf('id="vs-question"'));
  assert.doesNotMatch(afterQuestion, /leaveButton\(/, 'Leave is back under the belts');
  assert.match(screens, /class="ghost rq-quit" type="button">\$\{esc\(t\('Leave'\)\)\}/);
  // The Handler duel has no belts under it and keeps the wide button.
  const handler = screens.slice(screens.indexOf('function playHandler'), screens.indexOf('// ------------------------------------------------------------ the result'));
  assert.match(handler, /\$\{leaveButton\(\)\}/);
});

test('the warning keeps the pill its size, and still takes two presses', () => {
  assert.match(duel, /<p class="notice vs-leave-warn" data-vs-warn role="alert" hidden><\/p>/);
  const wire = screens.slice(screens.indexOf('function wireLeave'));
  assert.match(wire, /if \(warn\) \{ warn\.textContent = said; warn\.hidden = false; \}\s*\n\s*else button\.textContent = said;/);
  assert.ok(wire.indexOf('armed = true') < wire.indexOf('client.forfeit('));
});

test('the answers take the spare height, as the Ranked ones do', () => {
  assert.match(html, /\n  #app\.attempt-live \.screen-versus \{ flex: 1 0 auto; \}/);
  assert.match(html, /\n  #vs-question \{ flex: 1 0 auto; display: flex; flex-direction: column; gap: 12px; \}/);
  assert.match(html, /\n  #vs-question \.belts \.belt \{ min-height: clamp\(70px, 15\.6dvh, 132px\); \}/);
  const desk = html.slice(html.indexOf('@media (min-width: 900px)'));
  assert.match(desk, /\n    #vs-question, #vs-question \.rq-route \{ flex: 0 0 auto; \}/);
});

test('the score is bigger than the name beside it', () => {
  assert.match(html, /\n  \.vs-tug-you, \.vs-tug-opp \{ font-size: 20px; \}/);
  // the name keeps its own smaller size
  assert.match(html, /\.vs-tug-you b, \.vs-tug-opp b \{[^}]*font-size: 13px/);
});

test('the Versus board leads with the player\'s place', () => {
  const board = screens.slice(screens.indexOf('async function fillBoard'));
  assert.match(board, /<div class="board-mine" id="vs-mine">/);
  assert.match(board, /<p class="board-mine-place">#\$\{esc\(place\)\}<\/p>/);
  // wins and duels only when the server sent the player's own row
  assert.match(board, /const counted = board\.rows\.find\(row => row\.you\);/);
  assert.match(board, /\$\{counted \? `<div class="board-mine-pts">/);
  // the line for a player past the rows shown stays
  assert.match(board, /class="board-your-place"/);
  // and the note about how the standings are kept follows them
  assert.ok(board.lastIndexOf('class="lab-intro tab-intro"') > board.lastIndexOf('<ol class="board">'));
});

test('both boards in the app share one set of rules', () => {
  for (const rule of [
    /#board-panel \.board, #vs-board-panel \.board \{/,
    /#board-panel \.board li, #vs-board-panel \.board li \{/,
    /#board-panel \.board li\.board-you, #vs-board-panel \.board li\.board-you \{/,
  ]) assert.match(html, rule);
  assert.match(html, /\n  #vs-board-panel \.board-points \.vs-wins \{ display: inline; margin-left: 3px; \}/);
});

test('the result marks the winner without pushing the tiles out of line', () => {
  const result = screens.slice(screens.indexOf('function showResult'), screens.indexOf('// ------------------------------------------------------- the leaderboard'));
  assert.match(result, /const won = state\.outcome === 'you' \? state\.you : state\.outcome === 'opponent' \? state\.opponent : null;/);
  assert.match(result, /<span class="vs-final-crown">\$\{esc\(t\('Winner'\)\)\}<\/span>/);
  assert.match(result, /<span class="vs-final-crown is-blank" aria-hidden="true"><\/span>/);
  assert.match(html, /\n  \.vs-final-crown\.is-blank \{ visibility: hidden; \}/);
});

test('a title inside a card is not a page heading', () => {
  assert.match(html, /\n  \.screen-versus > \.lab-title, \.vs-result \.lab-title \{ font-size: 24px; \}/);
});

test('the new words have Spanish', () => {
  for (const key of ['Leave', 'Winner']) {
    assert.ok(i18n.includes(`'${key}': '`), `no Spanish for: ${key}`);
  }
});
