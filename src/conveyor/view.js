// Handler (internal name: conveyor) stage 3 -- the screen and the input.
//
// This layer draws the engine's snapshot and turns gestures into choose()
// calls. It never decides a route and it never scores: if a number on screen
// disagrees with the engine, the engine is right and this file is wrong.
//
// Rules 19, 20 and 21 live here. Two of them are corrections the owner made
// while playing the prototype, and both are easy to undo by accident:
//
//   * The combo effect is a SPARKLE, not a flame. An earlier version set the
//     package and the belt on fire and the owner rejected it.
//   * The combo badge sits OFF TO THE RIGHT and never over the lane. A centred
//     badge covered the code on the package coming down, and reading that code
//     early is the whole skill the game trains.
import { BELT_STYLE } from './../belts.js';
import { SERVICE_LABEL } from './../questions.js?v=chart-destination-20261108-r2';

// Rule 19: icy cyan, chosen to sit far from the BLUE belt's navy (#1f4e9c) so
// a glow around a package can never be read as a routing colour.
export const SPARK_RGB = '150,226,255';
// Rule 20: the verdict is a colour AND a glyph, always together. Red and
// green alone fail red-green colour blindness, and a player with the sound
// off would otherwise have no verdict at all.
export const VERDICT = {
  sorted: { rgb: '74,222,128', glyph: '✓' },
  missort: { rgb: '248,113,113', glyph: '✗' },
  dropped: { rgb: '248,113,113', glyph: '✗' },
};
// A dropped package takes this long to fall past the end of the belt.
export const DEPART_S = 0.55;
// A sorted or missorted package does NOT hold: it leaves in one motion, at
// the speed the finger was already moving, wearing its verdict as it goes
// (owner correction after playing on an iPhone, 2026-11-26: the old hold read
// as the box sticking under the thumb). FLING_MIN is the speed a tap on a
// destination or an arrow key leaves at; FLING_MAX stops a wild flick from
// taking the box away before the colour can be seen.
export const FLING_S = 0.3;
export const FLING_MIN = 900;
export const FLING_MAX = 2400;
export const FLING_ACCEL = 3000;
// The box leans this much per pixel dragged, and keeps that lean as it leaves.
export const LEAN = 0.0012;
// Losing the streak scatters the stars outward and they wink out. Under half
// a second, and no screen-wide flash.
export const BURST_S = 0.42;
// A gesture counts as a swipe past this much travel, in pixels.
export const SWIPE_MIN = 52;
// Handler has a skin of its own and stays dark in both app themes (owner
// decision, 2026-11-26). It is a game inside the app, not another app screen,
// and the look is the one the owner approved on the prototype. These are the
// prototype's colours, kept here rather than in index.html because the canvas
// cannot read a token.
export const SKIN = {
  room: '#2a1b15',
  roomLine: '#3d2a1e',
  frameOuter: '#7a5536',
  frameOuterLine: '#996c45',
  frameInner: '#241610',
  belt: '#43301f',
  slatDark: '#32231a',
  slatLight: '#64462e',
  guide: '#9b7247',
  edge: '#c49a62',
  edgeTeeth: '#38261a',
  boxFace: '#c79454',
  boxFaceIdle: '#a98351',
  boxLine: '#6b4527',
  boxTape: '#e5b674',
  boxTapeCentre: '#e9c68a',
  boxTapeLine: '#b68d54',
  label: '#fffaf0',
  labelIdle: '#eadfc9',
  labelInk: '#2b1d14',
  labelSoft: '#7a6450',
  labelFaint: '#897260',
  barcode: '#38261a',
  ink: '#c7a988',
};

// Rule 19, the owner's correction, enforced by geometry rather than by eye.
// The badge keeps a column on the right, and the belt is narrow and centred --
// which is what makes room for the side destinations AND the badge at once.
// Measured on a 375px phone, a badge merely pinned to the right edge sat 15px
// over the lane, so "put it on the right" is not enough on its own.
export const BADGE_GUTTER = 72;
export const FRAME_PAD = 18;

export function stageLayout(width) {
  // Centred, like the prototype. The third term is what keeps the frame clear
  // of the badge's column on a narrow phone: the belt gives up width before
  // the badge gives up its place.
  const beltW = Math.max(96, Math.min(300, width * 0.47, width - 2 * FRAME_PAD - 2 * BADGE_GUTTER));
  const centre = width / 2;
  const packW = Math.min(195, beltW * 0.9);
  return {
    centre,
    beltW,
    beltLeft: centre - beltW / 2,
    beltRight: centre + beltW / 2,
    frameLeft: centre - beltW / 2 - FRAME_PAD,
    frameRight: centre + beltW / 2 + FRAME_PAD,
    packW,
    packH: packW * 0.69,
    packLeft: centre - packW / 2,
    packRight: centre + packW / 2,
    badgeLeft: width - BADGE_GUTTER,
  };
}

export function formatClock(ms) {
  const total = Math.max(0, Math.ceil(ms / 1000));
  return `${Math.floor(total / 60)}:${String(total % 60).padStart(2, '0')}`;
}

// How loud the sparkle ring is, from the streak alone. Below the first tier
// there is no ring at all: the effect has to mean something.
export function sparkleSpec(combo, step = 5, cap = 4) {
  const tier = Math.min(cap, 1 + Math.floor(combo / step));
  if (tier < 2) return { tier, count: 0, intensity: 0 };
  const intensity = Math.min(1, (tier - 1) / (cap - 1));
  return { tier, count: 3 + Math.round(9 * intensity), intensity };
}

const ROUND_RECT = (ctx, x, y, w, h, r) => {
  ctx.beginPath();
  if (typeof ctx.roundRect === 'function') { ctx.roundRect(x, y, w, h, r); return; }
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
};

