// Outer radius = inner radius + padding. Where that does not hold, the inner
// tile reads rounder than the card holding it; on the Practice cards the
// card's own corner was actually tighter than its icon tile, which is what
// made it look pinched.
//
// Measured in the running app: 28/12/16 on the Practice cards, 26/12/14 on
// the Home shortcuts and 32/16/16 on the Ranked card.
//
// 2026-11-27: the owner approved a radius scale (6 / 12 / 16 / 22) and chose
// that it applies to the piece INSIDE (a button is 16, an icon tile is 12)
// while the card around it stays computed: inner + padding. So --r-sm moved
// from 14 to 16, and the cards that hold a button were re-padded to match.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

// `.lab-choice` is declared five times over. Same specificity each time, so
// the winner is the LAST one that states a radius -- which is the one the
// browser measured at 26px. Reading the first match would have tested a rule
// that nothing renders.
function radiusOf(selector) {
  const rules = [...html.matchAll(new RegExp(`\\n\\s*\\${selector} \\{([^}]*)\\}`, 'g'))];
  assert.ok(rules.length, `${selector} is gone`);
  const withRadius = rules
    .map(r => r[1].match(/border-radius:\s*(\d+)px/))
    .filter(Boolean);
  assert.ok(withRadius.length, `${selector} no longer states its radius in px`);
  return Number(withRadius[withRadius.length - 1][1]);
}

test('the Practice cards are concentric with their icon tile', () => {
  // icon tile 12px, padding 16px
  assert.equal(radiusOf('.lab-choice'), 28);
  assert.match(html, /\n  \.lab-choice \{ border-radius: 28px; padding: 16px;/);
});

test('the Home shortcuts are concentric with their icon square', () => {
  // icon square 12px, padding 14px
  assert.equal(radiusOf('.home-short'), 26);
});

test('the Ranked card is concentric with the button inside it', () => {
  // Play Ranked carries --r-sm (16px), padding 16px on every side
  assert.equal(radiusOf('.home-spot'), 32);
  assert.match(html, /\n  \.home-spot \{[^}]*padding: 16px;/);
});

test('the shared radius tokens sit on the approved scale', () => {
  assert.match(html, /--r-md:\s*22px/);
  assert.match(html, /--r-sm:\s*16px/);
});

test('a disabled button sits back into the surface, in either theme', () => {
  // The first skin's rule painted it cream (#ebe2d4) and nothing in the
  // current skin overrode it, so on the dark page a button that could not be
  // pressed was the brightest thing on the screen. The newer rule has the
  // same specificity and comes later, so it is the one that renders.
  const rules = [...html.matchAll(/\n\s*\.primary:disabled, \.ghost:disabled[^{]*\{([^}]*)\}/g)].map(r => r[1]);
  assert.ok(rules.length >= 2, 'the override should come after the old rule');
  const last = rules[rules.length - 1];
  assert.match(last, /background: var\(--glass-surface-sub\)/);
  assert.match(last, /color: var\(--muted\)/);
  assert.doesNotMatch(last, /#ebe2d4/);
});
