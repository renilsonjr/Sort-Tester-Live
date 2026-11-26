// What accuracy does each Handler combo tier actually ask for? (#397)
//
// The combo step, the ceiling and the per-mode speeds are assistant guesses
// that the owner tunes after playing. This does not decide them. It plays a
// full round in every mode at several miss rates, with the
// engine's real clock and the real decks, and prints what each setting costs
// -- so a change to a constant can be judged by its effect, not by feel
// alone. Run it again after changing any of them:
//
//   node tools/handler-tiers.mjs
import { cp, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { pathToFileURL } from 'node:url';

// The browser modules carry cache-busting query strings in their imports, so
// they are loaded from a scratch copy the way the tests load them.
const directory = await mkdtemp(join(tmpdir(), 'handler-tiers-'));
await cp(new URL('../src/', import.meta.url), join(directory, 'src'), { recursive: true });
await writeFile(join(directory, 'package.json'), '{"type":"module"}\n');
const load = path => import(pathToFileURL(join(directory, path)).href);
const [engine, routes] = await Promise.all([load('src/conveyor/engine.js'), load('src/conveyor/routes.js')]);
const { createGame, LEFT, RIGHT, COMBO_STEP, COMBO_CAP, ROUND_MS } = engine;

const seeded = seed => () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;

function run(mode, missEvery, seed = 7) {
  const rand = seeded(seed);
  const pools = new Map();
  const pool = deck => { if (!pools.has(deck)) pools.set(deck, routes.routePool(deck)); return pools.get(deck); };
  const game = createGame({ mode: routes.MODES[mode], laneLength: 560,
    questionSource: deck => routes.drawRoute(pool(deck), rand) });
  let decisions = 0;
  while (!game.snapshot().ended) {
    const front = game.snapshot().packages.find(item => item.front);
    // The player answers once the package is far enough down to have been read.
    if (front && front.progress > 0.45) {
      decisions += 1;
      const correct = front.route.options.findIndex(option => option.correct);
      const miss = missEvery && decisions % missEvery === 0;
      game.choose(miss ? (correct === 0 ? RIGHT : LEFT) : (correct === 0 ? LEFT : RIGHT), front.id);
    }
    game.tick(16);
  }
  const summary = game.summary();
  return { ...summary, tier: Math.min(COMBO_CAP, 1 + Math.floor(summary.longestCombo / COMBO_STEP)) };
}

const rates = [[0, 'perfect'], [50, '1 in 50'], [25, '1 in 25'], [15, '1 in 15'], [10, '1 in 10'], [7, '1 in 7'], [4, '1 in 4']];
console.log(`Round ${ROUND_MS / 1000}s. Step ${COMBO_STEP}, ceiling x${COMBO_CAP}: `
  + Array.from({ length: COMBO_CAP - 1 }, (unused, i) => `x${i + 2} needs ${COMBO_STEP * (i + 1)} straight`).join(', ') + '.\n');
console.log('mode     wrong       packages  best streak  tier  score');
for (const mode of routes.MODE_ORDER) {
  for (const [every, label] of rates) {
    const result = run(mode, every);
    console.log(`${mode.padEnd(8)} ${label.padEnd(11)} ${String(result.resolved).padStart(8)} `
      + `${String(result.longestCombo).padStart(12)} ${('x' + result.tier).padStart(5)} ${String(result.score).padStart(6)}`);
  }
  console.log('');
}
console.log('Speeds (px/s at the start -> at the end of the round), on a 560px lane:');
for (const mode of routes.MODE_ORDER) {
  const open = routes.MODES[mode].speed(0);
  const close = routes.MODES[mode].speed(1);
  console.log(`  ${mode.padEnd(7)} ${open.toFixed(0)} -> ${close.toFixed(0)}   a package crosses in `
    + `${(560 / open).toFixed(1)}s -> ${(560 / close).toFixed(1)}s, one arrives every `
    + `${(560 * engine.PACKAGE_GAP_RATIO / open).toFixed(1)}s -> ${(560 * engine.PACKAGE_GAP_RATIO / close).toFixed(1)}s`);
}
await rm(directory, { recursive: true, force: true });
