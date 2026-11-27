import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The Ranked question, as the owner approved it on 2026-11-27: the four
// answers sit at the bottom of the screen and Quit sits at the top, beside
// the clock. Measured in the running app: at 844px the belts end 20px above
// the bottom edge (132px each); at 667px and 568px the page still fits
// without scrolling (104px and 89px).

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const play = app.slice(app.indexOf('id="rq-play"'), app.indexOf("'ranked', () => playRankedAttempt(attempt, mode, tally)"));

test('Quit sits in the top row, beside the clock, and nowhere under the answers', () => {
  const top = play.slice(play.indexOf('class="tb-top"'), play.indexOf('class="tb-bar"'));
  assert.match(top, /id="rq-cancel" class="ghost rq-quit" type="button"/);
  assert.ok(top.indexOf('id="rq-cancel"') < top.indexOf('id="rq-clock"'));
  const afterQuestion = play.slice(play.indexOf('id="rq-question"'));
  assert.doesNotMatch(afterQuestion, /rq-cancel/, 'no Quit under the belts, where a racing thumb lands');
  // Escape still asks to quit through the same button.
  assert.match(app, /view\.querySelector\('#rq-cancel'\)\.click\(\)/);
});

test('Quit is small but still a full touch target', () => {
  const rule = html.match(/\n  #rq-play \.rq-quit \{([^}]*)\}/)[1];
  assert.match(rule, /min-height: 44px/);
  assert.match(rule, /width: auto/);
});

test('the route card takes the spare height, so the answers end at the bottom', () => {
  assert.match(html, /\n  #app\.attempt-live \.lab-main \{ display: flex; flex-direction: column; \}/);
  assert.match(html, /\n  #rq-play, #rq-question \{ flex: 1 0 auto; \}/);
  assert.match(html, /\n  #rq-question \.rq-prompt \{ flex: 1 0 auto;/);
  // :has() would drop the whole layout on a browser that does not know it.
  assert.doesNotMatch(html, /:has\(> #rq-play\) \{/);
});

test('a desktop keeps the question at its own height', () => {
  const desk = html.slice(html.lastIndexOf('@media (min-width: 900px)'));
  assert.match(desk, /#rq-play, #rq-question, #rq-question \.rq-prompt \{ flex: 0 0 auto; \}/);
  assert.match(desk, /#rq-question \.belts \.belt \{ min-height: clamp\(70px, 12\.5dvh, 104px\); \}/);
});
