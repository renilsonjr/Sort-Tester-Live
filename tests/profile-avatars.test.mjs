// Choosing a profile icon, and where it shows (issue #272).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { screensSource } from './helpers/screens-source.mjs';

const app = screensSource();
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');
const avatars = readFileSync(new URL('../src/avatars.js', import.meta.url), 'utf8');
const python = readFileSync(new URL('../backend/auth/avatars.py', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

const jsKeys = [...avatars.matchAll(/\['([a-z_]+)', '/g)].map((m) => m[1]);
const pyKeys = [...python.slice(python.indexOf('KEYS = ('), python.indexOf(')', python.indexOf('KEYS = (')))
  .matchAll(/"([a-z_]+)"/g)].map((m) => m[1]);

test('the two lists hold the same keys, in the same order', () => {
  assert.ok(jsKeys.length >= 15);
  assert.deepEqual(jsKeys, pyKeys);
});

test('every key draws exactly one icon, and none repeats', () => {
  const drawn = [...avatars.matchAll(/\['[a-z_]+', '([^']+)'\]/g)].map((m) => m[1]);
  assert.equal(drawn.length, jsKeys.length);
  assert.equal(new Set(drawn).size, jsKeys.length);
});

test('an unknown key draws nothing rather than a broken glyph', () => {
  assert.match(avatars, /BY_KEY\.get\(key\) \?\? ''/);
});

test('Profile offers the choice', () => {
  const settings = fn('async function fillSettings');
  assert.match(settings, /id="profile-avatar"/);
  assert.match(settings, /t\('Profile icon'\)/);
  assert.match(settings, /showAvatarPicker/);
});

test('the picker shows every icon and marks the one in use', () => {
  const picker = fn('function showAvatarPicker');
  assert.match(picker, /AVATARS\.map/);
  assert.match(picker, /aria-pressed/);
  assert.match(picker, /data-avatar="\$\{esc\(key\)\}"/);
});

test('choosing one sends its key, and the choice can be cleared', () => {
  const picker = fn('function showAvatarPicker');
  assert.match(picker, /apiSend\('PUT', '\/auth\/avatar', \{ avatar: /);
  assert.match(picker, /t\('No icon'\)/);
});

test('a refusal is reported, never passed off as a saved choice', () => {
  const picker = fn('function showAvatarPicker');
  assert.match(picker, /result\.ok/);
  assert.match(picker, /t\('That did not work\.'\)/);
});

test('the podium shows the icon instead of the initial', () => {
  const board = fn('async function fillLeaderboard');
  assert.match(board, /avatarEmoji\(row\.avatar\)/);
  // the initial stays as the fallback for a player who never chose
  assert.match(board, /row\.username\.slice\(0, 1\)\.toUpperCase\(\)/);
});

test('the list rows carry it too', () => {
  const board = fn('async function fillLeaderboard');
  const list = board.slice(board.indexOf('const rows = listRows.map'));
  assert.match(list, /avatarEmoji\(row\.avatar\)/);
});

test('the Profile header shows the player their own icon', () => {
  const profile = fn('async function fillProfile');
  assert.match(profile, /paintProfileAvatar\(/);
  assert.match(fn('function paintProfileAvatar'), /avatarEmoji\(key\)/);
});

test('the header draws it from the session, with no extra request', () => {
  const profile = fn('async function fillProfile');
  assert.match(profile, /paintProfileAvatar\(view, account\(\)\?\.avatar\)/);
  // the one /auth/me call is the pre-existing one, for a session without a name
  assert.equal((profile.match(/api\('\/auth\/me'\)/g) || []).length, 1);
});

test('it is imported, not re-listed', () => {
  assert.match(app, /import \{ AVATARS, avatarEmoji \} from '\.\/avatars\.js'/);
  assert.doesNotMatch(app, /'🦊'/);
});

test('every new sentence has Spanish', () => {
  for (const key of ['Profile icon', 'Choose a profile icon', 'No icon', 'Shown on your profile and the leaderboard.']) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(i18n, new RegExp(`'${escaped}': '`), `no Spanish for ${key}`);
  }
});
