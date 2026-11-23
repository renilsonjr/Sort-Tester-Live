// Outer radius = inner radius + padding. Where that does not hold, the inner
// tile reads rounder than the card holding it; on the Practice cards the
// card's own corner was actually tighter than its icon tile, which is what
// made it look pinched.
//
// Measured in the running app after the change: 26/12/14, 26/12/14 and
// 32/14/18 on the three surfaces.
//
// The --r-sm and --r-md tokens are deliberately NOT changed. Twenty-two other
// rules use them and most hold nothing nested, so moving a token to fix three
// surfaces would round off the whole app.

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
  // icon tile 12px, padding 14px
  assert.equal(radiusOf('.lab-choice'), 26);
});

test('the Home shortcuts are concentric with their icon square', () => {
  // icon square 12px, padding 14px
  assert.equal(radiusOf('.home-short'), 26);
});

test('the Ranked card is concentric with the button inside it', () => {
  // Play Ranked carries --r-sm (14px), padding 18px
  assert.equal(radiusOf('.home-spot'), 32);
});

test('the shared radius tokens are left alone', () => {
  assert.match(html, /--r-md:\s*22px/);
  assert.match(html, /--r-sm:\s*14px/);
});
