import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ BELTS, BELT_STYLE }], cleanup } = await loadAppModules(['src/belts.js']);
after(cleanup);

// BLACK joins the chart with the SORT CHANGE edits (TX GND/3DS).
test('BLACK is a registered belt with a legible chip', () => {
  assert.ok(BELTS.includes('BLACK'), 'BELTS includes BLACK');
  assert.ok(BELT_STYLE.BLACK, 'BELT_STYLE has a BLACK entry');
  assert.ok(BELT_STYLE.BLACK.bg, 'BLACK chip has a background');
  assert.ok(BELT_STYLE.BLACK.fg, 'BLACK chip has a foreground');
  // Must read as its own colour on dark glass, not blend into CHECK.
  assert.notEqual(BELT_STYLE.BLACK.bg, BELT_STYLE.CHECK.bg, 'BLACK differs from CHECK');
});
