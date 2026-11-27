// Versus, the 1 vs 1 frame over the two mini-games.
//
// What is held here: the pure rules (room codes, the tug bar, the shared
// random source), the client's routes, the promise that a handler duel
// deals both players the same packages, and the things Versus must not do
// -- ask a new question, keep a Handler best, speak Portuguese, or leave a
// string without Spanish.
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';
import { createLanguage } from '../src/i18n.js';
import { createVersusClient } from '../src/versus/client.js';
import {
  HANDLER_DUEL_MODE, POLL_MS, REVIEW_MS, TUG_MIN,
  normalizeCode, seededRandom, standing, tugShare,
} from '../src/versus/logic.js';

const read = name => readFileSync(new URL(`../${name}`, import.meta.url), 'utf8');
const screens = read('src/versus/screens.js');
const appSource = read('src/app.js');
const viewSource = read('src/conveyor/view.js');
const { modules: [routes], cleanup } = await loadAppModules(['src/conveyor/routes.js']);
after(cleanup);

// ---------------------------------------------------------------- room codes

test('a room code is the same room however it is typed', () => {
  for (const typed of ['HAT-42', 'hat-42', 'hat42', ' Hat 42 ', 'HAT–42', 'hat_42']) {
    assert.equal(normalizeCode(typed), 'HAT-42', `"${typed}"`);
  }
  assert.equal(normalizeCode('dock07'), 'DOCK-07');
  assert.equal(normalizeCode(''), '');
  assert.equal(normalizeCode(null), '');
});

// ------------------------------------------------------------------ tug bar

test('level scores sit in the middle, including nothing to nothing', () => {
  assert.equal(tugShare(0, 0), 50);
  assert.equal(tugShare(400, 400), 50);
});

test('the bar leans toward whoever is ahead and never squeezes a name off', () => {
  assert.ok(tugShare(300, 100) > 50);
  assert.ok(tugShare(100, 300) < 50);
  assert.equal(tugShare(1000, 0), 100 - TUG_MIN);
  assert.equal(tugShare(0, 1000), TUG_MIN);
  for (let mine = 0; mine <= 2000; mine += 137) {
    for (let theirs = 0; theirs <= 2000; theirs += 211) {
      const share = tugShare(mine, theirs);
      assert.ok(share >= TUG_MIN && share <= 100 - TUG_MIN, `${mine}-${theirs} gave ${share}`);
    }
  }
});

test('nonsense scores do not break the bar', () => {
  assert.equal(tugShare(undefined, null), 50);
  assert.equal(tugShare(-5, -9), 50);
  assert.equal(tugShare('abc', 100), TUG_MIN);
});

test('the caption says who is ahead and by how much', () => {
  assert.deepEqual(standing(0, 0), { key: 'level', margin: 0 });
  assert.deepEqual(standing(870, 540), { key: 'ahead', margin: 330 });
  assert.deepEqual(standing(540, 870), { key: 'behind', margin: 330 });
});

// ------------------------------------------------- the shared random source

test('the same seed gives the same sequence, a different seed another', () => {
  const a = seededRandom('3f9a1c0b77de4410');
  const b = seededRandom('3f9a1c0b77de4410');
  const c = seededRandom('3f9a1c0b77de4411');
  const first = Array.from({ length: 50 }, () => a());
  assert.deepEqual(Array.from({ length: 50 }, () => b()), first);
  assert.notDeepEqual(Array.from({ length: 50 }, () => c()), first);
  for (const value of first) assert.ok(value >= 0 && value < 1);
});

test('the sequence is spread out, not stuck in a corner', () => {
  const next = seededRandom('spread');
  const buckets = new Array(10).fill(0);
  for (let i = 0; i < 5000; i += 1) buckets[Math.floor(next() * 10)] += 1;
  for (const count of buckets) assert.ok(count > 380 && count < 620, `a bucket held ${count} of 5000`);
});

test('a handler duel deals both players the same packages', () => {
  // The whole fairness of the handler duel: two phones, one seed, and the
  // Handler's own drawRoute -- same code, same belts, same side.
  const deal = seed => {
    const random = seededRandom(seed);
    const mode = routes.MODES[HANDLER_DUEL_MODE];
    const dealt = [];
    for (let i = 0; i < 80; i += 1) {
      const route = routes.drawRoute(routes.routePool(mode.deck(i / 80)), random);
      dealt.push(`${route.svc}|${route.state}|${route.code}|${route.options.map(o => o.belt + (o.correct ? '*' : '')).join('/')}`);
    }
    return dealt;
  };
  assert.deepEqual(deal('a1b2c3d4e5f60718'), deal('a1b2c3d4e5f60718'));
  assert.notDeepEqual(deal('a1b2c3d4e5f60718'), deal('0000000000000000'));
});

test('the duel plays the hardest handler mode, which exists', () => {
  assert.equal(HANDLER_DUEL_MODE, 'expert');
  assert.ok(routes.MODES[HANDLER_DUEL_MODE]);
});

