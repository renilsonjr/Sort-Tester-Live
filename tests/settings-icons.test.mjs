// Round 3: #381, the Settings rows drew their icons with plain text
// characters while every other row in the app uses a hand-drawn SVG.
//
// Measured in the running app at 375 and 1440, night and day, EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');

const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const js = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#381 the six Settings rows draw an icon, not a character', () => {
  // They were a star, a question mark, an arrow, a circle, two squares and
  // an exclamation mark -- drawn by whatever font each phone falls back to.
  // Anchored on the function, not on a character offset.
  const start = js.indexOf('async function fillSettings');
  assert.notEqual(start, -1, 'fillSettings is gone');
  // Searched FROM the function: "Delete account" also appears earlier, on
  // the deletion screen, which made the slice empty.
  const settings = js.slice(start, js.indexOf("t('Delete account')", start) + 300);
  for (const name of ['owner', 'support', 'logOut', 'avatar', 'devices', 'deleteAccount']) {
    assert.match(settings, new RegExp(`<span class="lab-choice-icon" aria-hidden="true">\\$\\{ICONS\\.${name}\\}</span>`),
      `the ${name} row still has no icon`);
  }
  for (const ch of ['★', '↪', '○', '⧉']) {
    assert.ok(!settings.includes(ch), `${ch} is back in the Settings rows`);
  }
});

test('#381 they are on the same grid and stroke as the dock', () => {
  // Not a second icon set: 24x24, and the shared rule gives them the stroke.
  for (const name of ['owner', 'support', 'logOut', 'avatar', 'devices', 'deleteAccount']) {
    assert.match(js, new RegExp(`\\n  ${name}: '<svg viewBox="0 0 24 24">`), `ICONS.${name} is not on the grid`);
  }
  assert.match(css, /\.lab-nav i svg,[^{]*\.lab-choice-icon svg[^{]*\{[^}]*stroke: currentColor/);
});

test('#381 a screen reader no longer reads the decoration', () => {
  // The character spans had no aria-hidden, unlike every ICONS one, so a
  // screen reader announced "star Owner tools", "question mark Support".
  const start = js.indexOf('async function fillSettings');
  // Searched FROM the function: "Delete account" also appears earlier, on
  // the deletion screen, which made the slice empty.
  const settings = js.slice(start, js.indexOf("t('Delete account')", start) + 300);
  assert.doesNotMatch(settings, /<span class="lab-choice-icon">/);
});

test('#381 the dead avatar slot is gone', () => {
  // The circle carried id="profile-avatar-now", which nothing in the app
  // ever wrote to -- paintProfileAvatar fills #profile-avatar-mark, in the
  // identity card. Checked across every source file before removing it.
  assert.doesNotMatch(js, /profile-avatar-now/);
  assert.match(js, /mark\.textContent = avatarEmoji\(key\)/);
  assert.match(js, /#profile-avatar-mark/);
});

test('#381 the rows it left behind were taken deliberately, not swept', () => {
  // This test used to assert the opposite: that the owner menu, Support and
  // the tie-break still held their character icons, so that #381 could not
  // quietly widen into screens round 3 had not walked. They got their own
  // sub-issue, #404 walked them and drew them, so the thing being guarded
  // is now that none of them came back. Same intent, other end of it:
  // tests/character-icons.test.mjs holds the detail.
  assert.doesNotMatch(js, /<span class="lab-choice-icon">✓<\/span>/);
  assert.doesNotMatch(js, /<span class="lab-choice-icon">\+<\/span>/);
});
