import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const bank = JSON.parse(await readFile(new URL('../backend/data/ranked/routes-v1.json', import.meta.url)));
const { modules: [routes, chart, { BELTS }], cleanup } = await loadAppModules([
  'src/conveyor/routes.js', 'src/chart.js', 'src/belts.js',
]);
after(cleanup);
const { CHART } = chart;
const {
  MODES, MODE_ORDER, SERVICE_NAMES, EXPERT_DECK_SWITCH,
  drawRoute, modeDecks, parseRange, routePool, shadowedPrefixes,
} = routes;

const spread = ({ from, to }) => Array.from({ length: to - from + 1 }, (unused, index) => from + index);
const sorted = values => [...values].sort((left, right) => left - right);

// A seeded generator, so a failure names one sequence instead of a mood.
function seeded(seed) {
  let state = seed >>> 0;
  return () => {
    state = (state * 1664525 + 1013904223) >>> 0;
    return state / 4294967296;
  };
}

// ---------------------------------------------------------------------------
// The excluded prefixes are the owner's, not the adapter's.
//
// backend/data/ranked/routes-v1.json is the reviewed Ranked bank: each main
// row that an exception cuts into carries exclusion_refs naming the exception
// rows. The adapter never reads that file -- it derives the same set from
// src/chart.js, which the browser already has. These two tests assert the two
// derivations agree in both directions, so correcting one side and forgetting
// the other fails here instead of teaching a player the wrong belt.
// ---------------------------------------------------------------------------

const byReviewRef = new Map();
for (const question of bank.questions) {
  const ref = question.source.review_ref;
  if (!byReviewRef.has(ref)) byReviewRef.set(ref, []);
  byReviewRef.get(ref).push(question);
}

function bankShadow(question) {
  const shadow = new Set();
  for (const ref of question.exclusion_refs) {
    const referenced = byReviewRef.get(ref);
    assert.ok(referenced?.length, `exclusion_refs names ${ref}, which the bank does not contain`);
    for (const row of referenced) {
      const range = parseRange(row.source.code_label);
      if (range) {
        for (const prefix of spread(range)) shadow.add(prefix);
        continue;
      }
      const prefix = Number(String(row.source.code_label).trim().slice(0, 3));
      assert.ok(Number.isInteger(prefix), `cannot read a prefix from ${row.source.code_label}`);
      shadow.add(prefix);
    }
  }
  return shadow;
}

const bankRangeRows = bank.questions
  .filter(question => question.source.row_kind === 'main' && parseRange(question.source.code_label))
  .map(question => ({
    service: SERVICE_NAMES[question.context.service],
    state: question.source.state_label,
    code: question.source.code_label,
    range: parseRange(question.source.code_label),
    shadow: bankShadow(question),
  }));

// The one chart range row Handler never draws from: NJ 070-089 routes to
// CHECK, which cardsFromChart filters out of every deck and the Ranked bank
// omits for the same reason. Naming it here keeps the comparison strict -- if
// any OTHER row stops being reviewed, this test fails instead of shrugging.
const UNPLAYED = Object.keys(CHART).map(service => `${service} NJ 070\u2013089`);

test('the bank still describes every chart range row Handler can draw', () => {
  const chartRows = Object.keys(CHART).flatMap(service => CHART[service].main
    .filter(row => parseRange(row[1]))
    .map(row => `${service} ${row[0]} ${row[1]}`));
  const banked = bankRangeRows.map(row => `${row.service} ${row.state} ${row.code}`);
  assert.deepEqual(chartRows.filter(row => !banked.includes(row)).sort(), [...UNPLAYED].sort());
  assert.deepEqual(banked.filter(row => !chartRows.includes(row)).sort(), []);
  assert.equal(banked.length + UNPLAYED.length, chartRows.length);
});

for (const row of bankRangeRows) {
  test(`${row.service} ${row.code}: derived exclusions match the reviewed bank`, () => {
    const derived = shadowedPrefixes(row.service);
    const inside = spread(row.range).filter(prefix => derived.has(prefix));
    assert.deepEqual(sorted(inside), sorted(row.shadow));
  });
}

// ---------------------------------------------------------------------------
// What the label says.
// ---------------------------------------------------------------------------

test('the owner-named traps never come out of the range they are cut from', () => {
  const ground = routePool('level-hard').filter(entry => entry.service === 'Ground');
  const brown = ground.find(entry => entry.card.code === '370–385');
  assert.ok(brown, 'the TN 370-385 row is missing from the Hard pool');
  for (const trap of ['376', '377', '378']) assert.ok(!brown.labels.includes(trap), `${trap} must not come from the BROWN range`);
  assert.ok(brown.labels.includes('375') && brown.labels.includes('379'));

  // 575 turns on a fourth digit the label would not show, so the range drops
  // it; the exception row carries it instead, as "575 3-6".
  const wide = ground.find(entry => entry.card.code === '498–589');
  assert.ok(!wide.labels.includes('575'));
  assert.ok(ground.some(entry => entry.labels.includes('575 3-6')));
});