const esc = value => String(value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

function memoryBest() {
  const held = new Map();
  return { get: mode => held.get(mode) ?? 0, set: (mode, score) => held.set(mode, score) };
}

export function createHandlerScreen({
  root,
  t = source => source,
  engine,
  routes,
  audio = null,
  // Rule 21: Handler follows the app's own sound preference rather than
  // keeping a second one, so the header switch silences the game too.
  soundPref = { isEnabled: () => true, toggle: () => true },
  bestScores = memoryBest(),
  // The leaderboard's read (#417) and the app's own way of drawing a
  // player's chosen icon. Without a board the button is simply not offered.
  board = null,
  avatarOf = () => '',
  random = Math.random,
  reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches,
} = {}) {
  if (!root) throw new Error('createHandlerScreen needs a root element');
  if (!engine?.createGame) throw new Error('createHandlerScreen needs the engine module');
  if (!routes?.MODES) throw new Error('createHandlerScreen needs the routes module');

  const { createGame, COMBO_STEP, COMBO_CAP, LEFT, RIGHT } = engine;
  const { MODES, MODE_ORDER, routePool, drawRoute } = routes;

  const DECK_LABEL = {
    'level-basic': 'BASIC SORT',
    'level-medium': 'MEDIUM SORT',
    'level-hard': 'HARD SORT',
  };

  const MODE_COPY = {
    easy: ['Easy', 'A slow belt and the Basic routes'],
    medium: ['Medium', 'A normal belt and the Medium routes'],
    hard: ['Hard', 'A fast belt and the full chart'],
    expert: ['Expert', 'Opens fast, keeps speeding up, and the routes harden'],
  };

  let game = null;
  let mode = null;
  let frame = null;
  let last = null;
  let countdown = null;
  let countdownTimer = null;
  let departing = [];
  let bursts = [];
  let drag = null;
  let shownTier = 1;
  let observer = null;
  let canvas = null;
  let ctx = null;
  let size = { w: 0, h: 0 };
  const pools = new Map();
  const listeners = [];

  const on = (target, type, handler, options) => {
    target.addEventListener(type, handler, options);
    listeners.push(() => target.removeEventListener(type, handler, options));
  };

  const poolFor = deck => {
    if (!pools.has(deck)) pools.set(deck, routePool(deck));
    return pools.get(deck);
  };

  // ------------------------------------------------------------------ screens

  function say(message) {
    const live = root.querySelector('[data-hd-live]');
    if (live) live.textContent = message;
  }

  function showModes() {
    stopLoop();
    audio?.stop();
    root.innerHTML = `
      <section class="hd hd-modes" aria-labelledby="hd-modes-title">
        <p class="hd-eyebrow">${esc(t('Two minutes on the belt'))}</p>
        <h2 id="hd-modes-title" class="hd-title">${esc(t('Handler'))}</h2>
        <p class="hd-lede">${esc(t('Send each package to the right belt before it runs off the end.'))}</p>
        <ul class="hd-mode-list">
          ${MODE_ORDER.map(key => `
            <li><button type="button" class="hd-mode" data-hd-mode="${esc(key)}">
              <span class="hd-mode-name">${esc(t(MODE_COPY[key][0]))}</span>
              <span class="hd-mode-blurb">${esc(t(MODE_COPY[key][1]))}</span>
              <span class="hd-mode-best">${esc(t('Your best'))}: <strong>${bestScores.get(key)}</strong></span>
            </button></li>`).join('')}
        </ul>
        ${board ? `<button type="button" class="hd-board-open" data-hd-board-open>${esc(t('Handler leaderboard'))}</button>` : ''}
        <div class="hd-rules">
          <h3>${esc(t('How it scores'))}</h3>
          <ul>
            <li>${esc(t('A round lasts two minutes. It ends on the clock, not when packages run out.'))}</li>
            <li>${esc(t('Right belt: one point, times your streak multiplier.'))}</li>
            <li>${esc(t('Wrong belt, or a package that runs off the end: one point off, and the streak resets.'))}</li>
            <li>${esc(t('The multiplier rises every {step} in a row and stops at x{cap}. Your score never goes below zero.', { step: COMBO_STEP, cap: COMBO_CAP }))}</li>
            <li>${esc(t('Each mode keeps its own best score. Scores from different modes are not compared.'))}</li>
          </ul>
        </div>
        <p class="sr-only" data-hd-live role="status" aria-live="polite"></p>
      </section>`;
    for (const button of root.querySelectorAll('[data-hd-mode]')) {
      on(button, 'click', () => startCountdown(button.dataset.hdMode));
    }
    const open = root.querySelector('[data-hd-board-open]');
    if (open) on(open, 'click', () => showBoard(mode ?? MODE_ORDER[0]));
  }

  // The leaderboard (#417). One board per mode, never a combined one, and
  // titled so nobody reads it as Ranked standing: it says Handler and it
  // names the season. The frame is drawn at once and the rows arrive into
  // it, so changing mode never blanks the screen.
  let boardRequest = 0;
  function showBoard(which) {
    stopLoop();
    audio?.stop();
    root.innerHTML = `
      <section class="hd hd-board" aria-labelledby="hd-board-title">
        <p class="hd-eyebrow" data-hd-board-season>${esc(t('Handler'))}</p>
        <h2 id="hd-board-title" class="hd-title">${esc(t('Handler leaderboard'))}</h2>
        <div class="hd-board-tabs" role="group" aria-label="${esc(t('Mode'))}">
          ${MODE_ORDER.map(key => `
            <button type="button" class="hd-board-tab" data-hd-board-mode="${esc(key)}" aria-pressed="false">${esc(t(MODE_COPY[key][0]))}</button>`).join('')}
        </div>
        <p class="hd-board-note" data-hd-board-note></p>
        <ol class="hd-board-rows" data-hd-board-rows></ol>
        <p class="hd-board-you" data-hd-board-you hidden></p>
        <button type="button" class="hd-back" data-hd-back>${esc(t('Back to modes'))}</button>
        <p class="sr-only" data-hd-live role="status" aria-live="polite"></p>
      </section>`;
    for (const tab of root.querySelectorAll('[data-hd-board-mode]')) {
      on(tab, 'click', () => loadBoard(tab.dataset.hdBoardMode));
    }
    on(root.querySelector('[data-hd-back]'), 'click', showModes);
    loadBoard(which);
  }

  async function loadBoard(which) {
    const request = boardRequest += 1;
    for (const tab of root.querySelectorAll('[data-hd-board-mode]')) {
      tab.setAttribute('aria-pressed', String(tab.dataset.hdBoardMode === which));
    }
    const note = root.querySelector('[data-hd-board-note]');
    const list = root.querySelector('[data-hd-board-rows]');
    const you = root.querySelector('[data-hd-board-you]');
    if (!note || !list || !you) return;
    list.setAttribute('aria-busy', 'true');
    const answer = await board.load(which);
    // A slower answer for a mode the player has already left is dropped, and
    // so is one that arrives after the screen has moved on.
    if (request !== boardRequest || !root.contains(list)) return;
    list.removeAttribute('aria-busy');
    you.hidden = true;
    if (answer.state !== 'ok') {
      list.innerHTML = '';
      note.textContent = answer.state === 'guest'
        ? t('Sign in to see the Handler leaderboard.')
        : t('The leaderboard could not be loaded. Try again in a moment.');
      say(note.textContent);
      return;
    }
    const season = root.querySelector('[data-hd-board-season]');
    if (season && answer.seasonLabel) season.textContent = `${t('Handler')} · ${answer.seasonLabel}`;
    const modeName = t(MODE_COPY[which][0]);
    note.textContent = answer.rows.length === 0
      ? t('Nobody has scored in {mode} this season yet.', { mode: modeName })
      : answer.open
        ? t('Best two-minute score in {mode} this season.', { mode: modeName })
        : t('The season is over. This is how {mode} finished.', { mode: modeName });
    list.innerHTML = answer.rows.map(row => {
      const icon = avatarOf(row.avatar);
      return `
        <li class="hd-board-row${row.you ? ' you' : ''}">
          <span class="hd-board-place">${row.place}${row.tied ? '<abbr title="' + esc(t('Tied')) + '">=</abbr>' : ''}</span>
          <span class="hd-board-icon" aria-hidden="true">${icon || esc(String(row.username).slice(0, 1).toUpperCase())}</span>
          <span class="hd-board-name">${esc(row.username)}<small>#${esc(row.tag)}</small>${row.you ? ` <em>${esc(t('You'))}</em>` : ''}</span>
          <strong class="hd-board-score">${row.score}</strong>
        </li>`;
    }).join('');
    // Past the cut the reader still learns where they stand.
    if (answer.you && !answer.rows.some(row => row.you)) {
      you.hidden = false;
      you.textContent = t('Your place: {place} of {players}, with {score}.',
        { place: answer.you.place, players: answer.players, score: answer.you.score });
    }
    say(note.textContent);
  }

  function startCountdown(next) {
    mode = next;
    // Rule 21: audio opens here, inside the gesture that starts the round --
    // never on page load.
    audio?.start();
    countdown = 3;
    root.innerHTML = `
      <section class="hd hd-count" aria-labelledby="hd-count-title">
        <h2 id="hd-count-title" class="hd-title">${esc(t(MODE_COPY[mode][0]))}</h2>
        <p class="hd-count-number pop" data-hd-count aria-hidden="true">3</p>
        <p class="sr-only" data-hd-live role="status" aria-live="polite">${esc(t('Starting in 3'))}</p>
      </section>`;
    const node = root.querySelector('[data-hd-count]');
    const step = () => {
      countdown -= 1;
      if (countdown <= 0) { showPlaying(); return; }
      if (node) { node.textContent = String(countdown); node.classList.remove('pop'); void node.offsetWidth; node.classList.add('pop'); }
      say(t('Starting in {n}', { n: countdown }));
      countdownTimer = setTimeout(step, 700);
    };
    countdownTimer = setTimeout(step, 700);
  }

  function showPlaying() {
    root.innerHTML = `
      <section class="hd hd-play" aria-labelledby="hd-play-title">
        <p class="hd-eyebrow">${esc(t('Two minutes on the belt'))}</p>
        <h2 id="hd-play-title" class="hd-title">${esc(t('Handler'))}</h2>
        <div class="hd-strip">
          <div><dt>${esc(t('Score'))}</dt><dd data-hd-score>0</dd></div>
          <div><dt>${esc(t('Time left'))}</dt><dd data-hd-clock>2:00</dd></div>
          <div><dt>${esc(t('Sorted / wrong / dropped'))}</dt><dd data-hd-tally>0 / 0 / 0</dd></div>
        </div>
        <div class="hd-stage">
          <canvas data-hd-canvas class="hd-canvas" role="img"
            aria-label="${esc(t('The belt. The package at the front shows its routing code and service.'))}"></canvas>
          <p class="hd-edges" aria-hidden="true"><span>${esc(t('INBOUND / TOP'))}</span><span data-hd-deck></span></p>
          <!-- Rule 19: the badge is pinned to the right of the stage, above
               the destinations. It must never sit over the belt, where it
               would cover the code on the package coming down. -->
          <p class="hd-combo off" data-hd-combo aria-hidden="true"><b data-hd-combo-x>x2</b><small data-hd-combo-run></small></p>
          <!-- The destinations are tabs on the belt's own edges, which is
               where the player's thumbs already are. -->
          <button type="button" class="hd-dest left" data-hd-side="0">
            <span class="hd-dest-arrow" aria-hidden="true">←</span>
            <span class="hd-dest-name"></span>
            <span class="hd-dest-sub">${esc(t('LEFT BELT'))}</span>
          </button>
          <button type="button" class="hd-dest right" data-hd-side="1">
            <span class="hd-dest-arrow" aria-hidden="true">→</span>
            <span class="hd-dest-name"></span>
            <span class="hd-dest-sub">${esc(t('RIGHT BELT'))}</span>
          </button>
          <p class="hd-paused" data-hd-paused hidden>${esc(t('Paused'))}</p>
        </div>
        <div class="hd-bar">
          <button type="button" class="hd-icon-btn" data-hd-pause aria-pressed="false">${esc(t('Pause'))}</button>
          <button type="button" class="hd-icon-btn" data-hd-restart>${esc(t('Restart round'))}</button>
          <button type="button" class="hd-icon-btn" data-hd-sound aria-pressed="true">${esc(t('Sound'))}</button>
        </div>
        <p class="hd-hint">${esc(t('Swipe the front box, tap a side belt, or use the arrow keys.'))}</p>
        <p class="sr-only" data-hd-live role="status" aria-live="polite"></p>
      </section>`;
    canvas = root.querySelector('[data-hd-canvas]');
    ctx = canvas?.getContext?.('2d') ?? null;
    // Measure BEFORE the game exists. laneFor() reads the stage, and a game
    // built first gets the lane of whatever stage was there last -- which
    // dropped packages half way up a taller screen.
    measure();
    game = createGame({
      mode: MODES[mode],
      laneLength: laneFor(),
      questionSource: deck => drawRoute(poolFor(deck), random),
    });
    departing = [];
    bursts = [];
    drag = null;
    shownTier = 1;
    bindPlaying();
    say(t('Round started.'));
    last = null;
    startLoop();
  }

  function showSummary() {
    stopLoop();
    audio?.stop();
    const summary = game.summary();
    const previous = bestScores.get(mode);
    const beaten = summary.score > previous;
    if (beaten) bestScores.set(mode, summary.score);
    const percent = Math.round(summary.accuracy * 100);
    root.innerHTML = `
      <section class="hd hd-summary" aria-labelledby="hd-summary-title">
        <p class="hd-eyebrow">${esc(t(MODE_COPY[mode][0]))} · ${esc(t('Two minutes on the belt'))}</p>
        <h2 id="hd-summary-title" class="hd-title">${esc(t('Round over'))}</h2>
        <p class="hd-final"><span>${esc(t('Score'))}</span><strong>${summary.score}</strong></p>
        ${bestScores.saved === false
          // A guest, or a round played between seasons, is told plainly
          // rather than shown a silent zero.
          ? `<p class="hd-best-old">${esc(bestScores.betweenSeasons
            ? t('The season is over, so this score is not saved. Scores count again when the next season starts.')
            : t('Scores are kept only while you are signed in. This one is not saved.'))}</p>`
          : beaten
            ? `<p class="hd-best-new">${esc(t('A new best for {mode}.', { mode: t(MODE_COPY[mode][0]) }))}</p>`
            : `<p class="hd-best-old">${esc(t('Your best for {mode} is {score}.', { mode: t(MODE_COPY[mode][0]), score: previous }))}</p>`}
        <dl class="hd-stats">
          <div><dt>${esc(t('Right belt'))}</dt><dd>${summary.sorts}</dd></div>
          <div><dt>${esc(t('Wrong belt'))}</dt><dd>${summary.missorts}</dd></div>
          <div><dt>${esc(t('Ran off the end'))}</dt><dd>${summary.drops}</dd></div>
          <div><dt>${esc(t('Accuracy'))}</dt><dd>${percent}%</dd></div>
          <div><dt>${esc(t('Longest streak'))}</dt><dd>${summary.longestCombo}</dd></div>
        </dl>
        <div class="hd-actions">
          <button type="button" class="hd-again" data-hd-again>${esc(t('Play again'))}</button>
          <button type="button" class="hd-back" data-hd-back>${esc(t('Change mode'))}</button>
        </div>
        <p class="sr-only" data-hd-live role="status" aria-live="polite">${esc(t('Round over. Score {score}.', { score: summary.score }))}</p>
      </section>`;
    on(root.querySelector('[data-hd-again]'), 'click', () => startCountdown(mode));
    on(root.querySelector('[data-hd-back]'), 'click', showModes);
  }

  // -------------------------------------------------------------------- input

  function bindPlaying() {
    const pause = root.querySelector('[data-hd-pause]');
    const sound = root.querySelector('[data-hd-sound]');
    on(pause, 'click', () => {
      const shot = game.snapshot();
      drag = null;
      if (shot.running) { game.pause(); audio?.stop(); } else { game.resume(); audio?.start(); last = null; }
      const paused = !game.snapshot().running;
      pause.setAttribute('aria-pressed', String(paused));
      pause.textContent = paused ? t('Resume') : t('Pause');
      root.querySelector('[data-hd-paused]').hidden = !paused;
      say(paused ? t('Paused.') : t('Playing.'));
    });
    sound.setAttribute('aria-pressed', String(soundPref.isEnabled()));
    on(sound, 'click', () => {
      const enabled = soundPref.toggle();
      sound.setAttribute('aria-pressed', String(enabled));
      // The game stays fully playable with the sound off (rule 20 is why).
      if (enabled) audio?.start(); else audio?.stop();
      say(enabled ? t('Sound on.') : t('Sound off.'));
    });
    on(root.querySelector('[data-hd-restart]'), 'click', () => startCountdown(mode));
    for (const button of root.querySelectorAll('[data-hd-side]')) {
      on(button, 'click', () => resolve(Number(button.dataset.hdSide)));
    }
    // #395: the front package follows the finger immediately, and only the
    // front package. A drag starts only when the finger lands ON that box --
    // anywhere else on the stage is a scroll, not a sort. Rule 7: the gesture
    // remembers which package it started on, so a package resolved under it
    // cannot be answered for by its replacement.
    const localPoint = event => {
      const box = canvas.getBoundingClientRect();
      return { x: event.clientX - box.left, y: event.clientY - box.top };
    };
    on(canvas, 'pointerdown', event => {
      const shot = game.snapshot();
      if (!shot.running || drag) return;
      const front = shot.packages.find(item => item.front);
      if (!front) return;
      const { w, h, centre } = packageBox();
      const point = localPoint(event);
      if (Math.abs(point.x - centre) > w * 0.65) return;
      if (Math.abs(point.y - (front.y - h / 2)) > w * 0.5) return;
      event.preventDefault?.();
      // Capture keeps the drag alive if the finger leaves the canvas. A
      // browser that refuses the id must not lose the gesture over it.
      try { canvas.setPointerCapture?.(event.pointerId); } catch { /* keep dragging */ }
      drag = { id: front.id, startX: point.x, dx: 0, pointer: event.pointerId, vx: 0, at: event.timeStamp };
    });
    on(canvas, 'pointermove', event => {
      if (drag?.pointer !== event.pointerId) return;
      const dx = localPoint(event).x - drag.startX;
      // The finger's speed, smoothed over the last few moves, so the box can
      // leave at the speed it was already travelling.
      const elapsed = (event.timeStamp - drag.at) / 1000;
      if (elapsed > 0) drag.vx = drag.vx * 0.4 + ((dx - drag.dx) / elapsed) * 0.6;
      drag.dx = dx;
      drag.at = event.timeStamp;
    });
    on(canvas, 'pointerup', event => {
      if (drag?.pointer !== event.pointerId) return;
      const travel = drag.dx;
      const started = drag.id;
      // A short drag is a change of mind: the box springs back and nothing
      // resolves.
      if (Math.abs(travel) < Math.min(SWIPE_MIN, size.w * 0.12)) { drag = null; return; }
      resolve(travel < 0 ? LEFT : RIGHT, started);
    });
    for (const type of ['pointercancel', 'pointerleave']) on(canvas, type, () => { drag = null; });
    on(root.ownerDocument ?? root, 'keydown', event => {
      if (event.key === 'ArrowLeft') { event.preventDefault(); resolve(LEFT); }
      else if (event.key === 'ArrowRight') { event.preventDefault(); resolve(RIGHT); }
    });
  }

  function resolve(side, packageId) {
    if (!game) return;
    const shot = game.snapshot();
    const target = packageId ?? shot.activePackageId;
    const front = shot.packages.find(item => item.id === target);
    const held = drag && drag.id === target ? drag.dx : 0;
    const speed = drag && drag.id === target ? drag.vx : 0;
    const hadCombo = shot.combo;
    drag = null;
    const result = game.choose(side, target);
    if (!result.resolved) return;
    mark(front, result.outcome === 'sorted' ? 'sorted' : 'missort', side, held, speed);
    if (result.outcome !== 'sorted') scatter(front, hadCombo);
    if (result.outcome === 'sorted') {
      audio?.sorted();
      say(t('Right belt. {belt}.', { belt: result.belt }));
    } else {
      audio?.missort();
      say(t('Wrong belt. {belt} was not it.', { belt: result.belt }));
    }
    paintHud();
  }

  // A streak worth seeing is a streak worth seeing lost: the ring scatters
  // from where the package was, rather than simply switching off.
  function scatter(item, hadCombo) {
    if (!item || hadCombo < COMBO_STEP) return;
    const { h, centre } = packageBox();
    bursts.push({ x: centre, y: item.y - h / 2, t: 0 });
  }

  // Rule 20: the verdict is said on the package, where the player is looking,
  // and it travels with the package as it leaves.
  function mark(item, kind, side, dx = 0, vx = 0) {
    if (!item) return;
    const dir = side === LEFT ? -1 : side === RIGHT ? 1 : 0;
    // Only speed in the direction it was sent counts; a box pulled back the
    // other way at the last instant still leaves at the floor speed.
    const v0 = Math.min(FLING_MAX, Math.max(FLING_MIN, vx * dir));
    departing.push({ y: item.y, route: item.route, id: item.id, kind, side, dx, v0, t: 0 });
  }

  // ------------------------------------------------------------------- paint

  function measure() {
    if (!canvas) return;
    const box = canvas.parentElement?.getBoundingClientRect?.() ?? { width: 340, height: 420 };
    const ratio = Math.min(3, globalThis.devicePixelRatio || 1);
    size = { w: Math.max(160, Math.round(box.width)), h: Math.max(220, Math.round(box.height)) };
    canvas.width = Math.round(size.w * ratio);
    canvas.height = Math.round(size.h * ratio);
    canvas.style.width = `${size.w}px`;
    canvas.style.height = `${size.h}px`;
    ctx?.setTransform?.(ratio, 0, 0, ratio, 0, 0);
  }

  // The package box, and with it the distance a package travels. A package
  // enters fully above the stage and leaves fully below it, so the code is
  // never clipped by either edge: the player has the whole lane to read it.
  // That is why the lane the engine runs is the stage height PLUS one box.
  function packageBox() {
    const layout = stageLayout(size.w);
    return { w: layout.packW, h: layout.packH, centre: layout.centre };
  }
  function laneFor() {
    return Math.max(220, size.h) + packageBox().h;
  }

  function roundRect(x, y, w, h, r, fill, stroke) {
    ROUND_RECT(ctx, x, y, w, h, r);
    if (fill) { ctx.fillStyle = fill; ctx.fill(); }
    if (stroke) { ctx.strokeStyle = stroke; ctx.stroke(); }
  }

  // Rule 19: a ring of cold four-point stars orbiting the box, more of them
  // and brighter as the streak holds. Additive blending, so each star adds
  // light rather than painting a dot over the belt.
  //
  // This is a SPARKLE. The owner rejected a version where the package and the
  // belt caught fire; do not bring tongues, embers or a lane glow back.
  function paintSparkles(w, h, spec, clock, alpha) {
    if (!spec.count || reducedMotion()) return;
    const orbit = Math.max(w, h) * 0.6;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    const rim = ctx.createRadialGradient(0, 0, orbit * 0.52, 0, 0, orbit * 1.15);
    rim.addColorStop(0, `rgba(${SPARK_RGB},0)`);
    rim.addColorStop(0.55, `rgba(${SPARK_RGB},${0.1 + 0.1 * spec.intensity})`);
    rim.addColorStop(1, `rgba(${SPARK_RGB},0)`);
    ctx.fillStyle = rim;
    ctx.beginPath(); ctx.arc(0, 0, orbit * 1.15, 0, Math.PI * 2); ctx.fill();
    for (let i = 0; i < spec.count; i += 1) {
      const angle = i * 2.399 + clock * 0.004;
      const radius = orbit * (0.78 + 0.22 * Math.sin(i * 1.7));
      const sx = Math.cos(angle) * radius * 1.08;
      const sy = Math.sin(angle) * radius * 0.78;
      // Two offset sines rather than randomness, so the ring breathes
      // instead of strobing.
      const beat = Math.abs(Math.sin(clock * 0.09 + i * 1.3));
      const size = (2 + 2.6 * spec.intensity) * (0.35 + 0.65 * beat);
      if (size < 0.5) continue;
      ctx.globalAlpha = alpha * (0.35 + 0.65 * beat) * (0.5 + 0.5 * spec.intensity);
      const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, size * 1.9);
      glow.addColorStop(0, 'rgba(255,255,255,1)');
      glow.addColorStop(0.35, `rgba(${SPARK_RGB},.85)`);
      glow.addColorStop(1, `rgba(${SPARK_RGB},0)`);
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(sx, sy, size * 1.9, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,.9)';
      ctx.lineWidth = Math.max(0.8, size * 0.3);
      ctx.beginPath();
      ctx.moveTo(sx - size * 1.7, sy); ctx.lineTo(sx + size * 1.7, sy);
      ctx.moveTo(sx, sy - size * 1.7); ctx.lineTo(sx, sy + size * 1.7);
      ctx.stroke();
    }
    ctx.restore();
  }

  // Rule 20: the whole box washes green on a sort and red on a missort or a
  // drop, with a rim of the same colour and a glyph over it. The colour and
  // the glyph always travel together, because red and green alone fail
  // red-green colour blindness and a player with the sound off would then
  // have no verdict at all.
  function paintVerdict(w, h, kind, alpha) {
    const spec = VERDICT[kind];
    if (!spec) return;
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = alpha * 0.5;
    roundRect(-w / 2, -h / 2, w, h, 9, `rgba(${spec.rgb},0.75)`);
    ctx.restore();
    ctx.globalAlpha = alpha;
    ctx.lineWidth = 5;
    roundRect(-w / 2, -h / 2, w, h, 9, null, `rgba(${spec.rgb},1)`);
    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    ctx.globalAlpha = alpha * 0.55;
    const halo = ctx.createRadialGradient(0, 0, w * 0.34, 0, 0, w * 0.85);
    halo.addColorStop(0, `rgba(${spec.rgb},0.45)`);
    halo.addColorStop(1, `rgba(${spec.rgb},0)`);
    ctx.fillStyle = halo;
    ctx.beginPath(); ctx.arc(0, 0, w * 0.85, 0, Math.PI * 2); ctx.fill();
    ctx.restore();
    ctx.globalAlpha = alpha;
    ctx.lineCap = 'round';
    const s = w * 0.14;
    const glyph = () => {
      ctx.beginPath();
      if (kind === 'sorted') {
        ctx.moveTo(-s, 0); ctx.lineTo(-s * 0.2, s * 0.8); ctx.lineTo(s, -s * 0.8);
      } else {
        ctx.moveTo(-s * 0.8, -s * 0.8); ctx.lineTo(s * 0.8, s * 0.8);
        ctx.moveTo(s * 0.8, -s * 0.8); ctx.lineTo(-s * 0.8, s * 0.8);
      }
      ctx.stroke();
    };
    ctx.strokeStyle = 'rgba(20,12,8,.5)'; ctx.lineWidth = Math.max(4, w * 0.055) + 4; glyph();
    ctx.strokeStyle = '#fff'; ctx.lineWidth = Math.max(4, w * 0.055); glyph();
    ctx.lineCap = 'butt';
  }

  // A package is a taped box carrying a shipping label: the service in small
  // caps, the routing code large, the state under it and a barcode along the
  // bottom. The code is the one thing the player has to read at speed, so it
  // is the largest thing on the box and it shrinks only when it is long.
  function paintPackage(item, alpha, verdict, sparkle, clock, dx = 0, rot = 0) {
    const { w, h, centre } = packageBox();
    ctx.save();
    ctx.translate(centre + dx, item.y - h / 2);
    if (rot) ctx.rotate(rot);
    ctx.globalAlpha = alpha;

    if (sparkle) paintSparkles(w, h, sparkle, clock, alpha);

    const active = Boolean(item.front);
    ctx.shadowColor = '#0006';
    ctx.shadowBlur = active ? 20 : 10;
    ctx.shadowOffsetY = active ? 10 : 6;
    roundRect(-w / 2, -h / 2, w, h, 9, active ? SKIN.boxFace : SKIN.boxFaceIdle, SKIN.boxLine);
    ctx.shadowColor = 'transparent';
    ctx.shadowBlur = 0;
    ctx.shadowOffsetY = 0;

    // Packing tape: one strip across the top, one down the middle.
    roundRect(-w / 2 + 2, -h / 2 + 2, w - 4, 13, 7, SKIN.boxTape);
    ctx.fillStyle = SKIN.boxTapeCentre;
    ctx.fillRect(-w * 0.09, -h / 2, w * 0.18, h);
    ctx.strokeStyle = SKIN.boxTapeLine;
    ctx.lineWidth = 1;
    ctx.strokeRect(-w * 0.09, -h / 2, w * 0.18, h);

    const lw = w * 0.78;
    const lh = h * 0.79;
    roundRect(-lw / 2, -lh / 2 + 3, lw, lh, 4, active ? SKIN.label : SKIN.labelIdle);

    const code = String(item.route.code ?? '');
    ctx.textAlign = 'left';
    ctx.textBaseline = 'alphabetic';
    // The service on the left and the state on the right of one line. They
    // shared a line with the barcode before, and collided with it.
    ctx.fillStyle = SKIN.labelSoft;
    ctx.font = `700 ${Math.max(8, w * 0.045)}px system-ui, sans-serif`;
    ctx.fillText(t(SERVICE_LABEL[item.route.svc] ?? item.route.svc ?? ''), -lw / 2 + 11, -lh / 2 + 18);
    ctx.textAlign = 'right';
    ctx.fillStyle = SKIN.labelFaint;
    ctx.fillText(String(item.route.state ?? '').slice(0, 16), lw / 2 - 11, -lh / 2 + 18);
    ctx.textAlign = 'left';
    // The routing code is the one thing that has to be read at speed, so it
    // is the biggest thing on the label and shrinks only when it is long.
    ctx.fillStyle = SKIN.labelInk;
    ctx.font = `800 ${code.length > 7 ? w * 0.12 : code.length > 5 ? w * 0.145 : w * 0.2}px system-ui, sans-serif`;
    ctx.fillText(code, -lw / 2 + 10, 14);
    // A barcode, so the label reads as a label. Its bars come from the
    // package number, not from randomness, so one package keeps one barcode.
    let bx = -lw / 2 + 11;
    ctx.fillStyle = SKIN.barcode;
    const seed = Number(String(item.id).replace(/\D/g, '')) || 1;
    for (let i = 0; i < 31; i += 1) {
      const bw = ((i * 7 + seed) % 3 + 1) * 0.65;
      ctx.fillRect(bx, lh / 2 - 15, bw, 10);
      bx += bw + 1.1;
      if (bx > lw / 2 - 10) break;
    }

    if (verdict) paintVerdict(w, h, verdict, alpha);
    ctx.restore();
  }

  // The belt itself: a frame, moving slats, dashed guides down each side and
  // a toothed edge at the bottom. It stays the belt -- the streak shows only
  // around the package, which is what the owner asked for after the fire
  // version went too far.
  function paintBelt(clock) {
    const layout = stageLayout(size.w);
    const edge = size.h - 42;

    ctx.fillStyle = SKIN.room;
    ctx.fillRect(0, 0, size.w, size.h);
    ctx.strokeStyle = SKIN.roomLine;
    ctx.lineWidth = 1;
    for (let y = 25; y < size.h; y += 42) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(size.w, y); ctx.stroke();
    }

    roundRect(layout.frameLeft, -20, layout.beltW + FRAME_PAD * 2, edge + 35, 17, SKIN.frameOuter, SKIN.frameOuterLine);
    roundRect(layout.beltLeft - 9, -20, layout.beltW + 18, edge + 27, 12, SKIN.frameInner);
    roundRect(layout.beltLeft, -20, layout.beltW, edge + 19, 8, SKIN.belt);

    ctx.save();
    ctx.beginPath();
    ctx.rect(layout.beltLeft, 0, layout.beltW, edge + 6);
    ctx.clip();
    // The slats scroll with the clock, so the belt is visibly running even
    // when no package is on it.
    const offset = reducedMotion() ? 0 : clock / 24 % 26;
    for (let y = -30 + offset; y < edge + 30; y += 26) {
      ctx.fillStyle = SKIN.slatDark; ctx.fillRect(layout.beltLeft, y, layout.beltW, 3);
      ctx.fillStyle = SKIN.slatLight; ctx.fillRect(layout.beltLeft, y + 3, layout.beltW, 1);
    }
    ctx.restore();

    ctx.strokeStyle = SKIN.guide;
    ctx.setLineDash([4, 13]);
    ctx.beginPath();
    ctx.moveTo(layout.beltLeft - 13, 0); ctx.lineTo(layout.beltLeft - 13, edge);
    ctx.moveTo(layout.beltRight + 13, 0); ctx.lineTo(layout.beltRight + 13, edge);
    ctx.stroke();
    ctx.setLineDash([]);

    roundRect(layout.frameLeft, edge + 3, layout.beltW + FRAME_PAD * 2, 16, 5, SKIN.edge);
    ctx.save();
    ctx.beginPath();
    ctx.rect(layout.frameLeft, edge + 4, layout.beltW + FRAME_PAD * 2, 14);
    ctx.clip();
    ctx.fillStyle = SKIN.edgeTeeth;
    for (let x = layout.frameLeft - 22; x < layout.frameRight + 22; x += 25) {
      ctx.beginPath();
      ctx.moveTo(x, edge + 3); ctx.lineTo(x + 12, edge + 3);
      ctx.lineTo(x + 24, edge + 20); ctx.lineTo(x + 12, edge + 20);
      ctx.fill();
    }
    ctx.restore();

    ctx.fillStyle = SKIN.ink;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'alphabetic';
    ctx.font = '700 9px system-ui, sans-serif';
    ctx.fillText(t('END OF BELT / DON’T DROP IT'), layout.centre, size.h - 10);
  }

  function paintHud() {
    const shot = game.snapshot();
    const clock = root.querySelector('[data-hd-clock]');
    const score = root.querySelector('[data-hd-score]');
    if (clock) clock.textContent = formatClock(shot.remainingMs);
    if (score) score.textContent = String(shot.score);
    const tally = root.querySelector('[data-hd-tally]');
    if (tally) tally.textContent = `${shot.sorts} / ${shot.missorts} / ${shot.drops}`;
    const deck = root.querySelector('[data-hd-deck]');
    if (deck) deck.textContent = t(DECK_LABEL[shot.deck] ?? '');

    paintChoices(shot);

    const badge = root.querySelector('[data-hd-combo]');
    const value = root.querySelector('[data-hd-combo-x]');
    if (!badge) return;
    const spec = sparkleSpec(shot.combo, COMBO_STEP, COMBO_CAP);
    badge.classList.toggle('off', spec.tier < 2);
    badge.classList.toggle('t3', spec.tier === 3);
    badge.classList.toggle('t4', spec.tier >= 4);
    // The tier is written as well as coloured, so stilling the motion or
    // losing the colour removes no information.
    if (value) value.textContent = `x${spec.tier}`;
    const run = root.querySelector('[data-hd-combo-run]');
    if (run) run.textContent = t('{n} in a row', { n: shot.combo });
    if (spec.tier > shownTier) {
      // Rule 21: the tier cue plays inside the badge's bump, so the sound and
      // the movement are one event.
      badge.classList.remove('bump');
      void badge.offsetWidth;
      badge.classList.add('bump');
      audio?.tier(spec.tier);
      say(t('Streak x{n}.', { n: spec.tier }));
    }
    badge.classList.toggle('lost', spec.tier < shownTier);
    shownTier = spec.tier;
  }

  // Rule 4: each destination shows the belt colour AND its written name, so
  // the colour is never the only thing carrying the answer. They are read off
  // the front package, so they cannot change under a gesture.
  let shownOptions = '';
  function paintChoices(shot) {
    const front = shot.packages.find(item => item.front);
    const options = front?.route?.options ?? [];
    const key = `${front?.id ?? ''}|${options.map(option => option.belt).join('|')}`;
    if (key === shownOptions) return;
    shownOptions = key;
    for (const button of root.querySelectorAll('[data-hd-side]')) {
      const option = options[Number(button.dataset.hdSide)];
      const style = option ? BELT_STYLE[option.belt] : null;
      button.querySelector('.hd-dest-name').textContent = option ? option.belt : '';
      button.disabled = !option;
      button.style.background = style?.bg ?? '';
      button.style.color = style?.fg ?? '';
    }
  }

  // Rule 19 again: losing the streak scatters the stars outward rather than
  // fading them, so it is seen even by an eye that was on the belt and not on
  // the badge.
  function paintBursts(dt) {
    for (const burst of bursts) burst.t += dt;
    bursts = bursts.filter(burst => burst.t < BURST_S);
    const base = packageBox().w * 0.6;
    for (const burst of bursts) {
      const k = Math.min(1, burst.t / BURST_S);
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < 10; i += 1) {
        const angle = i * 2.399;
        const distance = base * (0.8 + 1.4 * k);
        const sx = burst.x + Math.cos(angle) * distance * 1.05;
        const sy = burst.y + Math.sin(angle) * distance * 0.8;
        const size = 3.2 * (1 - k);
        if (size < 0.5) continue;
        ctx.globalAlpha = (1 - k) * 0.9;
        const glow = ctx.createRadialGradient(sx, sy, 0, sx, sy, size * 2);
        glow.addColorStop(0, 'rgba(255,255,255,1)');
        glow.addColorStop(0.4, `rgba(${SPARK_RGB},.8)`);
        glow.addColorStop(1, `rgba(${SPARK_RGB},0)`);
        ctx.fillStyle = glow;
        ctx.beginPath(); ctx.arc(sx, sy, size * 2, 0, Math.PI * 2); ctx.fill();
        ctx.strokeStyle = 'rgba(255,255,255,.85)';
        ctx.lineWidth = Math.max(0.8, size * 0.3);
        ctx.beginPath();
        ctx.moveTo(sx - size * 1.6, sy); ctx.lineTo(sx + size * 1.6, sy);
        ctx.moveTo(sx, sy - size * 1.6); ctx.lineTo(sx, sy + size * 1.6);
        ctx.stroke();
      }
      ctx.restore();
    }
  }

  // Rule 20: a sorted or missorted package leaves sideways in one motion,
  // towards the belt it was sent to and at the speed the finger gave it. A
  // dropped one falls straight past the end instead.
  function paintDeparting(dt, clock) {
    for (const effect of departing) effect.t += dt;
    departing = departing.filter(effect => effect.t < (effect.side == null ? DEPART_S : FLING_S));
    for (const effect of departing) {
      const fell = effect.side == null;
      if (fell) {
        const k = effect.t / DEPART_S;
        paintPackage({ y: effect.y + k * k * 220, route: effect.route, id: effect.id, front: true },
          Math.max(0, 1 - k * k), effect.kind, null, clock, 0, k * 0.4);
        continue;
      }
      const dir = effect.side === LEFT ? -1 : 1;
      const k = effect.t / FLING_S;
      const travel = effect.v0 * effect.t + 0.5 * FLING_ACCEL * effect.t * effect.t;
      paintPackage(
        { y: effect.y, route: effect.route, id: effect.id, front: true },
        // Fully visible for most of the way, so the colour and the glyph are
        // read in flight, then gone.
        Math.max(0, 1 - k * k * k),
        effect.kind,
        null,
        clock,
        effect.dx + dir * travel,
        // It starts from the lean it already had under the finger.
        effect.dx * LEAN + dir * k * 0.3,
      );
    }
  }

  function paint(clock, dt) {
    if (!ctx) return;
    const shot = game.snapshot();
    ctx.clearRect(0, 0, size.w, size.h);
    paintBelt(clock);

    const sparkle = sparkleSpec(shot.combo, COMBO_STEP, COMBO_CAP);
    for (let i = shot.packages.length - 1; i >= 0; i -= 1) {
      const item = shot.packages[i];
      // The front package follows the finger, and leans the way it is going.
      const dx = drag && drag.id === item.id ? drag.dx : 0;
      paintPackage(item, item.front ? 1 : 0.69, null, item.front ? sparkle : null, clock,
        dx, dx * LEAN);
    }
    paintDeparting(dt, clock);
    paintBursts(dt);
  }

  function step(stamp) {
    frame = requestAnimationFrame(step);
    // The round normally ends inside tick() below, which shows the summary in
    // the same frame. This catches the other way round -- a round already over
    // when the loop looks -- so the loop can never spin on a finished game.
    if (game.snapshot().ended) { showSummary(); return; }
    if (last === null) { last = stamp; return; }
    const delta = stamp - last;
    last = stamp;
    const seconds = Math.min(delta, 50) / 1000;
    const before = game.snapshot();
    if (before.running) {
      const drops = before.drops;
      const hadCombo = before.combo;
      const after = game.tick(delta);
      if (after.drops > drops) {
        const lost = before.packages[0];
        // side null: a dropped package falls past the end of the belt rather
        // than leaving towards either side.
        if (lost) { mark({ ...lost, y: laneFor() }, 'dropped', null); scatter({ y: laneFor() }, hadCombo); }
        if (drag && lost && drag.id === lost.id) drag = null;
        audio?.dropped();
        say(t('A package ran off the end.'));
      }
      audio?.belt(after.speed);
      paintHud();
      if (after.ended) { showSummary(); return; }
    }
    paint(stamp, seconds);
  }

  function startLoop() {
    if (frame === null) frame = requestAnimationFrame(step);
    if (typeof ResizeObserver === 'function' && canvas?.parentElement) {
      observer = new ResizeObserver(() => measure());
      observer.observe(canvas.parentElement);
    }
  }

  function stopLoop() {
    if (frame !== null) { cancelAnimationFrame(frame); frame = null; }
    if (countdownTimer) { clearTimeout(countdownTimer); countdownTimer = null; }
    observer?.disconnect?.();
    observer = null;
  }

  function unmount() {
    stopLoop();
    audio?.stop();
    for (const off of listeners.splice(0)) off();
    game = null;
    ctx = null;
    canvas = null;
    root.innerHTML = '';
  }

  showModes();
  return { unmount, showModes, showBoard, get mode() { return mode; }, get game() { return game; } };
}
