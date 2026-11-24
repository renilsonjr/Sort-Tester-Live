// Round 5: #426. Leaving a Ranked run by a dock tab replaced the screen but
// left the attempt's heartbeat running, once a second, for as long as the
// page stayed open. The server closes an attempt 15 seconds after its last
// beat, so the attempt never went quiet, never closed, and every new one
// came back 409 while "Preparing your next match" promised "a few seconds".
//
// Measured in the running app at 375x812, signed in:
//   before -- 13 beats in 12s minutes after leaving, POST /ranked/attempts
//             409 on every retry, the screen never clearing
//   after  -- 0 beats in 6s after the dock tap, and the next attempt starts
//             on its own 9s later, unattended
//
// And the screens that must KEEP it, measured at 4 beats in 4s each: the
// question, the feedback between questions, and the quit confirmation --
// whose "Continue quiz" goes back to the question, so a stopped beat there
// would have let the server close a match the player is still playing.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');

function body(name) {
  const start = app.search(new RegExp(`(async )?function ${name}\\(`));
  assert.notEqual(start, -1, `${name} is gone`);
  const next = app.indexOf('\nfunction ', start + 1);
  const nextAsync = app.indexOf('\nasync function ', start + 1);
  const end = Math.min(next === -1 ? app.length : next, nextAsync === -1 ? app.length : nextAsync);
  return app.slice(start, end);
}

test('#426 a screen without the marker ends the attempt', () => {
  const render = body('render');
  assert.match(render, /if \(!node\.querySelector\?\.\('\[data-attempt-live\]'\)\) endLiveAttempt\(\);/);
});

test('#426 the attempt is held where any screen can end it', () => {
  // Not in the screen that started it: the screen that ends it may be any
  // other -- a dock tab, a deep link, a session that expires.
  assert.match(app, /let liveAttempt = null;/);
  assert.match(app, /function holdLiveAttempt\(attempt\) \{ liveAttempt = attempt; \}/);
});

test('#426 ending clears the reference before stopping', () => {
  // So a stop() that renders cannot come back round into this.
  const fn = app.slice(app.indexOf('function endLiveAttempt()'), app.indexOf('function endLiveAttempt()') + 240);
  assert.ok(fn.indexOf('liveAttempt = null') < fn.indexOf('going.stop()'), 'stop runs before the reference is cleared');
});

test('#426 both heartbeats are held', () => {
  // Ranked and the tie-break each start one.
  assert.equal((app.match(/attempt\.startHeartbeat\(\);\s*\n\s*holdLiveAttempt\(attempt\);/g) ?? []).length, 2);
});

test('#426 every screen the attempt runs behind carries the marker', () => {
  // The question, the feedback between questions, the quit confirmation and
  // the tie-break round. Counted, so a new one cannot be added without a
  // decision about the beat.
  const marked = app.match(/<section class="lab-screen"[^>]*data-attempt-live>/g) ?? [];
  assert.equal(marked.length, 4, `expected 4 marked screens, found ${marked.length}`);
  assert.match(body('showQuitConfirm'), /<section class="lab-screen" data-attempt-live>/);
  assert.match(app, /<section class="lab-screen" id="tb-play" data-attempt-live>/);
  assert.match(app, /<section class="lab-screen" id="rq-play" data-ranked-music data-attempt-live>/);
});

test('#426 the result screen is not marked', () => {
  // It is where an attempt has finished, so the beat must end there.
  assert.doesNotMatch(body('showRankedResult'), /data-attempt-live/);
});
