// The Profile overview must show the real Best Ranked and Place from
// /ranked/profile/stats (issue #218), not a hard-coded dash, and its stat
// labels must be translated like the rest of the app.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { practiceCountLabel } from '../src/shiftLog.js';
import { screensSource } from './helpers/screens-source.mjs';

const app = screensSource();
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function overview() {
  const start = app.indexOf('async function fillOverview');
  assert.ok(start >= 0, 'fillOverview not found');
  const end = app.indexOf('\nasync function fillHistory');
  return app.slice(start, end);
}

test('the overview loads the profile stats endpoint', () => {
  assert.match(overview(), /\/ranked\/profile\/stats/);
});

test('Best Ranked shows the correct-of-total count, not only a dash', () => {
  const body = overview();
  assert.match(body, /best_ranked/);
  // the correct count and the total both reach the tile
  assert.match(body, /\.correct/);
  assert.match(body, /\.total/);
});

test('Place shows the leaderboard place from the stats', () => {
  assert.match(overview(), /\.place/);
});

test('every Profile stat label has a Spanish translation', () => {
  for (const label of ['Points', 'Best Ranked', 'Practices', 'Place', 'See history', 'Your climb']) {
    assert.ok(app.includes(`t('${label}')`), `app.js does not use t('${label}')`);
    assert.ok(i18n.includes(`'${label}': '`), `no Spanish for: ${label}`);
  }
});

test('Practices counts this device\'s finished sessions, not a dash', () => {
  const body = overview();
  assert.match(body, /practiceCountLabel\(log\.all\(\)\)/);
  // The note under the tiles -- "Practices counts the sessions in the Shift
  // log on this device." -- was removed with the other sub-labels. What the
  // test still guards is the part that was ever load-bearing: the number is
  // the length of THIS device's log, not a server count, so it reads from
  // log.all() above. The sentence explaining that is gone from the screen.
  const note = 'Practices counts the sessions in the Shift log on this device.';
  assert.ok(!body.includes(`t('${note}')`));
  assert.ok(!i18n.includes(`'${note}': '`));
});

test('the Practices number is the log length, and a full log says so', () => {
  assert.equal(practiceCountLabel([]), '0');
  assert.equal(practiceCountLabel([{}, {}, {}]), '3');
  assert.equal(practiceCountLabel(new Array(199).fill({})), '199');
  assert.equal(practiceCountLabel(new Array(200).fill({})), '200+');
  assert.equal(practiceCountLabel(null), '0');
});
