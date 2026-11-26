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
const { BADGE_GUTTER, SPARK_RGB, VERDICT, formatClock, sparkleSpec, stageLayout } = view;

// ---------------------------------------------------------------------------
// Rule 19, the owner's correction: the badge never sits over the lane.
//
// This is geometry, not taste. Measured in a browser at 375px, a badge merely
// pinned to the right edge still overlapped the lane by 15px, so the lane is
// centred in the width that is left once the badge has its column.
// ---------------------------------------------------------------------------

test('the lane never reaches the badge column, at any width', () => {
  for (let width = 280; width <= 1200; width += 7) {
    const layout = stageLayout(width);
    assert.ok(layout.laneRight <= layout.badgeLeft,
      `at ${width}px the lane reaches ${layout.laneRight} and the badge starts at ${layout.badgeLeft}`);
    assert.ok(layout.centre + layout.packW / 2 <= layout.badgeLeft,
      `at ${width}px a package would run under the badge`);
    assert.ok(layout.laneLeft >= 0 && layout.packW > 60, `at ${width}px the lane fell off the left`);
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
  assert.match(viewSource, /value\.textContent = `x\$\{spec\.tier\}`/);
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
  for (const selector of ['.hd-icon-btn', '.hd-choice', '.hd-again', '.hd-back', '.hd-mode']) {
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
  assert.match(viewSource, /button\.textContent = option \? t\(option\.belt\) : ''/);
  assert.match(viewSource, /BELT_STYLE\[option\.belt\]/);
});

test('audio opens on the gesture that starts a round, never on load', () => {
  const start = viewSource.indexOf('function startCountdown');
  const end = viewSource.indexOf('function showPlaying');
  assert.match(viewSource.slice(start, end), /audio\?\.start\(\)/);
  // Nothing may start audio at module scope.
  assert.ok(!/^\s*audio\.start\(\)/m.test(viewSource));
  assert.match(audioSource, /if \(running\) return;/);
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
