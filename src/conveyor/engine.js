// Handler (internal name: conveyor) stage 2 -- the game model.
//
// Clock, motion, scoring and combo, and nothing else. No DOM, no canvas, no
// audio, no storage, no import of the routing data: the packages arrive
// through an injected questionSource, and time arrives through tick(). That
// is what makes rules 1 to 22 testable with a fake clock.
//
// Every number here is an assistant proposal, never measured, which is why
// each one is a named constant for #397 to change after the owner plays.

// Rule 12: the round ends when the clock reaches zero.
export const ROUND_MS = 60000;
// Rule 16: the multiplier rises one step every COMBO_STEP straight sorts and
// stops at COMBO_CAP.
export const COMBO_STEP = 5;
export const COMBO_CAP = 4;
// How far apart packages enter, as a fraction of the lane. A third of the lane
// keeps about three packages in sight, so the player can read the code on the
// package behind the one being sorted -- which is the whole skill the game
// trains. It is a fraction rather than a pixel count so the queue looks the
// same on a phone and on a desktop. At a fixed gap, a faster belt delivers
// more packages per second, which is what makes a mode harder.
//
// How many packages should be in sight is a guess, like the other numbers
// here; #397 decides it after the owner plays.
export const PACKAGE_GAP_RATIO = 1 / 3;
// The lane a package travels, top edge to drop edge, in belt pixels. Stage 3
// passes the measured stage height; this default only keeps the model usable
// on its own.
export const DEFAULT_LANE = 420;
// A tab that was asleep, or a long frame, must not dump the queue over the
// drop edge in one tick. Motion and the clock share this clamp, so a round is
// a minute of played time rather than a minute of wall clock.
export const MAX_TICK_MS = 250;

export function multiplierFor(combo) {
  return Math.min(COMBO_CAP, 1 + Math.floor(combo / COMBO_STEP));
}

// side is 0 for the left option and 1 for the right one, matching the order
// the route's options array already carries.
export const LEFT = 0;
export const RIGHT = 1;

