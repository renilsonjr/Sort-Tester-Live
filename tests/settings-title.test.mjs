// Round 3: #389. The Settings screen borrowed the Profile overview's header,
// so its eyebrow said PROFILE and its h1 was the player's username. Measured
// against main at 375x812: the screen's own text did not contain the word
// "Settings" anywhere -- the only clue was the gear chip in the sub-header,
// which is the control that opened it.
//
// Every other screen is eyebrow + title (Ranked / Leaderboard, Practice /
// Pick a test), and Settings' OWN sub-screens already use "Settings" as their
// eyebrow. This completes that ladder: Profile > Settings > Sign out my
// other devices.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { screensSource } from './helpers/screens-source.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = screensSource();
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

function body(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} is gone`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
}

const profile = body('showProfile');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#389 Settings has a title of its own', () => {
  // The branch widened in #414, which gave the history a title the same
  // way, so it now reads "any tab but the overview" and picks the word.
  // Same intent: Settings names itself and does not borrow the username.
  assert.match(profile, /\$\{tab !== 'overview' \? `/);
  assert.match(profile, /t\(tab === 'settings' \? 'Settings' : 'Ranked history'\)/);
});

test('#389 the eyebrow still names the section', () => {
  // Eyebrow = where you are, title = what this screen is. Settings' own
  // children then use "Settings" as THEIR eyebrow, which is the ladder.
  assert.match(profile, /<p class="lab-eyebrow">\$\{esc\(t\('Profile'\)\)\}<\/p>/);
  assert.match(app, /<p class="lab-eyebrow">\$\{esc\(t\('Settings'\)\)\}<\/p>\s*<h1 class="lab-title">\$\{esc\(t\('Sign out other devices'\)\)\}<\/h1>/);
});

test('#389 the overview keeps its identity card', () => {
  // The badge, icon, username and tag belong to the overview. Only the
  // Settings branch drops them, and Back goes back to them.
  assert.match(profile, /<div class="pf-ident">/);
  assert.match(profile, /<h1 class="lab-title" id="profile-name">/);
});

test('#389 the late /auth/me fill tolerates a page without those nodes', () => {
  // It used to write straight into #profile-name and #profile-tag. On the
  // Settings tab neither exists now, which would throw on the one path that
  // asks the server.
  const fill = body('fillProfile');
  assert.doesNotMatch(fill, /view\.querySelector\('#profile-name'\)\.textContent/);
  assert.match(fill, /if \(nameEl\) nameEl\.textContent = me\.username;/);
  assert.match(fill, /if \(tagEl2\) tagEl2\.textContent/);
});

test('#389 the gear chip goes where it would lead nowhere', () => {
  // It opens Settings. On Settings it re-renders the screen you are on, and
  // with the title there the word appeared twice, 150px apart.
  assert.match(profile, /if \(tab === 'settings'\) view\.querySelector\('#top-settings'\)\?\.remove\(\);/);
  // It is still drawn for the other profile tabs.
  assert.match(app, /id="top-settings"/);
});

test('#389 the title has Spanish', () => {
  assert.match(i18n, /'Settings': 'Ajustes',/);
});
