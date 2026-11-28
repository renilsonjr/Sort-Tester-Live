// Round 4: #424. On the profile-icon screen "No icon" and "Back" were
// pixel-identical full-width ghosts, stacked, with the one that CLEARS your
// icon on top. Measured in the running app at 375x812 -- both 335x52, same
// background rgba(56,38,27,0.5), same border, same weight 900.
//
// #331 introduced the compact .lab-back for a sub-screen's way out and #385
// put it on the leaderboard; this screen never got it. Measured after: Back
// is 77x44 at the top, "No icon" is the only full-width button left.
//
// #423 was filed from the same screen and closed instead: the chosen icon's
// mark is a 3px gold ring (1px border + a 2px inset shadow I had missed),
// not the weak 1px border I reported.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { screensSource } from './helpers/screens-source.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = screensSource();

const picker = (() => {
  const start = app.indexOf('function showAvatarPicker(');
  assert.notEqual(start, -1, 'showAvatarPicker is gone');
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
})();

test('#424 the way out is the compact Back, first on the screen', () => {
  assert.match(picker, /<section class="lab-screen">[\s\S]{0,400}?\$\{backLink\('av-back'\)\}/);
});

test('#424 the old full-width Back is gone', () => {
  assert.doesNotMatch(picker, /<button id="av-back" class="ghost"/);
});

test('#424 "No icon" is the only full-width button left', () => {
  const ghosts = picker.match(/<button id="av-[a-z]+" class="ghost"/g) ?? [];
  assert.deepEqual(ghosts, ['<button id="av-none" class="ghost"']);
});

test('#424 the id is kept, so the handler still finds it', () => {
  // backLink takes the id, so the existing listener binds to the same node.
  // Walked in the app: Back returns to Settings.
  assert.match(picker, /view\.querySelector\('#av-back'\)/);
});

test('#423 the chosen icon keeps its ring', () => {
  // Measured, not guessed: border plus a 2px inset shadow. Pinned because
  // the issue that asked to change it was wrong about what it measures.
  const html = readFileSync(join(root, 'index.html'), 'utf8');
  assert.match(html, /\.avatar-pick\[aria-pressed="true"\] \{ border-color: var\(--gold\); box-shadow: inset 0 0 0 2px var\(--gold\); \}/);
});
