import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [engine], cleanup } = await loadAppModules(['src/conveyor/engine.js']);
after(cleanup);
const {
  COMBO_CAP, COMBO_STEP, DEFAULT_LANE, LEFT, MAX_TICK_MS, PACKAGE_GAP_RATIO, RIGHT, ROUND_MS,
  createGame, multiplierFor,
} = engine;

// A question source that never randomises: the correct belt is always on the
// left unless a test says otherwise, so a test can sort or missort on purpose.
function source({ correctSide = LEFT, belt = 'GOLD', wrong = 'BLUE' } = {}) {
  const decks = [];
  const next = deck => {
    decks.push(deck);
    const options = correctSide === LEFT
      ? [{ belt, correct: true }, { belt: wrong, correct: false }]
      : [{ belt: wrong, correct: false }, { belt, correct: true }];
    return { id: `route-${decks.length}`, code: '207', belt, options };
  };
  next.decks = decks;
  return next;
}

const flat = { speed: () => 60, deck: () => 'level-medium' };
const expert = { speed: p => 84 + 48 * p, deck: p => (p < 1 / 3 ? 'level-medium' : 'level-hard') };

// Sort the front package n times, advancing just enough time to refill.
function sortTimes(game, n, side = LEFT) {
  const results = [];
  for (let i = 0; i < n; i += 1) {
    results.push(game.choose(side, game.snapshot().activePackageId));
    game.tick(16);
  }
  return results;
}

// ---------------------------------------------------------------------------
// Rule 16: the multiplier.
// ---------------------------------------------------------------------------

test('the multiplier steps every COMBO_STEP sorts and stops at COMBO_CAP', () => {
  assert.equal(multiplierFor(0), 1);
  assert.equal(multiplierFor(COMBO_STEP - 1), 1);
  assert.equal(multiplierFor(COMBO_STEP), 2);
  assert.equal(multiplierFor(COMBO_STEP * 2), 3);
  assert.equal(multiplierFor(COMBO_STEP * (COMBO_CAP - 1)), COMBO_CAP);
  assert.equal(multiplierFor(COMBO_STEP * 50), COMBO_CAP, 'the ceiling must hold');
});

// ---------------------------------------------------------------------------
// Rules 13 to 17: scoring.
//
// The sequence the owner checked by hand: twelve straight sorts score
// 1,1,1,1,1,2,2,2,2,2,3,3 and total 21.
// ---------------------------------------------------------------------------

test('twelve straight sorts score the sequence the owner checked', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const steps = [];
  let previous = 0;
  for (let i = 0; i < 12; i += 1) {
    sortTimes(game, 1);
    const now = game.snapshot().score;
    steps.push(now - previous);
    previous = now;
  }
  assert.deepEqual(steps, [1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3]);
  assert.equal(game.snapshot().score, 21);
  assert.equal(game.snapshot().sorts, 12);
  assert.equal(game.snapshot().longestCombo, 12);
});

test('a missort costs one point and clears the combo', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  sortTimes(game, 12);
  assert.equal(game.snapshot().score, 21);
  game.choose(RIGHT, game.snapshot().activePackageId);
  const shot = game.snapshot();
  assert.equal(shot.score, 20);
  assert.equal(shot.combo, 0);
  assert.equal(shot.multiplier, 1);
  assert.equal(shot.missorts, 1);
  // The streak is cleared, but the round's longest streak is kept for rule 18.
  assert.equal(shot.longestCombo, 12);
});

test('the score never falls below zero', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  for (let i = 0; i < 5; i += 1) {
    game.choose(RIGHT, game.snapshot().activePackageId);
    game.tick(16);
  }
  const shot = game.snapshot();
  assert.equal(shot.score, 0, 'a missort at zero leaves zero, not minus one');
  assert.equal(shot.missorts, 5);
});

