// Findings from the Web Interface Guidelines review (the Vercel rule set),
// run over index.html and src/*.js.
//
// The one that mattered: not a single tap in the app set `touch-action`, so
// the browser held every tap for about 300ms to see whether a second one
// followed (double-tap to zoom). In a quiz on a clock that is time taken off
// the player on every answer.
//
// The rest: the night theme never told the browser it was dark, so the
// scrollbars and the insides of text fields stayed light inside it; the phone
// bar above the page was never given a colour to match; the heading face named
// in the CSS, "Space Grotesk", had no @font-face and no file in assets/, so
// four selectors that no later layer overrode were silently drawing in the
// system sans while the rest of the app was Nunito; the prize hat reserved no
// height, so the card under it jumped when the drawing arrived; and a loading
// string ended in three dots instead of an ellipsis, in both languages.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

test('a tap acts at once', () => {
  const rule = css.match(/([^{}]*)\{[^}]*touch-action: manipulation[^}]*\}/);
  assert.ok(rule, 'nothing sets touch-action: manipulation');
  // The things a player taps, not just one class: a rule naming a single
  // component leaves the rest of the app on the 300ms delay.
  for (const selector of ['button', 'a', 'summary', 'label']) {
    assert.match(rule[1], new RegExp(`(^|[\\s,])${selector}([\\s,]|$)`), `${selector} is not covered`);
  }
});

test('both themes declare what the browser paints for itself', () => {
  // :root is Night; the day block overrides it. Both are stated, so neither
  // theme falls through to the player's system setting.
  assert.match(css, /:root \{[^}]*color-scheme: dark/);
  assert.match(css, /html\[data-theme="day"\] \{[^}]*color-scheme: light/);
});

test('the phone bar is given each theme’s own colour', () => {
  const meta = html.match(/<meta name="theme-color" content="(#[0-9a-f]{6})">/);
  assert.ok(meta, 'no theme-color meta');
  // The tag ships with Night, which is the default theme, and applyTheme
  // rewrites it. Both values live in one place in app.js.
  const bar = app.match(/const THEME_BAR = \{ night: '(#[0-9a-f]{6})', day: '(#[0-9a-f]{6})' \}/);
  assert.ok(bar, 'applyTheme has no bar colours');
  assert.equal(meta[1], bar[1], 'the tag must ship with the default theme’s colour');
  assert.match(app, /applyTheme[\s\S]{0,700}meta\[name="theme-color"\]/, 'the toggle does not update the tag');
});

test('the page cannot scroll sideways', () => {
  // `clip`, not `hidden`: `hidden` on <html> would make it a scroll container
  // and break every `position: sticky` inside it.
  assert.match(css, /html, body \{[^}]*overflow-x: clip/);
  assert.doesNotMatch(css, /html[^{]*\{[^}]*overflow-x: hidden/);
});

test('no rule asks for a font the app does not ship', () => {
  const faces = [...css.matchAll(/@font-face \{([^}]*)\}/g)]
    .map((m) => m[1].match(/font-family: *([^;]+);/)?.[1].trim().replace(/["']/g, ''))
    .filter(Boolean);
  assert.ok(faces.includes('Nunito'), 'Nunito is no longer declared');
  // Every family named in the stylesheet is either one the app loads or a
  // fallback the device already has. "Space Grotesk" was neither.
  assert.doesNotMatch(css, /Space Grotesk/);
});

test('the display face is fetched with the page, not after the stylesheet', () => {
  const preload = html.match(/<link rel="preload" href="([^"]+)" as="font"[^>]*>/);
  assert.ok(preload, 'the font is not preloaded');
  assert.match(preload[0], /crossorigin/, 'a font preload without crossorigin is fetched twice');
  const face = css.match(/@font-face \{[^}]*src: url\("([^"]+)"\)/);
  assert.equal(preload[1], face[1], 'the preload and the @font-face must name one file');
});

test('the prize hat reserves its box before the drawing arrives', () => {
  const rule = css.match(/\n  \.home-prize-hat \{([^}]*)\}/)[1];
  assert.match(rule, /aspect-ratio: *650 *\/ *450/);
  assert.doesNotMatch(rule, /height: *auto/);
});

test('a loading string ends in an ellipsis in both languages', () => {
  assert.match(app, /Preparing the sheet…/);
  assert.match(i18n, /'Preparing the sheet…': 'Preparando la hoja…'/);
  // The key and the Spanish value are one string pair; three dots in either
  // one would leave the lookup missing and the screen in English.
  assert.doesNotMatch(app, /Preparing the sheet\.\.\./);
  assert.doesNotMatch(i18n, /hoja\.\.\./);
});
