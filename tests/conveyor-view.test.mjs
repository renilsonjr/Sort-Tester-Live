import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { loadAppModules } from './helpers/load-app-modules.mjs';
import { HEADER, extractAppStyle } from '../tools/build-handler-preview-css.mjs';

const read = name => readFile(new URL(`../${name}`, import.meta.url), 'utf8');
const [viewSource, audioSource, indexHtml, previewCss, previewHtml, i18nSource] = await Promise.all([
  read('src/conveyor/view.js'), read('src/conveyor/audio.js'), read('index.html'),
  read('mockups/handler-preview.css'), read('mockups/handler-preview.html'), read('src/i18n.js'),
]);
const { modules: [view], cleanup } = await loadAppModules(['src/conveyor/view.js']);
after(cleanup);
const { BADGE_GUTTER, BURST_S, DEPART_S, FLING_MIN, FLING_S, FRAME_PAD, SKIN, SPARK_RGB, SWIPE_MIN, VERDICT,
  formatClock, sparkleSpec, stageLayout } = view;

// ---------------------------------------------------------------------------
// Rule 19, the owner's correction: the badge never sits over the lane.
//
// This is geometry, not taste. Measured in a browser at 375px, a badge merely
// pinned to the right edge still overlapped the lane by 15px, so the lane is
// centred in the width that is left once the badge has its column.
// ---------------------------------------------------------------------------

test('the belt never reaches the badge column, at any width', () => {
  for (let width = 280; width <= 1200; width += 7) {
    const layout = stageLayout(width);
    assert.ok(layout.frameRight <= layout.badgeLeft,
      `at ${width}px the frame reaches ${layout.frameRight} and the badge starts at ${layout.badgeLeft}`);
    assert.ok(layout.packRight <= layout.badgeLeft,
      `at ${width}px a package would run under the badge`);
    assert.ok(layout.frameLeft >= 0, `at ${width}px the frame fell off the left`);
    assert.ok(layout.packW >= 80, `at ${width}px the package is ${layout.packW}px wide and the code stops being readable`);
    assert.ok(layout.packW < layout.beltW, 'a package must sit inside the belt, not over its frame');
  }
});

test('the side destinations never cover the package', () => {
  // They sit on the belt's edges, which is where the thumbs are, and they may
  // overlap the frame. Covering the code is what they must never do.
  for (let width = 280; width <= 1200; width += 11) {
    const layout = stageLayout(width);
    const tabRight = width * 0.02 + Math.min(150, width * 0.22);
    assert.ok(tabRight <= layout.packLeft,
      `at ${width}px the left destination reaches ${tabRight} and the package starts at ${layout.packLeft}`);
  }
});

test('the badge sits in the gutter the layout reserves', async () => {
  const block = indexHtml.slice(indexHtml.indexOf('.hd-combo {'));
  const rule = block.slice(0, block.indexOf('}'));
  assert.match(rule, /position:\s*absolute/);
  assert.match(rule, /right:\s*(\d+)px/, 'the badge is pinned right, never centred');
  assert.ok(!/left:\s*50%/.test(rule), 'a centred badge covers the code on the package coming down');
  const right = Number(/right:\s*(\d+)px/.exec(rule)[1]);
  const width = Number(/width:\s*(\d+)px/.exec(rule)[1]);
  assert.ok(right + width <= BADGE_GUTTER, `the badge needs ${right + width}px but only ${BADGE_GUTTER}px is reserved`);
  assert.ok(FRAME_PAD > 0);
});

// ---------------------------------------------------------------------------
// Rule 19: a sparkle, not a flame.
// ---------------------------------------------------------------------------

