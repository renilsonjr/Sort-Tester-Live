// Round 4: #420 and #421, both on the Tickets screen and both in
// fillSupport, so they land together.
//
// #420: three paragraphs, 88 words, 284px of retention policy between the
// title and the only control. Measured at 375x812: the title ended at y=186
// and the Create ticket row began at y=470. After: 110px, the row at y=296,
// with every word of the policy kept, below it.
//
// #421: a ticket is about a Ranked attempt, so a player with none was sent
// to a screen that could only say so and offer Cancel, with 435px of empty
// space. The row is the dashed, half-lit .lab-choice.locked the deck picker
// already uses, and it carries the sentence the dead end used to say.
// Walked all three branches in the app: no attempts -> locked; one attempt
// -> live with its arrow; /ranked/history refused -> live.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

const fill = (() => {
  const start = app.indexOf('async function fillSupport(');
  assert.notEqual(start, -1, 'fillSupport is gone');
  const next = app.indexOf('\nasync function ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
})();

const RETENTION = 'Only you can see your tickets. When a ticket is closed';

test('#420 the action comes before the policy', () => {
  const row = fill.indexOf('id="support-create"');
  const locked = fill.indexOf('class="lab-choice locked"');
  const policy = fill.indexOf(RETENTION);
  assert.ok(row !== -1 && locked !== -1, 'the create row is gone');
  assert.ok(policy > row && policy > locked, 'the retention policy is still above the action');
});

test('#420 the policy keeps every word', () => {
  // Moved, not trimmed: both sentences are still on this screen.
  assert.ok(fill.includes(RETENTION));
  assert.ok(fill.includes('Opening a ticket never changes your points or your access.'));
});

test('#421 the row locks when there is nothing to write about', () => {
  assert.match(fill, /\$\{canCreate \? `/);
  assert.match(fill, /<div class="lab-choice locked">/);
  // It says why, in the words the dead-end screen used.
  assert.match(fill, /t\('A ticket is about a Ranked attempt, and you have none yet\.'\)/);
});

test('#421 a locked row has no arrow and is not a button', () => {
  const lockedAt = fill.indexOf('<div class="lab-choice locked">');
  const block = fill.slice(lockedAt, fill.indexOf('</div>', lockedAt));
  assert.doesNotMatch(block, /lab-arrow/);
  assert.doesNotMatch(block, /<button/);
});

test('#421 it fails open when the history request does not land', () => {
  // `api` answers null for a request that did not land. A support screen
  // must not lock its only action because a second request failed.
  assert.match(fill, /const canCreate = history === null \|\| history\.length > 0;/);
});

test('#421 the second request costs no extra wall time', () => {
  assert.match(fill, /await Promise\.all\(\[support\.listTickets\(\), api\('\/ranked\/history'\)\]\)/);
});

test('#421 the click binding tolerates a locked row', () => {
  assert.match(app, /panel\.querySelector\('#support-create'\)\?\.addEventListener\('click', showCreateTicket\);/);
});

test('#421 the sentence it borrows already has Spanish', () => {
  assert.match(i18n, /'A ticket is about a Ranked attempt, and you have none yet\.': '/);
});