test('a drop costs the same as a missort and is counted apart from it', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  sortTimes(game, 6);
  const before = game.snapshot();
  assert.equal(before.score, 7);
  assert.ok(before.combo > 0);
  // Let the front package run off the edge without a gesture.
  for (let i = 0; i < 400 && game.snapshot().drops === 0; i += 1) game.tick(MAX_TICK_MS);
  const after = game.snapshot();
  assert.equal(after.drops, 1);
  assert.equal(after.score, before.score - 1);
  assert.equal(after.combo, 0);
  assert.equal(after.missorts, 0, 'a drop is not a missort');
});

// ---------------------------------------------------------------------------
// Rules 2, 7, 8, 9 and 11: one package, one resolution.
// ---------------------------------------------------------------------------

// The belt starts empty and fills from the top, so the queue takes a moment
// to build. Run it until the front package is near the edge: by then the lane
// must hold the packages behind it, or the player has nothing to read ahead.
function fillLane(game) {
  while (game.snapshot().packages[0].progress < 0.9) game.tick(16);
  return game.snapshot();
}

test('only the front package resolves, and only once', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const shot = fillLane(game);
  assert.ok(shot.packages.length >= 3, `the queue must be visible, saw ${shot.packages.length}`);
  assert.equal(shot.packages.filter(item => item.front).length, 1);
  assert.equal(shot.packages[0].id, shot.activePackageId);

  const stale = shot.activePackageId;
  assert.equal(game.choose(LEFT, stale).resolved, true);
  // A rapid second tap for the same package: ignored, not applied to the next.
  const again = game.choose(LEFT, stale);
  assert.equal(again.resolved, false);
  assert.equal(again.reason, 'not-the-front-package');
  assert.equal(game.snapshot().sorts, 1);
});

test('a gesture for a package behind the front one is ignored', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  fillLane(game);
  const behind = game.snapshot().packages[1].id;
  const result = game.choose(LEFT, behind);
  assert.equal(result.resolved, false);
  assert.equal(game.snapshot().sorts, 0);
});

test('a gesture for a package the clock already dropped is ignored', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const doomed = game.snapshot().activePackageId;
  for (let i = 0; i < 400 && game.snapshot().drops === 0; i += 1) game.tick(MAX_TICK_MS);
  const result = game.choose(LEFT, doomed);
  assert.equal(result.resolved, false);
  assert.equal(game.snapshot().sorts, 0);
  assert.equal(game.snapshot().drops, 1);
});

test('the boundary tie resolves by order and never counts twice', () => {
  // A swipe released as the package reaches the edge: whichever call lands
  // first resolves the package, and the other is ignored. Either way the
  // package is counted exactly once.
  const sortFirst = createGame({ questionSource: source(), mode: flat });
  const id = sortFirst.snapshot().activePackageId;
  while (sortFirst.snapshot().packages[0].y < DEFAULT_LANE - 10) sortFirst.tick(16);
  assert.equal(sortFirst.choose(LEFT, id).resolved, true);
  sortFirst.tick(16);
  let shot = sortFirst.snapshot();
  assert.equal(shot.sorts + shot.missorts + shot.drops, 1);

  const dropFirst = createGame({ questionSource: source(), mode: flat });
  const doomed = dropFirst.snapshot().activePackageId;
  while (dropFirst.snapshot().drops === 0) dropFirst.tick(16);
  assert.equal(dropFirst.choose(LEFT, doomed).resolved, false);
  shot = dropFirst.snapshot();
  assert.equal(shot.sorts + shot.missorts + shot.drops, 1);
});

test('the front package keeps its options while it is on the belt', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const first = game.snapshot().packages[0];
  const answer = JSON.stringify(first.route.options);
  for (let i = 0; i < 10; i += 1) {
    game.tick(16);
    const now = game.snapshot().packages.find(item => item.id === first.id);
    if (!now) break;
    assert.equal(JSON.stringify(now.route.options), answer, 'a following package must not change the active answer');
  }
});

test('an unknown side is refused rather than guessed', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  assert.equal(game.choose(7, game.snapshot().activePackageId).reason, 'no-such-side');
  assert.equal(game.snapshot().sorts + game.snapshot().missorts, 0);
});

