// The chart's service filters (Ground, Next Day Air, 2 Day Air, 3 Day Select)
// are tapped with a gloved thumb on the warehouse floor, so they have to clear
// the 44x44 touch minimum. They drew at 40px tall.
//
// Only the height ever failed: the labels make every chip at least 71px wide.
// So the padding is deliberately left alone -- widening them would re-wrap the
// row on a phone for no gain.
//
// Measured in the running app after the change, at 375px and 1440px, in both
// themes: every chip 44px tall, widths unchanged at 71/103/82/101, still two
// rows at 375px and one at 1440px, 7px between chips and none overlapping.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

const PILL = /\.lab-service-tabs button \{([^}]*)\}/g;

function pillRules() {
  return [...html.matchAll(PILL)].map(m => m[1]);
}

test('the chart filters clear the touch minimum', () => {
  const withHeight = pillRules().filter(r => /min-height/.test(r));
  assert.equal(withHeight.length, 1, 'exactly one rule should set their height');
  const height = Number(withHeight[0].match(/min-height:\s*(\d+)px/)[1]);
  assert.ok(height >= 44, `${height}px is below the 44px touch minimum`);
});

test('the filters keep their padding, so the row does not re-wrap', () => {
  // 9px 13px is what makes the chips 71-103px wide, which already clears 44.
  // Growing the padding to reach the minimum would push a fourth chip onto a
  // third row at 375px and buy nothing.
  const withHeight = pillRules().find(r => /min-height/.test(r));
  assert.match(withHeight, /padding:\s*9px 13px/);
});

test('the filters still sit apart from each other', () => {
  // 7px between chips; the fix changes height only, so nothing can overlap.
  assert.match(html, /\.lab-service-tabs \{ display: flex; flex-wrap: wrap; gap: 7px; \}/);
});
