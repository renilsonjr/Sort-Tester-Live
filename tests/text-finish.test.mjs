// The finishing group: #343 (the dock's dead `transition: all`), #348 (text
// wrapping) and #349 (font smoothing).
//
// Measured in the running app before and after. Before: the dock button
// resolved to `transition-property: all` at 0.2s; body smoothing was `auto`;
// every heading was `text-wrap: wrap`. After: the dock resolves to
// `transform, background-color, color, box-shadow` at 0.12s -- the same pair
// every other control uses -- smoothing is `antialiased`, and the headings
// and body copy carry `balance` and `pretty`.
//
// The wrapping change does nothing in English on Home, where the headings
// already fit one line. It earns its place in Spanish, where the same
// strings run longer: "La temporada oficial ha empezado" went from a 183px
// line over a 79px stub to 108/154, and the Practice card's description
// stopped leaving a 20px orphan alone on its third line.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

// Comments explain these very declarations, so a plain search would match the
// prose that says they are gone.
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('nothing transitions `all` any more', () => {
  // `transition: all` on the dock could not animate anything -- the shell is
  // rebuilt on every navigation, so the selected tab is a new node with no
  // previous value to move from. What it did do was win on !important and
  // drag the dock's press onto `all` at 0.2s (#343).
  assert.doesNotMatch(css, /transition:\s*all/);
  assert.doesNotMatch(css, /transition-property:\s*all/);
});

test('the dock keeps the shared press transition', () => {
  // Removing the override only helps if the shared rule still names the dock.
  const shared = css.match(/\.primary, \.ghost, \.lab-choice, \.home-short, \.lab-nav button, \.belt \{([^}]*)\}/);
  assert.ok(shared, 'the shared press rule no longer lists .lab-nav button');
  assert.match(shared[1], /transition-property:\s*transform, background-color, color, box-shadow/);
  assert.match(shared[1], /transition-duration:\s*\.12s/);
});

test('body text is smoothed on macOS and iOS', () => {
  const body = css.match(/\n  body \{([^}]*)\}/)[1];
  assert.match(body, /-webkit-font-smoothing:\s*antialiased/);
  // Without the Firefox half, the same text renders heavier there than in
  // Safari and Chrome.
  assert.match(body, /-moz-osx-font-smoothing:\s*grayscale/);
});

test('headings balance and body copy avoids orphans', () => {
  const balance = css.match(/\n  h1, h2, \.home-spot-title \{([^}]*)\}/);
  assert.ok(balance, 'the balance rule is gone or its selector changed');
  assert.match(balance[1], /text-wrap:\s*balance/);

  // `.home-spot-desc` left the group when the Ranked card's blurb was
  // removed; the rule still covers every piece of body copy that is left.
  const pretty = css.match(/\n  \.lab-disclaimer, \.home-short small, \.lab-choice small \{([^}]*)\}/);
  assert.ok(pretty, 'the pretty rule is gone or its selector changed');
  assert.match(pretty[1], /text-wrap:\s*pretty/);
});

test('balance is not applied to a class nothing renders', () => {
  // `.lab-section-heading` is styled four times in this file and never put in
  // the DOM -- the eyebrow labels are `.lab-eyebrow`. Adding a declaration to
  // it would be dead CSS of exactly the kind this group removes.
  assert.doesNotMatch(
    css,
    /h1, h2, \.home-spot-title, \.lab-section-heading/,
    'balance is back on a selector that never renders',
  );
});

test('`pretty` is not sprayed across all body text', () => {
  // `pretty` costs layout work on long paragraphs, and the app has one real
  // paragraph block. It stays on the four places that showed orphans.
  assert.doesNotMatch(css, /\n  (?:body|p) \{[^}]*text-wrap:\s*pretty/);
});