export function createGame({
  questionSource,
  mode,
  laneLength = DEFAULT_LANE,
  roundMs = ROUND_MS,
} = {}) {
  if (typeof questionSource !== 'function') throw new Error('createGame needs a questionSource function');
  if (!mode || typeof mode.speed !== 'function' || typeof mode.deck !== 'function') {
    throw new Error('createGame needs a mode with speed(progress) and deck(progress)');
  }
  if (!(laneLength > 0)) throw new Error('createGame needs a positive laneLength');
  const gap = laneLength * PACKAGE_GAP_RATIO;

  let elapsedMs;
  let running;
  let ended;
  let packages;
  let nextPackageNumber;
  let score;
  let combo;
  let longestCombo;
  let sorts;
  let missorts;
  let drops;

  const progress = () => Math.min(1, elapsedMs / roundMs);
  const speed = () => mode.speed(progress());
  const deck = () => mode.deck(progress());

  function spawn() {
    const route = questionSource(deck());
    if (!route) return false;
    nextPackageNumber += 1;
    // The route id is a chart row and repeats; the package id never does, so a
    // gesture can never resolve a different package that shares a route.
    packages.push({ id: `pkg-${nextPackageNumber}`, route, y: 0 });
    return true;
  }

  // Rule 1: following packages stay visible behind the front one. Keep the
  // lane filled from the top whenever the newest package has moved a gap on.
  function fill() {
    if (ended) return;
    let guard = 0;
    while (guard < 64) {
      const newest = packages[packages.length - 1];
      if (newest && newest.y < gap) break;
      if (!spawn()) break;
      // A fresh package starts behind the one before it rather than at zero,
      // so a long tick cannot stack two packages on the same spot.
      if (packages.length > 1) {
        const previous = packages[packages.length - 2];
        packages[packages.length - 1].y = Math.max(0, previous.y - gap);
      }
      guard += 1;
    }
  }

  function reset() {
    elapsedMs = 0;
    running = true;
    ended = false;
    packages = [];
    nextPackageNumber = 0;
    score = 0;
    combo = 0;
    longestCombo = 0;
    sorts = 0;
    missorts = 0;
    drops = 0;
    fill();
  }

  // Rule 2: only the front package can be sorted. The front one is the one
  // nearest the drop edge, which is the oldest unresolved package.
  const front = () => packages[0] ?? null;

  function sortScored() {
    // Rule 13: the multiplier that applies is the one the streak has already
    // earned, read before this sort extends the streak.
    score += multiplierFor(combo);
    combo += 1;
    if (combo > longestCombo) longestCombo = combo;
    sorts += 1;
  }

  // Rules 14, 15 and 17: a missort and a drop each cost one point and clear
  // the combo, and the score never falls below zero.
  function penalise(kind) {
    score = Math.max(0, score - 1);
    combo = 0;
    if (kind === 'missort') missorts += 1; else drops += 1;
  }

  function endRound() {
    ended = true;
    running = false;
  }

  function tick(deltaMs) {
    if (!running || ended) return snapshot();
    if (!(deltaMs > 0)) return snapshot();
    const step = Math.min(deltaMs, MAX_TICK_MS);
    const before = speed();
    elapsedMs = Math.min(roundMs, elapsedMs + step);
    // Average the speed across the step so an accelerating belt advances the
    // same distance however the frames fall.
    const travelled = ((before + speed()) / 2) * (step / 1000);
    for (const item of packages) item.y += travelled;
    // Rule 10: a package that passes the drop edge is a drop. Resolve from
    // the front, so the counters follow the order the player saw.
    while (packages.length && packages[0].y >= laneLength) {
      packages.shift();
      penalise('drop');
    }
    fill();
    if (elapsedMs >= roundMs) endRound();
    return snapshot();
  }

  // Rules 8, 9 and 11: a sort or a missort resolves the front package exactly
  // once. A gesture naming any other package -- a rapid second tap, a
  // duplicate pointer event, a gesture for a package the clock already
  // dropped -- is ignored rather than applied to its neighbour.
  function choose(side, packageId) {
    if (!running || ended) return { resolved: false, reason: 'round-not-running' };
    const active = front();
    if (!active) return { resolved: false, reason: 'no-package' };
    if (packageId !== undefined && packageId !== active.id) return { resolved: false, reason: 'not-the-front-package' };
    const option = active.route.options?.[side];
    if (!option) return { resolved: false, reason: 'no-such-side' };
    packages.shift();
    if (option.correct) sortScored(); else penalise('missort');
    fill();
    return { resolved: true, outcome: option.correct ? 'sorted' : 'missort', packageId: active.id, belt: option.belt };
  }

  function pause() {
    if (!ended) running = false;
    return snapshot();
  }

  function resume() {
    // Resuming adds no time, so nothing catches up and nothing drops at once.
    if (!ended) running = true;
    return snapshot();
  }

  function snapshot() {
    const activeId = front()?.id ?? null;
    return {
      elapsedMs,
      remainingMs: Math.max(0, roundMs - elapsedMs),
      progress: progress(),
      running,
      ended,
      speed: speed(),
      deck: deck(),
      score,
      combo,
      multiplier: multiplierFor(combo),
      longestCombo,
      sorts,
      missorts,
      drops,
      activePackageId: activeId,
      packages: packages.map(item => ({
        id: item.id,
        y: item.y,
        progress: item.y / laneLength,
        route: item.route,
        front: item.id === activeId,
      })),
    };
  }

  // Rule 18: what the end-of-round screen shows.
  function summary() {
    const resolved = sorts + missorts + drops;
    return {
      score,
      sorts,
      missorts,
      drops,
      resolved,
      accuracy: resolved ? sorts / resolved : 0,
      longestCombo,
      ended,
    };
  }

  reset();
  return { tick, choose, pause, resume, restart: reset, snapshot, summary };
}