test('the review fits inside the three seconds the server budgets', () => {
  assert.ok(REVIEW_MS < 3000);
  assert.equal(POLL_MS, 1000);
});

// ------------------------------------------------------------------ client

function fakeFetch(answer = { ok: true, status: 200, json: async () => ({ fine: true }) }) {
  const calls = [];
  const fetchFn = async (url, options) => { calls.push({ url, ...options }); return answer; };
  return { calls, fetchFn };
}

test('each client call goes to its own route', async () => {
  const { calls, fetchFn } = fakeFetch();
  const client = createVersusClient({ fetchFn });
  await client.createRoom('quiz');
  await client.joinRoom('HAT-42');
  await client.readRoom('r1');
  await client.leaveRoom('r1');
  await client.startMatch('r1');
  await client.readMatch('m1');
  await client.question('m1');
  await client.answer('m1', 3, 'GOLD');
  await client.progress('m1', 41, true);
  await client.forfeit('m1');
  await client.leaderboard();
  assert.deepEqual(calls.map(call => `${call.method} ${call.url}`), [
    'POST /api/versus/rooms',
    'POST /api/versus/rooms/join',
    'GET /api/versus/rooms/r1',
    'POST /api/versus/rooms/r1/leave',
    'POST /api/versus/rooms/r1/start',
    'GET /api/versus/matches/m1',
    'GET /api/versus/matches/m1/question',
    'POST /api/versus/matches/m1/answer',
    'POST /api/versus/matches/m1/progress',
    'POST /api/versus/matches/m1/forfeit',
    'GET /api/versus/leaderboard',
  ]);
  assert.deepEqual(JSON.parse(calls[0].body), { game: 'quiz' });
  assert.deepEqual(JSON.parse(calls[7].body), { seq: 3, choice: 'GOLD' });
  assert.deepEqual(JSON.parse(calls[8].body), { score: 41, final: true });
  for (const call of calls) assert.equal(call.credentials, 'same-origin');
});

test('a timed-out question is sent as no choice, not as null', async () => {
  const { calls, fetchFn } = fakeFetch();
  await createVersusClient({ fetchFn }).answer('m1', 1, null);
  assert.deepEqual(JSON.parse(calls[0].body), { seq: 1, choice: '' });
});

test('a dropped request is a missed beat, never a thrown error', async () => {
  const client = createVersusClient({ fetchFn: async () => { throw new Error('offline'); } });
  assert.deepEqual(await client.readMatch('m1'), { ok: false, status: 0, data: null });
  const broken = createVersusClient({ fetchFn: async () => ({ ok: false, status: 502, json: async () => { throw new Error('not json'); } }) });
  assert.deepEqual(await broken.readMatch('m1'), { ok: false, status: 502, data: null });
});

// ------------------------------------------------------- what Versus reuses

test('Versus asks no question of its own and deals no package of its own', () => {
  // No question text, no belt list and no route table lives in Versus: the
  // quiz duel is served by the Ranked bank and the handler duel mounts the
  // Handler. A second bank here would be a second thing to keep correct.
  for (const source of [screens, read('src/versus/logic.js'), read('src/versus/client.js')]) {
    assert.ok(!/questions\.js|chart\.js|levels\.js|decks\.js/.test(source), 'Versus must not import routing content');
    assert.ok(!/\b(BROWN|ORANGE|PURPLE)\b/.test(source), 'no belt names are written into Versus');
  }
  assert.match(appSource, /random: seededRandom\(seed\)/);
  assert.match(appSource, /duel: \{ mode: HANDLER_DUEL_MODE, onScore, onEnd \}/);
});