// ---------------------------------------------------------------------------
// Rule 12 and the clock.
// ---------------------------------------------------------------------------

test('the round ends on the clock, not when packages run out', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  let ticks = 0;
  while (!game.snapshot().ended && ticks < 100000) { game.tick(MAX_TICK_MS); ticks += 1; }
  const shot = game.snapshot();
  assert.equal(shot.ended, true);
  assert.equal(shot.remainingMs, 0);
  assert.equal(shot.elapsedMs, ROUND_MS);
  assert.ok(shot.drops > 0, 'packages kept coming for the whole round');
  // Nothing resolves after the bell.
  assert.equal(game.choose(LEFT, shot.activePackageId).reason, 'round-not-running');
  assert.equal(game.tick(1000).elapsedMs, ROUND_MS);
});

test('motion follows elapsed time, not the number of frames', () => {
  const few = createGame({ questionSource: source(), mode: flat });
  const many = createGame({ questionSource: source(), mode: flat });
  for (let i = 0; i < 10; i += 1) few.tick(100);
  for (let i = 0; i < 100; i += 1) many.tick(10);
  assert.equal(few.snapshot().elapsedMs, many.snapshot().elapsedMs);
  assert.ok(Math.abs(few.snapshot().packages[0].y - many.snapshot().packages[0].y) < 1e-9);
});

test('a long frame is clamped, so a sleeping tab cannot dump the queue', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const shot = game.tick(60000);
  assert.equal(shot.elapsedMs, MAX_TICK_MS);
  assert.equal(shot.drops, 0, 'one long frame must not drop a whole queue');
});

test('a tick of zero or less changes nothing', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const before = JSON.stringify(game.snapshot());
  game.tick(0);
  game.tick(-500);
  assert.equal(JSON.stringify(game.snapshot()), before);
});

test('pause stops the clock and the belt, and resume adds no catch-up', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  fillLane(game);
  const paused = game.pause();
  assert.equal(paused.running, false);
  game.tick(5000);
  game.tick(5000);
  assert.equal(game.snapshot().elapsedMs, paused.elapsedMs, 'a paused round must not advance');
  assert.equal(game.snapshot().packages[0].y, paused.packages[0].y);
  assert.equal(game.choose(LEFT, paused.activePackageId).reason, 'round-not-running');
  const resumed = game.resume();
  assert.equal(resumed.running, true);
  assert.equal(resumed.elapsedMs, paused.elapsedMs);
  assert.equal(resumed.drops, paused.drops, 'nothing may drop at the moment of resuming');
});

test('restart puts everything back, including the clock and the counters', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  sortTimes(game, 7);
  game.choose(RIGHT, game.snapshot().activePackageId);
  game.tick(9000);
  game.restart();
  const shot = game.snapshot();
  for (const key of ['elapsedMs', 'score', 'combo', 'longestCombo', 'sorts', 'missorts', 'drops']) {
    assert.equal(shot[key], 0, `${key} must be back to zero`);
  }
  assert.equal(shot.ended, false);
  assert.equal(shot.running, true);
  assert.equal(shot.remainingMs, ROUND_MS);
  assert.equal(shot.packages.length, 1);
});

// ---------------------------------------------------------------------------
// The Expert curve.
// ---------------------------------------------------------------------------

test('Expert speeds up through the round and hardens its deck partway', () => {
  const source1 = source();
  const game = createGame({ questionSource: source1, mode: expert });
  const opening = game.snapshot().speed;
  let previous = opening;
  while (!game.snapshot().ended) {
    const now = game.tick(MAX_TICK_MS).speed;
    assert.ok(now >= previous - 1e-9, 'Expert speed must never fall');
    previous = now;
  }
  assert.ok(previous > opening, 'Expert must finish faster than it started');
  assert.ok(source1.decks.includes('level-medium') && source1.decks.includes('level-hard'));
  // The deck hardens once and does not flip back.
  const firstHard = source1.decks.indexOf('level-hard');
  assert.ok(firstHard > 0);
  assert.ok(source1.decks.slice(firstHard).every(deck => deck === 'level-hard'));
});