test('no drawn label is a range, and nothing invents a five-digit ZIP', () => {
  for (const deck of ['level-basic', 'level-medium', 'level-hard']) {
    for (const entry of routePool(deck)) {
      for (const label of entry.labels) {
        assert.ok(!/^\d{3}\s*[–-]\s*\d{3}$/.test(label), `${deck} offers the range ${label}`);
        assert.ok(!/^\d{5}$/.test(label), `${deck} offers the fabricated ZIP ${label}`);
      }
    }
  }
});

test('a range card draws a prefix and keeps the chart answer', () => {
  const pool = routePool('level-hard');
  const rand = seeded(7);
  for (let round = 0; round < 4000; round += 1) {
    const route = drawRoute(pool, rand);
    const section = CHART[route.service];
    const row = [...section.main, ...section.exceptions]
      .find(([state, code]) => code === route.chartCode && (state === route.state || (state === '*' && route.state === 'All states')));
    assert.ok(row, `${route.service} ${route.chartCode} is not a chart row`);
    assert.equal(route.belt, row[2]);
    const range = parseRange(route.chartCode);
    if (range) {
      assert.match(route.code, /^\d{3}$/);
      const prefix = Number(route.code);
      assert.ok(prefix >= range.from && prefix <= range.to);
      assert.ok(!shadowedPrefixes(route.service).has(prefix));
    } else {
      assert.equal(route.code, String(route.chartCode).trim());
    }
  }
});

// ---------------------------------------------------------------------------
// The two belts offered.
// ---------------------------------------------------------------------------

test('every package offers one correct belt and one real wrong belt', () => {
  const pool = routePool('level-hard');
  const rand = seeded(11);
  const sides = new Set();
  for (let round = 0; round < 4000; round += 1) {
    const route = drawRoute(pool, rand);
    assert.equal(route.options.length, 2);
    const correct = route.options.filter(option => option.correct);
    assert.equal(correct.length, 1);
    assert.equal(correct[0].belt, route.belt);
    const wrong = route.options.find(option => !option.correct);
    assert.notEqual(wrong.belt, route.belt);
    assert.notEqual(wrong.belt, 'CHECK');
    assert.ok(BELTS.includes(wrong.belt));
    sides.add(route.options[0].correct);
  }
  // The answer must not settle on one side; that would be a free point.
  assert.deepEqual(sorted([...sides].map(Number)), [0, 1]);
});

test('the same seed draws the same round', () => {
  const pool = routePool('level-hard');
  const once = Array.from({ length: 50 }, () => 0);
  const read = seed => { const rand = seeded(seed); return once.map(() => JSON.stringify(drawRoute(pool, rand))); };
  assert.deepEqual(read(3), read(3));
  assert.notDeepEqual(read(3), read(4));
});

// ---------------------------------------------------------------------------
// The four modes.
// ---------------------------------------------------------------------------

test('each mode draws from an existing deck and offers real variety', () => {
  const counts = new Map();
  for (const mode of MODE_ORDER) {
    const labels = new Set();
    for (const deck of modeDecks(mode)) {
      for (const entry of routePool(deck)) {
        for (const label of entry.labels) labels.add(`${entry.card.svc} ${label}`);
      }
    }
    counts.set(mode, labels.size);
  }
  // A round must not run out of distinct packages.
  assert.ok(counts.get('easy') > 200, `easy offers only ${counts.get('easy')} labels`);
  assert.ok(counts.get('hard') > 3000, `hard offers only ${counts.get('hard')} labels`);
  assert.ok(counts.get('hard') > counts.get('medium'));
  assert.ok(counts.get('medium') > counts.get('easy'));
});

test('Expert opens at Hard speed, keeps climbing, and hardens its deck', () => {
  assert.equal(MODES.expert.speed(0), MODES.hard.speed(0));
  let previous = -Infinity;
  for (let step = 0; step <= 10; step += 1) {
    const speed = MODES.expert.speed(step / 10);
    assert.ok(speed >= previous, 'Expert speed must never fall');
    previous = speed;
  }
  assert.ok(MODES.expert.speed(1) > MODES.expert.speed(0));
  assert.equal(MODES.expert.deck(0), 'level-medium');
  assert.equal(MODES.expert.deck(EXPERT_DECK_SWITCH), 'level-hard');
  assert.equal(MODES.expert.deck(1), 'level-hard');
  assert.deepEqual(modeDecks('expert'), ['level-medium', 'level-hard']);
});

test('the other three modes hold one speed and one deck', () => {
  for (const mode of ['easy', 'medium', 'hard']) {
    assert.equal(MODES[mode].speed(0), MODES[mode].speed(1));
    assert.equal(modeDecks(mode).length, 1);
  }
  assert.ok(MODES.easy.speed(0) < MODES.medium.speed(0));
  assert.ok(MODES.medium.speed(0) < MODES.hard.speed(0));
});

test('an unknown mode or deck is refused, not guessed', () => {
  assert.throws(() => modeDecks('nightmare'), /Unknown mode/);
  assert.throws(() => routePool('level-nightmare'), /Unknown deck/);
  assert.throws(() => drawRoute([]), /Empty route pool/);
});