test('a duel round cannot be paused, restarted or left through the Handler', () => {
  // Both players' minute has to be the same minute. The Handler's own
  // pause and restart would stretch one side's clock past the other's.
  assert.match(viewSource, /\$\{duel \? '' : `<button type="button" class="hd-icon-btn" data-hd-pause/);
  assert.match(viewSource, /\$\{duel \? '' : `<button type="button" class="hd-leave" data-hd-leave/);
  assert.match(viewSource, /if \(duel\) startCountdown\(duel\.mode\); else showModes\(\);/);
});

test('a duel score is never written as a Handler best', () => {
  const summary = viewSource.slice(viewSource.indexOf('function showSummary()'));
  const handOff = summary.indexOf('if (duel) { duel.onEnd?.(summary); return; }');
  const bestWrite = summary.indexOf('bestScores.set(');
  assert.ok(handOff > 0 && handOff < bestWrite, 'the duel must leave before the best score is touched');
});

test('the dock is not drawn while a duel is live', () => {
  // A dock under a timed duel is a way to lose it by a slip of the thumb,
  // exactly as under a Ranked attempt (#427).
  for (const screen of ['async function playQuiz', 'function playHandler', 'function showWaiting']) {
    const body = screens.slice(screens.indexOf(screen));
    const markup = body.slice(0, body.indexOf("`, 'versus'"));
    assert.match(markup, /data-attempt-live/, `${screen} must hide the dock`);
  }
  for (const screen of ['function showVersus', 'function showResult', 'function showBoard']) {
    const body = screens.slice(screens.indexOf(screen));
    const markup = body.slice(0, body.indexOf("`, 'versus'"));
    assert.ok(!/data-attempt-live/.test(markup), `${screen} keeps the dock`);
  }
});

test('leaving a duel takes two presses and says what it costs', () => {
  assert.match(screens, /Press again to leave\. Leaving counts as a loss\./);
  const wire = screens.slice(screens.indexOf('function wireLeave'));
  assert.ok(wire.indexOf('armed = true') < wire.indexOf('client.forfeit('));
});

test('every poll stops when its screen leaves the page', () => {
  const every = screens.slice(screens.indexOf('function every('), screens.indexOf('function face('));
  assert.match(every, /if \(!view\.isConnected\) \{ clearInterval\(timer\); return; \}/);
  assert.match(every, /if \(busy\) return;/, 'a slow answer must not stack requests');
});

test('Versus is a tab for signed-in players only', () => {
  const tabs = appSource.slice(appSource.indexOf('function navTabs()'), appSource.indexOf('function labPage('));
  assert.ok(tabs.indexOf("tabs.push(['versus'") > tabs.indexOf('if (signedIn())'));
  assert.match(appSource, /else if \(button\.dataset\.nav === 'versus'\) showVersus\(\);/);
});

// ------------------------------------------------------------- the language

function shownSentences() {
  const keys = new Set();
  const readRaw = raw => new Function(`return '${raw}'`)();
  for (const m of screens.matchAll(/\bt\(\s*'((?:[^'\\]|\\.)*)'/g)) keys.add(readRaw(m[1]));
  // t(a ? 'one' : 'other') and the names kept in tables
  for (const m of screens.matchAll(/\bt\(\s*[^'"`)][^)]*?\)/gs)) {
    for (const s of m[0].matchAll(/[?:]\s*'((?:[^'\\]|\\.)*)'/g)) keys.add(readRaw(s[1]));
  }
  for (const name of ['Quiz duel', 'Handler duel', 'You won', 'You lost', 'A tie', 'Level']) keys.add(name);
  return [...keys];
}

test('every sentence Versus shows has a Spanish entry', () => {
  const es = createLanguage(null);
  es.set('es');
  // 'Versus' and '1 vs 1' read the same in Spanish, on purpose.
  const same = new Set(['Versus', '1 vs 1']);
  const keys = shownSentences();
  assert.ok(keys.length > 40, `expected to find Versus's sentences, found ${keys.length}`);
  const missing = keys.filter(key => /[A-Za-z]{2}/.test(key) && !same.has(key) && es.text(key) === key);
  assert.deepEqual(missing, []);
});

test('placeholders survive translation', () => {
  const es = createLanguage(null);
  es.set('es');
  assert.equal(es.text('Waiting for {name} to start.', { name: 'ana' }), 'Esperando a que ana empiece.');
  assert.equal(es.text('You are ahead by {n}', { n: 330 }), 'Vas ganando por 330');
});

test('the app speaks English and Spanish, and Versus adds no third language', () => {
  for (const word of ['Sala', 'Jogar', 'Você', 'Entrar na', 'Vitória', 'Aguardando', 'Partida']) {
    assert.ok(!screens.includes(word), `"${word}" is Portuguese; the app is EN + ES`);
  }
});

// ------------------------------------------- found by playing a real duel

test('the names sit above the tug bar, never on it', () => {
  // On the bar, a big lead ran the gold fill under the other player's name
  // and left light text on gold. Above it, no score can do that.
  const markup = screens.slice(screens.indexOf('function tugMarkup'), screens.indexOf('function paintTug'));
  const names = markup.indexOf('class="vs-tug-names"');
  const track = markup.indexOf('class="vs-tug" data-vs-tug');
  assert.ok(names > 0 && track > names, 'the names row comes before the track');
  assert.match(markup, /<div class="vs-tug" data-vs-tug role="img"><i class="vs-tug-fill" data-vs-fill><\/i><\/div>/,
    'the track holds the fill and nothing else');
});

test('the handler duel tells the server its last score, in order', () => {
  // A wrong belt takes a point off, so the score can fall and the server
  // keeps the last one it hears. Two reports in flight could land out of
  // order and leave an older, higher number standing.
  const body = screens.slice(screens.indexOf('function playHandler'), screens.indexOf('// ------------------------------------------------------------ the result'));
  assert.match(body, /if \(sending \|\| latest === sent\) return;/, 'one report in flight at a time');
  const end = body.slice(body.indexOf('onEnd:'));
  assert.ok(end.indexOf('while (sending)') < end.indexOf('client.progress(state.id, summary.score, true)'),
    'the final score waits for a report already in flight');
});
