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
export const VERDICT_HOLD_MS = 260;
// Rule 19, the owner's correction, enforced by geometry rather than by eye.
// The badge gets a column of its own on the right, and the lane and the
// packages are centred in what is left. Measured on a 375px phone, a badge
// merely pinned to the right edge still sat 15px over the lane, so "put it on
// the right" is not enough on its own.
export const BADGE_GUTTER = 76;

// Where the lane and the packages sit, given the stage width. Exported so a
// test can assert the lane never reaches the badge's column.
export function stageLayout(width) {
  const usable = Math.max(120, width - BADGE_GUTTER);
  const centre = usable / 2;
  const packW = Math.min(190, usable * 0.62);
  const laneW = Math.min(240, usable * 0.82);
  return {
    usable,
    centre,
    packW,
    packH: Math.min(120, packW * 0.66),
    laneW,
    laneLeft: centre - laneW / 2,
    laneRight: centre + laneW / 2,
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
  random = Math.random,
  reducedMotion = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches,
} = {}) {
  if (!root) throw new Error('createHandlerScreen needs a root element');
  if (!engine?.createGame) throw new Error('createHandlerScreen needs the engine module');
  if (!routes?.MODES) throw new Error('createHandlerScreen needs the routes module');

  const { createGame, COMBO_STEP, COMBO_CAP, LEFT, RIGHT } = engine;
  const { MODES, MODE_ORDER, routePool, drawRoute } = routes;

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
  let verdicts = [];
  let shownTier = 1;
  let observer = null;
  let canvas = null;
  let ctx = null;
  let size = { w: 0, h: 0 };
  // Canvas colours that follow the theme. Read once per mount from the CSS
  // custom properties above, because getComputedStyle in the paint loop would
  // be a layout read on every frame.
  let paintColours = { lane: 'rgba(0,0,0,0.22)', box: '#d8c6ad', boxLine: 'rgba(60,38,20,0.55)' };
  function readColours() {
    if (typeof getComputedStyle !== 'function' || !canvas) return;
    const style = getComputedStyle(canvas);
    const read = (name, fallback) => style.getPropertyValue(name).trim() || fallback;
    paintColours = {
      lane: read('--hd-lane', paintColours.lane),
      box: read('--hd-box', paintColours.box),
      boxLine: read('--hd-box-line', paintColours.boxLine),
    };
  }
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
        <p class="hd-count-number" data-hd-count aria-hidden="true">3</p>
        <p class="sr-only" data-hd-live role="status" aria-live="polite">${esc(t('Starting in 3'))}</p>
      </section>`;
    const node = root.querySelector('[data-hd-count]');
    const step = () => {
      countdown -= 1;
      if (countdown <= 0) { showPlaying(); return; }
      if (node) node.textContent = String(countdown);
      say(t('Starting in {n}', { n: countdown }));
      countdownTimer = setTimeout(step, 700);
    };
    countdownTimer = setTimeout(step, 700);
  }

  function showPlaying() {
    const definition = MODES[mode];
    game = createGame({
      mode: definition,
      laneLength: laneFor(),
      questionSource: deck => drawRoute(poolFor(deck), random),
    });
    verdicts = [];
    shownTier = 1;
    root.innerHTML = `
      <section class="hd hd-play" aria-labelledby="hd-play-title">
        <h2 id="hd-play-title" class="sr-only">${esc(t('Handler'))} — ${esc(t(MODE_COPY[mode][0]))}</h2>
        <div class="hd-bar">
          <span class="hd-clock" data-hd-clock>2:00</span>
          <span class="hd-score"><span class="hd-score-label">${esc(t('Score'))}</span> <strong data-hd-score>0</strong></span>
          <button type="button" class="hd-icon-btn" data-hd-pause aria-pressed="false">${esc(t('Pause'))}</button>
          <button type="button" class="hd-icon-btn" data-hd-sound aria-pressed="true">${esc(t('Sound'))}</button>
        </div>
        <div class="hd-stage">
          <canvas data-hd-canvas class="hd-canvas" role="img"
            aria-label="${esc(t('The belt. The package at the front shows its routing code and service.'))}"></canvas>
          <!-- Rule 19: the badge is pinned to the right of the stage. It must
               never sit over the lane, where it would cover the code on the
               package coming down. -->
          <p class="hd-combo off" data-hd-combo aria-hidden="true"><span data-hd-combo-x>x2</span></p>
          <p class="hd-paused" data-hd-paused hidden>${esc(t('Paused'))}</p>
        </div>
        <div class="hd-choices" role="group" aria-label="${esc(t('Send the package'))}">
          <button type="button" class="hd-choice" data-hd-side="0"></button>
          <button type="button" class="hd-choice" data-hd-side="1"></button>
        </div>
        <p class="sr-only" data-hd-live role="status" aria-live="polite"></p>
      </section>`;
    canvas = root.querySelector('[data-hd-canvas]');
    ctx = canvas?.getContext?.('2d') ?? null;
    measure();
    readColours();
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
        <h2 id="hd-summary-title" class="hd-title">${esc(t('Round over'))}</h2>
        <p class="hd-final"><span>${esc(t('Score'))}</span><strong>${summary.score}</strong></p>
        ${beaten
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
    for (const button of root.querySelectorAll('[data-hd-side]')) {
      on(button, 'click', () => resolve(Number(button.dataset.hdSide)));
    }
    // Rule 7 and #395: a swipe must not be able to resolve a package other
    // than the one the finger started on, and a cancelled or scrolled gesture
    // must resolve nothing at all.
    let gesture = null;
    on(canvas, 'pointerdown', event => {
      const shot = game.snapshot();
      if (!shot.running || !shot.activePackageId) return;
      gesture = { x: event.clientX, y: event.clientY, id: shot.activePackageId, pointer: event.pointerId };
      canvas.setPointerCapture?.(event.pointerId);
    });
    on(canvas, 'pointermove', event => {
      if (!gesture || event.pointerId !== gesture.pointer) return;
      // A mostly vertical drag is a scroll, not a sort.
      if (Math.abs(event.clientY - gesture.y) > Math.abs(event.clientX - gesture.x) * 1.6) gesture = null;
    });
    on(canvas, 'pointerup', event => {
      if (!gesture || event.pointerId !== gesture.pointer) return;
      const travel = event.clientX - gesture.x;
      const started = gesture.id;
      gesture = null;
      if (Math.abs(travel) < 24) return;
      resolve(travel < 0 ? LEFT : RIGHT, started);
    });
    for (const type of ['pointercancel', 'pointerleave']) on(canvas, type, () => { gesture = null; });
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
    const result = game.choose(side, target);
    if (!result.resolved) return;
    mark(front, result.outcome === 'sorted' ? 'sorted' : 'missort');
    if (result.outcome === 'sorted') {
      audio?.sorted();
      say(t('Right belt. {belt}.', { belt: result.belt }));
    } else {
      audio?.missort();
      say(t('Wrong belt. {belt} was not it.', { belt: result.belt }));
    }
    paintHud();
  }

  // Rule 20: the verdict is said on the package, where the player is looking,
  // and it holds for a beat before the package leaves the belt.
  function mark(item, kind) {
    if (!item) return;
    verdicts.push({ y: item.y, route: item.route, kind, at: 0 });
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

  function paintPackage(item, alpha, verdict, sparkle, clock) {
    const { w, h, centre } = packageBox();
    const x = centre - w / 2;
    const y = item.y - h;
    ctx.save();
    ctx.globalAlpha = alpha;

    if (sparkle && sparkle.count && !reducedMotion()) {
      ctx.save();
      ctx.globalCompositeOperation = 'lighter';
      for (let i = 0; i < sparkle.count; i += 1) {
        const angle = (i / sparkle.count) * Math.PI * 2 + clock / 900;
        const twinkle = 0.45 + 0.55 * Math.abs(Math.sin(clock / 320 + i));
        const radius = Math.max(w, h) * 0.66 + Math.sin(clock / 500 + i) * 5;
        const px = x + w / 2 + Math.cos(angle) * radius;
        const py = y + h / 2 + Math.sin(angle) * radius * 0.72;
        const s = (2.4 + 2.6 * sparkle.intensity) * twinkle;
        ctx.fillStyle = `rgba(${SPARK_RGB},${0.75 * twinkle * sparkle.intensity})`;
        // A four-point star: a sparkle, never a flame. The owner rejected
        // the fire version; do not bring tongues or embers back.
        ctx.beginPath();
        ctx.moveTo(px, py - s * 2.1); ctx.lineTo(px + s * 0.5, py - s * 0.5);
        ctx.lineTo(px + s * 2.1, py); ctx.lineTo(px + s * 0.5, py + s * 0.5);
        ctx.lineTo(px, py + s * 2.1); ctx.lineTo(px - s * 0.5, py + s * 0.5);
        ctx.lineTo(px - s * 2.1, py); ctx.lineTo(px - s * 0.5, py - s * 0.5);
        ctx.closePath(); ctx.fill();
      }
      ctx.restore();
    }

    ROUND_RECT(ctx, x, y, w, h, 14);
    ctx.fillStyle = paintColours.box;
    ctx.fill();
    ctx.lineWidth = 3;
    ctx.strokeStyle = paintColours.boxLine;
    ctx.stroke();

    ctx.fillStyle = '#2b1c10';
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.font = `700 ${Math.round(h * 0.36)}px system-ui, sans-serif`;
    ctx.fillText(String(item.route.code ?? ''), x + w / 2, y + h * 0.42);
    ctx.font = `600 ${Math.round(h * 0.17)}px system-ui, sans-serif`;
    ctx.fillText(`${item.route.svc ?? ''} · ${item.route.state ?? ''}`, x + w / 2, y + h * 0.74);

    if (verdict) {
      const spec = VERDICT[verdict];
      ROUND_RECT(ctx, x, y, w, h, 14);
      ctx.fillStyle = `rgba(${spec.rgb},0.42)`;
      ctx.fill();
      ctx.lineWidth = 5;
      ctx.strokeStyle = `rgb(${spec.rgb})`;
      ctx.stroke();
      // The glyph travels with the colour, always.
      ctx.font = `800 ${Math.round(h * 0.52)}px system-ui, sans-serif`;
      ctx.lineWidth = 6;
      ctx.strokeStyle = 'rgba(20,12,6,0.65)';
      ctx.strokeText(spec.glyph, x + w / 2, y + h / 2);
      ctx.fillStyle = '#ffffff';
      ctx.fillText(spec.glyph, x + w / 2, y + h / 2);
    }
    ctx.restore();
  }

  function paintHud() {
    const shot = game.snapshot();
    const clock = root.querySelector('[data-hd-clock]');
    const score = root.querySelector('[data-hd-score]');
    if (clock) clock.textContent = formatClock(shot.remainingMs);
    if (score) score.textContent = String(shot.score);

    paintChoices(shot);

    const badge = root.querySelector('[data-hd-combo]');
    const value = root.querySelector('[data-hd-combo-x]');
    if (!badge) return;
    const spec = sparkleSpec(shot.combo, COMBO_STEP, COMBO_CAP);
    badge.classList.toggle('off', spec.tier < 2);
    badge.classList.toggle('t3', spec.tier === 3);
    badge.classList.toggle('t4', spec.tier >= 4);
    if (value) value.textContent = `x${spec.tier}`;
    if (spec.tier > shownTier) {
      // Rule 21: the tier cue plays inside the badge's bump, so the sound and
      // the movement are one event.
      badge.classList.remove('bump');
      void badge.offsetWidth;
      badge.classList.add('bump');
      audio?.tier(spec.tier);
      say(t('Streak x{n}.', { n: spec.tier }));
    }
    if (spec.tier < shownTier) badge.classList.add('lost');
    else badge.classList.remove('lost');
    shownTier = spec.tier;
  }

  // The two destinations, rule 4: each shows the belt colour AND its written
  // name, so the colour is never the only thing carrying the answer. They are
  // read off the front package, so they cannot change under a gesture.
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
      button.textContent = option ? t(option.belt) : '';
      button.disabled = !option;
      button.style.background = style?.bg ?? '';
      button.style.color = style?.fg ?? '';
    }
  }

  function paint(clock) {
    if (!ctx) return;
    const shot = game.snapshot();
    ctx.clearRect(0, 0, size.w, size.h);

    // The lane. It stays the belt: nothing on it reacts to the combo.
    const layout = stageLayout(size.w);
    ctx.fillStyle = paintColours.lane;
    ctx.fillRect(layout.laneLeft, 0, layout.laneW, size.h);

    const sparkle = sparkleSpec(shot.combo, COMBO_STEP, COMBO_CAP);
    for (let i = shot.packages.length - 1; i >= 0; i -= 1) {
      const item = shot.packages[i];
      paintPackage(item, item.front ? 1 : 0.82, null, item.front ? sparkle : null, clock);
    }
    for (const verdict of verdicts) {
      const age = verdict.at / VERDICT_HOLD_MS;
      paintPackage({ y: verdict.y, route: verdict.route, front: false }, Math.max(0, 1 - age), verdict.kind, null, clock);
    }
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
    const before = game.snapshot();
    if (before.running) {
      const drops = before.drops;
      const after = game.tick(delta);
      if (after.drops > drops) {
        const lost = before.packages[0];
        if (lost) mark({ ...lost, y: laneFor() }, 'dropped');
        audio?.dropped();
        say(t('A package ran off the end.'));
      }
      audio?.belt(after.speed);
      for (const verdict of verdicts) verdict.at += delta;
      verdicts = verdicts.filter(verdict => verdict.at < VERDICT_HOLD_MS);
      paintHud();
      if (after.ended) { showSummary(); return; }
    }
    paint(stamp);
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
  return { unmount, showModes, get mode() { return mode; }, get game() { return game; } };
}
