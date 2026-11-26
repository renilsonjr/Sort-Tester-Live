import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const read = name => readFile(new URL(`../${name}`, import.meta.url), 'utf8');
const [app, css, i18n] = await Promise.all([read('src/app.js'), read('index.html'), read('src/i18n.js')]);
const { modules: [{ createBestScores, MODES }], cleanup } = await loadAppModules(['src/conveyor/bestScores.js']);
after(cleanup);

// ---------------------------------------------------------------------------
// Where Handler lives: a tab of its own and a stripe of its own.
// ---------------------------------------------------------------------------

test('Handler is a fifth tab, and a guest gets it too', () => {
  const tabs = app.slice(app.indexOf('function navTabs()'), app.indexOf('function labPage'));
  const beforeSignIn = tabs.slice(0, tabs.indexOf('if (signedIn())'));
  assert.match(beforeSignIn, /\['handler', ICONS\.handler, t\('Handler'\)\]/,
    'a guest can play, so the tab cannot sit behind signedIn()');
  // It sits with Practice, because it is practice, and before Ranked.
  assert.ok(beforeSignIn.indexOf("'practice'") < beforeSignIn.indexOf("'handler'"));
  assert.ok(tabs.indexOf("'handler'") < tabs.indexOf("'ranked'"));
  assert.match(app, /button\.dataset\.nav === 'handler'\) showHandler\(\)/);
  assert.match(app, /handler: '<svg viewBox="0 0 24 24"/, 'the tab needs an icon from the same set');
});

test('the Home stripe sits under Ranked and before Practice, not inside Ranked', () => {
  const home = app.slice(app.indexOf('home-split-hero'), app.indexOf('home-split-actions'));
  assert.match(home, /home-split-handler/);
  // Inside the Ranked stripe would say the mini-game is part of Ranked, and
  // the persistence boundary says the opposite.
  const hero = app.slice(app.indexOf('home-split-hero'), app.indexOf('home-split-climb'));
  assert.ok(!hero.includes('home-handler'), 'Handler must not be inside the Ranked hero');
  assert.match(app, /view\.querySelector\('#home-handler'\)\.addEventListener\('click', showHandler\)/);
  // Before the Practice shortcuts.
  assert.ok(app.indexOf('home-split-handler') < app.indexOf('id="home-practice"'));
});

// ---------------------------------------------------------------------------
// The dock, measured rather than eyeballed (#396 asks for this by name).
// ---------------------------------------------------------------------------

test('a five-wide dock shrinks its label, because a long one was clipped', () => {
  // Measured in a browser at 320px: each tab is 64px, and "Clasificatorio",
  // the Spanish Ranked label, is 68.9px of text at the dock's 11px. At 10px
  // it is 62.7px and fits. Four tabs and a guest's three are untouched.
  assert.match(app, /navTabs\(\)\.length > 4 \? ' lab-nav-tight' : ''/);
  assert.match(css, /\.lab-nav-tight button \{ font-size: 10px; \}/);
  // The word itself is not shortened: it is the owner's.
  assert.match(i18n, /'Ranked': 'Clasificatorio'/);
});

// ---------------------------------------------------------------------------
// Leaving the tab has to stop everything the game started.
// ---------------------------------------------------------------------------

test('leaving Handler stops its frame, clock, audio and listeners', () => {
  // The screen can be left in more ways than one -- a dock tab, the Home
  // stripe, a sign-in, a language change that redraws the page -- so the
  // unmount lives in render(), the single place that swaps a screen, beside
  // the music and the heartbeat decisions that exist for the same reason.
  const render = app.slice(app.indexOf('function render(node)'), app.indexOf('function render(node)') + 600);
  assert.match(render, /unmountHandler\(\)/);
  assert.match(app, /function unmountHandler\(\) \{[\s\S]*?handlerScreen = null;[\s\S]*?leaving\.unmount\(\);/,
    'clear the reference before unmounting, or a re-entrant render loops');
  // Re-entering must not leave two belts running.
  const page = app.slice(app.indexOf('function showHandler()'), app.indexOf('function showPractice()'));
  assert.match(page, /unmountHandler\(\);\s*\n\s*handlerScreen = createHandlerScreen\(/);
});

test('the page is a mount point and decides nothing about the game', () => {
  const page = app.slice(app.indexOf('function showHandler()'), app.indexOf('function showPractice()'));
  for (const forbidden of ['ROUND_MS', 'COMBO', 'requestAnimationFrame', 'getContext(\'2d\')', 'drawRoute']) {
    assert.ok(!page.includes(forbidden), `app.js must not take over ${forbidden}`);
  }
  assert.match(page, /engine: conveyorEngine/);
  assert.match(page, /routes: conveyorRoutes/);
});

// ---------------------------------------------------------------------------
// The persistence boundary, from the client's side.
// ---------------------------------------------------------------------------

function fakeFetch(script) {
  const calls = [];
  const fetchFn = async (url, options) => {
    calls.push({ url, method: options.method, body: options.body ? JSON.parse(options.body) : undefined });
    const next = script.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  return { fetchFn, calls };
}
const answer = (status, body) => ({ status, ok: status >= 200 && status < 300, json: async () => body });

test('a signed-in account loads its four bests and raises one', async () => {
  const { fetchFn, calls } = fakeFetch([
    answer(200, { best: { easy: 4, medium: 0, hard: 21, expert: 0 } }),
    answer(200, { mode: 'hard', best: 30 }),
  ]);
  const best = createBestScores({ fetchFn });
  await best.load();
  assert.equal(best.saved, true);
  assert.equal(best.get('hard'), 21);
  best.set('hard', 30);
  assert.equal(best.get('hard'), 30, 'the screen has already drawn it; do not wait on the server');
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.deepEqual(calls[1], { url: '/api/handler/best', method: 'PUT', body: { mode: 'hard', score: 30 } });
});

test('a worse round is never sent, and a bad one never leaves the page', async () => {
  const { fetchFn, calls } = fakeFetch([answer(200, { best: { easy: 0, medium: 0, hard: 21, expert: 0 } })]);
  const best = createBestScores({ fetchFn });
  await best.load();
  best.set('hard', 8);
  best.set('nightmare', 99);
  best.set('easy', -1);
  best.set('easy', 2.5);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.length, 1, 'only the load should have gone out');
  assert.equal(best.get('hard'), 21);
});

test('a guest plays and is told the score is not saved', async () => {
  const { fetchFn, calls } = fakeFetch([answer(401, null)]);
  const best = createBestScores({ fetchFn });
  await best.load();
  assert.equal(best.saved, false);
  best.set('easy', 12);
  // It still reads back, so the screen can show the round's own best, but
  // nothing is sent and the summary says so rather than showing a zero.
  assert.equal(best.get('easy'), 12);
  await new Promise(resolve => setTimeout(resolve, 0));
  assert.equal(calls.length, 1);
  const view = await read('src/conveyor/view.js');
  assert.match(view, /bestScores\.saved === false/);
  assert.match(i18n, /'Scores are kept only while you are signed in\. This one is not saved\.'/);
});

test('a server that is down costs the player nothing on screen', async () => {
  const { fetchFn } = fakeFetch([new Error('offline')]);
  const best = createBestScores({ fetchFn });
  await best.load();
  assert.equal(best.saved, false);
  assert.deepEqual(MODES.map(mode => best.get(mode)), [0, 0, 0, 0]);
  assert.match(String(best.lastError), /offline/);
});
