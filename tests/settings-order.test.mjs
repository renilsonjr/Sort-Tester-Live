// The order of the Settings rows, set by the owner on 2026-11-25.
//
// It is an order, not a set: a test that only checks each row exists would
// pass while the rows sat in any order at all. So this reads the rendered
// list and compares the sequence.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');

function settings() {
  const start = app.indexOf('async function fillSettings');
  assert.ok(start >= 0, 'fillSettings not found');
  return app.slice(start, app.indexOf('\nfunction ', start + 1));
}

const WANTED = [
  'profile-owner',
  'profile-avatar',
  'profile-change-code',
  'profile-signout-others',
  'profile-support',
  'profile-logout',
  'profile-delete',
];

test('the rows are drawn in the order the owner set', () => {
  const drawn = [...settings().matchAll(/<button id="(profile-[a-z-]+)"/g)].map((m) => m[1]);
  assert.deepEqual(drawn, WANTED);
});

test('Owner tools is first, and hidden until the account is the owner', () => {
  const body = settings();
  assert.match(body, /<button id="profile-owner"[^>]*hidden/);
  // shown from the server's answer, never assumed from the screen
  assert.match(body, /api\('\/auth\/me'\)/);
  assert.match(body, /is_owner/);
});

test('deleting the account is last, and the only row marked apart', () => {
  const body = settings();
  const marked = [...body.matchAll(/<button id="(profile-[a-z-]+)" class="([^"]*)"/g)]
    .filter(([, , cls]) => cls.includes('lab-choice-quiz'))
    .map(([, id]) => id);
  assert.deepEqual(marked, ['profile-delete']);
});

test('every row still does what it says', () => {
  const body = settings();
  for (const [id, call] of [
    ['profile-avatar', 'showAvatarPicker'],
    ['profile-change-code', 'showChangeCode'],
    ['profile-signout-others', 'showSignOutOthers'],
    ['profile-support', 'showSupport'],
    ['profile-logout', 'signOut'],
    ['profile-delete', 'showDeleteAccount'],
    ['profile-owner', 'showOwnerTools'],
  ]) {
    assert.match(body, new RegExp(`#${id}'\\)[\\s\\S]{0,120}${call}`), `${id} no longer calls ${call}`);
  }
});