test('the combo effect is a sparkle and nothing catches fire', () => {
  for (const word of ['flame', 'fire', 'ember', 'tongue', 'blaze', 'vignette']) {
    const used = new RegExp(`\\b${word}`, 'i').test(viewSource.replace(/\/\/.*$/gm, '').replace(/\/\*[\s\S]*?\*\//g, ''));
    assert.ok(!used, `the owner rejected the fire version; ${word} must not come back`);
  }
  // Icy cyan, deliberately far from the BLUE belt's navy #1f4e9c, so a glow
  // around a package can never be read as a routing colour.
  const [r, g, b] = SPARK_RGB.split(',').map(Number);
  assert.ok(b > 200 && g > 180 && r > 100, 'the sparkle must stay an icy cyan');
  assert.ok(Math.abs(r - 0x1f) + Math.abs(g - 0x4e) + Math.abs(b - 0x9c) > 200, 'the sparkle must not approach the BLUE belt');
});

test('the ring means something: nothing below the first tier, then it grows', () => {
  assert.equal(sparkleSpec(0).count, 0);
  assert.equal(sparkleSpec(4).count, 0, 'four in a row is still x1 and earns no ring');
  const five = sparkleSpec(5);
  const ten = sparkleSpec(10);
  const fifteen = sparkleSpec(15);
  assert.ok(five.count > 0 && ten.count > five.count && fifteen.count > ten.count);
  assert.deepEqual(sparkleSpec(99), fifteen, 'the ring stops where the multiplier stops');
  assert.ok(fifteen.intensity <= 1);
});

// ---------------------------------------------------------------------------
// Rule 20: colour and glyph always travel together.
// ---------------------------------------------------------------------------

test('every verdict carries a glyph as well as a colour', () => {
  for (const [outcome, spec] of Object.entries(VERDICT)) {
    assert.match(spec.rgb, /^\d{1,3},\d{1,3},\d{1,3}$/, `${outcome} has no colour`);
    assert.ok(spec.glyph && spec.glyph.length === 1, `${outcome} has no glyph, so colour would carry it alone`);
  }
  assert.notEqual(VERDICT.sorted.glyph, VERDICT.missort.glyph);
  // A drop and a missort are both mistakes and look alike; the sound tells
  // them apart, which is why audio.js has a thud of its own.
  assert.equal(VERDICT.dropped.glyph, VERDICT.missort.glyph);
  assert.match(audioSource, /dropped\s*=/);
});

test('there is no running commentary under the belt', () => {
  // The owner found that text pulled the eye off the lane. The outcome still
  // reaches a screen reader, through a visually hidden live region.
  assert.ok(!/class="hd-feedback|class="feedback/.test(viewSource));
  assert.match(viewSource, /class="sr-only" data-hd-live role="status" aria-live="polite"/);
  assert.match(viewSource, /function say\(/);
});

test('the clock reads as a clock', () => {
  assert.equal(formatClock(120000), '2:00');
  assert.equal(formatClock(61000), '1:01');
  assert.equal(formatClock(999), '0:01');
  assert.equal(formatClock(0), '0:00');
  assert.equal(formatClock(-50), '0:00');
});

// ---------------------------------------------------------------------------
// Reach, and the app's own conventions.
// ---------------------------------------------------------------------------

test('reduced motion stills the movement without touching a rule', () => {
  const at = indexHtml.indexOf('@media (prefers-reduced-motion: reduce)', indexHtml.indexOf('Handler, the conveyor mini-game'));
  assert.ok(at > 0, 'the Handler block has no reduced-motion rules');
  const block = indexHtml.slice(at, indexHtml.indexOf('}\n\n', at));
  assert.match(block, /animation:\s*none/);
  // The tier is still carried by the badge's colour and its written
  // multiplier, so stilling the motion removes no information.
  assert.ok(viewSource.includes('value.textContent = `x${spec.tier}`'),
    'the tier must be written, not only coloured');
});

test('every control can be reached by finger and by keyboard', () => {
  const block = indexHtml.slice(indexHtml.indexOf('Handler, the conveyor mini-game'), indexHtml.indexOf('Desktop (#273'));
  // Selectors are grouped in this stylesheet (".hd-again, .hd-back {"), so
  // find the rule that names the selector rather than one that starts with it.
  const ruleFor = selector => {
    for (const rule of block.split('}')) {
      const head = rule.slice(rule.lastIndexOf('\n', rule.indexOf('{')) + 1, rule.indexOf('{'));
      if (head.split(',').some(part => part.trim() === selector)) return rule;
    }
    return null;
  };
  for (const selector of ['.hd-icon-btn', '.hd-dest', '.hd-again', '.hd-back', '.hd-mode']) {
    const rule = ruleFor(selector);
    assert.ok(rule, `${selector} has no rule of its own`);
    const height = /min-height:\s*(\d+)px/.exec(rule);
    assert.ok(height && Number(height[1]) >= 44, `${selector} must be at least 44px tall`);
  }
  assert.match(block, /:focus-visible\s*\{[^}]*outline:/, 'focus must be visible');
  assert.match(viewSource, /event\.key === 'ArrowLeft'/);
  assert.match(viewSource, /event\.key === 'ArrowRight'/);
  // A vertical drag is a scroll, and a cancelled gesture resolves nothing.
  assert.match(viewSource, /pointercancel/);
});

test('both destinations show the belt name, never the colour alone', () => {
  assert.match(viewSource, /\.hd-dest-name'\)\.textContent = option \? option\.belt : ''/);
  assert.match(viewSource, /BELT_STYLE\[option\.belt\]/);
});

test('Handler keeps a skin of its own and does not follow the day theme', () => {
  const block = indexHtml.slice(indexHtml.indexOf('Handler, the conveyor mini-game'), indexHtml.indexOf('Desktop (#273'));
  // The slice opens inside the block's own comment, so drop everything up to
  // that comment's end before looking: the comment explains that Handler must
  // not follow the day theme, and saying so is not doing it.
  const rules = block.slice(block.indexOf('*/') + 2).replace(/\/\*[\s\S]*?\*\//g, '');
  assert.ok(!rules.includes('data-theme'),
    'Handler is dark in both themes by owner decision; do not theme it');
  assert.match(block, /\.hd \{[^}]*--hd-900:/, 'the skin must declare its own tokens on .hd');
  // The canvas cannot read a token, so the same palette lives in SKIN.
  assert.equal(SKIN.room, '#2a1b15');
  assert.ok(Object.values(SKIN).every(value => /^#[0-9a-f]{6}$/.test(value)));
});

test('the sound levels are the owner\'s, not a guess', () => {
  // An earlier pass of audio.js invented these and came out two to three
  // times too quiet, which is why the game sounded as though it had none.
  // They are the prototype's numbers now.
  assert.match(audioSource, /MASTER_GAIN = 0\.85/);
  assert.match(audioSource, /MUSIC_GAIN = 0\.15/);
  assert.match(audioSource, /BELT_GAIN = 0\.035/);
  // The cues go straight to master, so they always cut through the belt.
  assert.match(audioSource, /osc\.connect\(envelope\)\.connect\(bus \|\| master\)/);
  // A drop is a thud, not a wrong answer.
  assert.match(audioSource, /dropped = \(\) => \{ if \(context\) blip\(150/);
  // The tier arpeggio is longer and higher at each step.
  assert.match(audioSource, /multiplier >= 4 \? \[12, 16, 19, 24, 28\]/);
});

test('audio opens on the gesture that starts a round, never on load', () => {
  const start = viewSource.indexOf('function startCountdown');
  const end = viewSource.indexOf('function showPlaying');
  assert.match(viewSource.slice(start, end), /audio\?\.start\(\)/);
  // Nothing may start audio at module scope.
  assert.ok(!/^\s*audio\.start\(\)/m.test(viewSource));
  // start() is idempotent: a second round must not stack a second belt or a
  // second melody on top of the first.
  assert.match(audioSource, /if \(master\) return true;/);
  assert.match(audioSource, /if \(!timer\) timer = setInterval/);
});

// ---------------------------------------------------------------------------
// EN and ES, like the rest of the app.
// ---------------------------------------------------------------------------

test('every string the screen shows has a Spanish entry', () => {
  const strings = [...viewSource.matchAll(/\bt\('((?:[^'\\]|\\.)*)'/g)].map(match => match[1]);
  assert.ok(strings.length > 25, `only found ${strings.length} translatable strings`);
  const missing = strings.filter(source => {
    if (source === 'Handler') return false; // a job title: it stays Handler
    if (/^[A-Z]+$/.test(source)) return false; // belt names are proper names
    return !i18nSource.includes(`  '${source.replace(/\\'/g, "'")}':`);
  });
  assert.deepEqual(missing, [], 'these have no ES entry in src/i18n.js');
});

// ---------------------------------------------------------------------------
// The preview is only evidence while it is styled by the app's own stylesheet.
// ---------------------------------------------------------------------------

test('the preview stylesheet has not drifted from index.html', () => {
  assert.equal(previewCss, HEADER + extractAppStyle(indexHtml),
    'run: node tools/build-handler-preview-css.mjs');
});

test('the preview says plainly that it is not the app', () => {
  assert.match(previewHtml, /not the app/);
  assert.match(previewHtml, /stage 4/, 'it must say where the real wiring happens');
  // It loads the shipping modules rather than a copy of them.
  assert.match(previewHtml, /from '\.\.\/src\/conveyor\/view\.js'/);
});

// ---------------------------------------------------------------------------
// The feel: the prototype's gesture and its two effects.
// ---------------------------------------------------------------------------

test('the front package follows the finger, and only the front package', () => {
  // #395: "The front package follows the finger immediately." The drag offset
  // reaches the painter, so the box moves under the thumb instead of waiting
  // for the gesture to end.
  assert.match(viewSource, /const dx = drag && drag\.id === item\.id \? drag\.dx : 0;/);
  assert.match(viewSource, /paintPackage\(item, item\.front \? 1 : 0\.69[\s\S]{0,120}dx, dx \* LEAN\)/);
  // A drag starts only when the finger lands on that box: anywhere else on
  // the stage is a scroll.
  assert.match(viewSource, /Math\.abs\(point\.x - centre\) > w \* 0\.65/);
  assert.match(viewSource, /Math\.abs\(point\.y - \(front\.y - h \/ 2\)\) > w \* 0\.5/);
  // A short drag is a change of mind and resolves nothing.
  assert.ok(SWIPE_MIN >= 32 && SWIPE_MIN <= 80, `a ${SWIPE_MIN}px swipe threshold is not a swipe`);
  assert.match(viewSource, /Math\.abs\(travel\) < Math\.min\(SWIPE_MIN, size\.w \* 0\.12\)/);
});

test('a gesture cannot survive a pause or the package it started on', () => {
  assert.match(viewSource, /if \(drag && lost && drag\.id === lost\.id\) drag = null;/);
  assert.match(viewSource, /drag = null;\n\s+if \(shot\.running\) \{ game\.pause\(\)/);
  assert.match(viewSource, /for \(const type of \['pointercancel', 'pointerleave'\]\)/);
});

test('a resolved package leaves the belt the way it was sent', () => {
  // Owner correction, 2026-11-26: no hold. The box leaves at the speed the
  // finger gave it, never slower than the floor, and from the lean it had.
  assert.match(viewSource, /effect\.v0 \* effect\.t \+ 0\.5 \* FLING_ACCEL \* effect\.t \* effect\.t/);
  assert.match(viewSource, /Math\.min\(FLING_MAX, Math\.max\(FLING_MIN, vx \* dir\)\)/);
  assert.match(viewSource, /effect\.dx \* LEAN \+ dir \* k \* 0\.3/);
  assert.ok(FLING_MIN * FLING_S > 200, 'even a tap must carry the box clear of the belt');
  assert.ok(FLING_S <= 0.35, 'a sorted box must not linger on the belt');
  // A drop falls past the end of the belt instead of leaving sideways.
  assert.match(viewSource, /effect\.y \+ k \* k \* 220/);
  assert.match(viewSource, /mark\(\{ \.\.\.lost, y: laneFor\(\) \}, 'dropped', null\)/);
  assert.ok(DEPART_S > 0.3 && DEPART_S < 1, 'a drop must be seen falling without stalling the belt');
});

test('losing a real streak scatters the ring instead of switching it off', () => {
  assert.match(viewSource, /function scatter\(item, hadCombo\) \{/);
  // Nothing scatters when there was no tier to lose: the effect has to mean
  // something, exactly as the ring itself does.
  assert.match(viewSource, /if \(!item \|\| hadCombo < COMBO_STEP\) return;/);
  assert.ok(BURST_S < 0.5, 'the scatter must be over quickly and never flash the screen');
  assert.ok(viewSource.includes("ctx.globalCompositeOperation = 'lighter'"), 'the stars add light rather than painting dots');
});
