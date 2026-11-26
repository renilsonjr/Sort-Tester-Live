import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

// #397: "Reconcile a controlled two-minute run by hand."
//
// These tests do not ask the engine what the score was. They record every
// event a full round produces and recompute the score, the streak and the
// three counters independently, from the rules as the spec words them, then
// compare event by event. They matter most AFTER the owner tunes the combo
// numbers: the recomputation reads the step and the ceiling but none of the
// engine's arithmetic, so a tuning change that breaks a rule fails here.
const { modules: [engine, routes, chart, belts], cleanup } = await loadAppModules([
  'src/conveyor/engine.js', 'src/conveyor/routes.js', 'src/chart.js', 'src/belts.js',
]);
after(cleanup);
const { createGame, LEFT, RIGHT, ROUND_MS, COMBO_STEP, COMBO_CAP } = engine;

function seeded(seed) {
  let state = seed >>> 0;
  return () => { state = (state * 1664525 + 1013904223) >>> 0; return state / 4294967296; };
}

// A deterministic player: mostly right, wrong every missEvery-th decision,
// and asleep on every sleepEvery-th package, which then runs off the end.
function play(mode, { seed = 2026, tickMs = 16, missEvery = 7, sleepEvery = 23 } = {}) {
  const rand = seeded(seed);
  const pools = new Map();
  const pool = deck => {
    if (!pools.has(deck)) pools.set(deck, routes.routePool(deck));
    return pools.get(deck);
  };
  const game = createGame({
    mode: routes.MODES[mode],
    laneLength: 560,
    questionSource: deck => routes.drawRoute(pool(deck), rand),
  });
  const events = [];
  // A skipped package has to stay skipped, or the next frame answers it and
  // nothing ever falls. The first draft of this missed that and reconciled a
  // round with no drops in it at all.
  const ignored = new Set();
  let decisions = 0;
  while (!game.snapshot().ended) {
    const before = game.snapshot();
    const front = before.packages.find(item => item.front);
    if (front && front.progress > 0.45) {
      if (!ignored.has(front.id)) {
        decisions += 1;
        if (decisions % sleepEvery === 0) ignored.add(front.id);
      }
      if (!ignored.has(front.id)) {
        const correct = front.route.options.findIndex(option => option.correct);
        const wrong = correct === 0 ? RIGHT : LEFT;
        const side = decisions % missEvery === 0 ? wrong : (correct === 0 ? LEFT : RIGHT);
        const result = game.choose(side, front.id);
        if (result.resolved) {
          events.push({ kind: result.outcome === 'sorted' ? 'sort' : 'missort',
            engineDelta: game.snapshot().score - before.score });
        }
      }
    }
    const mid = game.snapshot();
    const afterTick = game.tick(tickMs);
    if (afterTick.drops > mid.drops) {
      events.push({ kind: 'drop', engineDelta: afterTick.score - mid.score });
    }
  }
  return { game, events };
}

// Rules 13 to 17, written out again rather than imported.
function byHand(events) {
  let score = 0, combo = 0, longest = 0, sorts = 0, missorts = 0, drops = 0;
  const disagreements = [];
  events.forEach((event, index) => {
    let delta;
    if (event.kind === 'sort') {
      delta = Math.min(COMBO_CAP, 1 + Math.floor(combo / COMBO_STEP));
      score += delta;
      combo += 1;
      longest = Math.max(longest, combo);
      sorts += 1;
    } else {
      const floored = Math.max(0, score - 1);
      delta = floored - score;
      score = floored;
      combo = 0;
      if (event.kind === 'missort') missorts += 1; else drops += 1;
    }
    if (delta !== event.engineDelta) disagreements.push({ index, kind: event.kind, engine: event.engineDelta, byHand: delta });
  });
  const resolved = sorts + missorts + drops;
  return { score, longest, sorts, missorts, drops, resolved, accuracy: resolved ? sorts / resolved : 0, disagreements };
}

for (const mode of routes.MODE_ORDER) {
  test(`a full two-minute ${mode} round reconciles event by event`, () => {
    const { game, events } = play(mode);
    const hand = byHand(events);
    const summary = game.summary();
    assert.deepEqual(hand.disagreements, [], 'the engine and the rules parted at these events');
    assert.equal(summary.score, hand.score);
    assert.equal(summary.sorts, hand.sorts);
    assert.equal(summary.missorts, hand.missorts);
    assert.equal(summary.drops, hand.drops);
    assert.equal(summary.resolved, hand.resolved);
    assert.equal(summary.longestCombo, hand.longest);
    assert.ok(Math.abs(summary.accuracy - hand.accuracy) < 1e-12);
    // The round must contain all three outcomes, or it reconciled nothing.
    assert.ok(hand.sorts > 0 && hand.missorts > 0 && hand.drops > 0,
      `a ${mode} round with no ${hand.drops ? 'missort' : 'drop'} in it proves less than it claims`);
    assert.equal(game.snapshot().elapsedMs, ROUND_MS, 'the round ends on the clock');
  });
}

test('a round at zero cannot be driven below it', () => {
  // Every decision wrong: the floor is hit at once and has to hold all round.
  const { game, events } = play('hard', { missEvery: 1, sleepEvery: 5 });
  const hand = byHand(events);
  assert.deepEqual(hand.disagreements, []);
  assert.equal(game.summary().score, 0);
  assert.ok(events.every(event => event.engineDelta === 0), 'a penalty at zero costs nothing more');
});

// #397: "Verify every supported service and code sample offers exactly one
// correct destination and one wrong one." Exhaustive, not a sample: every
// card in every deck, checked against the chart row it came from.
test('every card in every deck offers one correct belt and real wrong ones', () => {
  let cards = 0;
  let labels = 0;
  for (const deck of ['level-basic', 'level-medium', 'level-hard']) {
    for (const entry of routes.routePool(deck)) {
      cards += 1;
      labels += entry.labels.length;
      const where = `${deck} ${entry.card.id}`;
      const { belt, confusions } = entry.card;
      assert.ok(belts.BELTS.includes(belt) && belt !== 'CHECK', `${where}: ${belt} is not a destination`);
      assert.ok(confusions.length > 0, `${where}: no wrong belt to offer`);
      assert.ok(!confusions.includes(belt), `${where}: the right belt is also offered as wrong`);
      assert.ok(!confusions.includes('CHECK'), `${where}: CHECK offered as a destination`);
      const section = chart.CHART[entry.service];
      const row = [...section.main, ...section.exceptions].find(([state, code]) =>
        code === entry.card.code && (state === entry.card.state || (state === '*' && entry.card.state === 'All states')));
      assert.ok(row, `${where}: ${entry.card.code} is not a chart row`);
      assert.equal(row[2], belt, `${where}: the chart and the card disagree`);
    }
  }
  assert.ok(cards > 400 && labels > 8000, `only ${cards} cards and ${labels} labels were checked`);
});

test('the correct belt does not settle on one side', () => {
  const pool = routes.routePool('level-hard');
  const rand = seeded(99);
  let left = 0;
  const draws = 20000;
  for (let i = 0; i < draws; i += 1) if (routes.drawRoute(pool, rand).options[0].correct) left += 1;
  const share = left / draws;
  assert.ok(share > 0.47 && share < 0.53, `the correct belt was on the left ${(share * 100).toFixed(1)}% of the time`);
});