test('a faster belt delivers more packages in the same time', () => {
  const slow = createGame({ questionSource: source(), mode: { speed: () => 42, deck: () => 'd' } });
  const fast = createGame({ questionSource: source(), mode: { speed: () => 120, deck: () => 'd' } });
  for (let i = 0; i < 200; i += 1) { slow.tick(100); fast.tick(100); }
  assert.ok(fast.snapshot().drops > slow.snapshot().drops);
});

// ---------------------------------------------------------------------------
// Rule 18: the summary.
// ---------------------------------------------------------------------------

test('the summary reports what the round actually was', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  sortTimes(game, 3);
  game.choose(RIGHT, game.snapshot().activePackageId);
  game.tick(16);
  while (game.snapshot().drops === 0) game.tick(MAX_TICK_MS);
  const summary = game.summary();
  assert.equal(summary.sorts, 3);
  assert.equal(summary.missorts, 1);
  assert.equal(summary.drops, 1);
  assert.equal(summary.resolved, 5);
  assert.equal(summary.accuracy, 3 / 5);
  assert.equal(summary.longestCombo, 3);
  assert.equal(summary.score, 3 - 1 - 1);
});

test('an untouched round reports zero accuracy rather than dividing by zero', () => {
  const game = createGame({ questionSource: source(), mode: flat });
  const summary = game.summary();
  assert.equal(summary.resolved, 0);
  assert.equal(summary.accuracy, 0);
  assert.ok(Number.isFinite(summary.accuracy));
});

// ---------------------------------------------------------------------------
// The boundary this module promises.
// ---------------------------------------------------------------------------

test('a question source that runs dry stops the queue instead of throwing', () => {
  let left = 2;
  const drying = () => (left-- > 0 ? { id: 'r', options: [{ belt: 'GOLD', correct: true }, { belt: 'BLUE', correct: false }] } : null);
  const game = createGame({ questionSource: drying, mode: flat });
  for (let i = 0; i < 200; i += 1) game.tick(MAX_TICK_MS);
  assert.equal(game.snapshot().packages.length, 0);
  assert.equal(game.snapshot().drops, 2);
  assert.equal(game.choose(LEFT).reason, 'no-package');
});

test('a game cannot be built without its injected pieces', () => {
  assert.throws(() => createGame(), /questionSource/);
  assert.throws(() => createGame({ questionSource: source() }), /mode/);
  assert.throws(() => createGame({ questionSource: source(), mode: { speed: () => 1 } }), /mode/);
  assert.throws(() => createGame({ questionSource: source(), mode: flat, laneLength: 0 }), /laneLength/);
});

test('the module touches no browser API and imports nothing', async () => {
  const text = await (await import('node:fs/promises')).readFile(new URL('../src/conveyor/engine.js', import.meta.url), 'utf8');
  // Strip comments first: the header explains what the module stays away
  // from, and naming a thing is not using it.
  const code = text.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  for (const forbidden of ['document', 'window', 'localStorage', 'sessionStorage', 'AudioContext', 'requestAnimationFrame', 'canvas', 'fetch(', 'Date.now', 'performance.now', 'Math.random']) {
    assert.ok(!code.includes(forbidden), `engine.js must not use ${forbidden}`);
  }
  assert.ok(!/^import /m.test(code), 'engine.js must not import the routing data');
});

test('the queue density follows the lane, not a pixel count', () => {
  const small = createGame({ questionSource: source(), mode: flat, laneLength: 200 });
  const large = createGame({ questionSource: source(), mode: flat, laneLength: 900 });
  const settle = game => { while (game.snapshot().packages[0].progress < 0.9) game.tick(16); return game.snapshot().packages.length; };
  assert.equal(settle(small), settle(large), 'a tall screen must not change how many packages are in sight');
  assert.equal(Math.round(1 / PACKAGE_GAP_RATIO), 3);
});
