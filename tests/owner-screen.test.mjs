// Owner tools (#11, slice 2), built to the screens approved on
// 2026-11-15. The point of most of these is what the screen does NOT do:
// the owner was granted three scoped powers and nothing else, so an
// accidental player browser or points editor should fail a test here.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { screensSource } from './helpers/screens-source.mjs';

const app = screensSource();
const owner = readFileSync(new URL('../src/ownerScreens.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

// The owner's screens are in src/ownerScreens.js, inside a factory, so a
// function there ends two spaces in; one in app.js ends at the margin.
function fn(name) {
  for (const [source, end] of [[owner, '\n  }\n'], [app, '\n}\n']]) {
    const start = source.indexOf(name);
    if (start === -1) continue;
    const body = source.slice(start);
    return body.slice(0, body.indexOf(end));
  }
  return assert.fail(`${name} is missing`);
}

test('the owner row is hidden until the server says who you are', () => {
  const settings = fn('async function fillSettings');
  assert.match(settings, /id="profile-owner"[^>]*hidden/);
  assert.match(settings, /me\?\.is_owner/);
  assert.match(settings, /owner\.hidden = false/);
});

test('the row is absent for a player, not merely disabled', () => {
  // A locked door still says there is a room.
  const settings = fn('async function fillSettings');
  assert.doesNotMatch(settings, /profile-owner'\)\.disabled/);
});

test('Owner tools offers the three scoped powers and nothing else', () => {
  const tools = fn('function showOwnerTools');
  for (const power of ['Prize eligibility', 'Access recovery', 'Case review']) {
    assert.match(tools, new RegExp(power));
  }
  // all three are built now, and each one leads somewhere
  for (const id of ['owner-eligibility', 'owner-recovery', 'owner-cases']) {
    assert.match(tools, new RegExp(`id="${id}"`), id);
  }
  assert.doesNotMatch(tools, /Not built yet/);
  assert.match(tools, /only administrator powers this app has/);
});

test('no player browser, points editor or ban button exists', () => {
  const tools = fn('function showOwnerTools');
  const eligibility = fn('async function fillEligibility');
  for (const forbidden of [/all players/i, /ban\b/i, /suspend/i, /edit points/i, /set points/i, /reset password/i]) {
    assert.doesNotMatch(tools, forbidden);
    assert.doesNotMatch(eligibility, forbidden);
  }
});

test('the owner approves by tag, not by account id', () => {
  const eligibility = fn('async function fillEligibility');
  assert.match(eligibility, /id="elig-tag"/);
  assert.match(eligibility, /Player tag/);
  const send = fn('async function approveSorter');
  assert.match(send, /tag: panel\.querySelector\('#elig-tag'\)\.value/);
});

test('the approved list carries no points and no history', () => {
  const eligibility = fn('async function fillEligibility');
  assert.match(eligibility, /row\.username/);
  assert.match(eligibility, /row\.roster_reference/);
  for (const forbidden of [/row\.points/, /row\.badge/, /row\.history/, /row\.tickets/]) {
    assert.doesNotMatch(eligibility, forbidden);
  }
});

test('a closed season hides the form but keeps the withdrawals', () => {
  const eligibility = fn('async function fillEligibility');
  assert.match(eligibility, /body\.approvals_open \?/);
  assert.match(eligibility, /closed to new approvals/);
  // the list and its Withdraw buttons are outside that conditional
  const afterForm = eligibility.slice(eligibility.indexOf('owner-count'));
  assert.match(afterForm, /owner-withdraw/);
});

test('an empty list explains what it means for the leaderboard', () => {
  assert.match(fn('async function fillEligibility'), /Nobody is approved yet/);
});

test('a server that cannot be reached says nothing has been changed', () => {
  assert.match(fn('async function fillEligibility'), /Could not load the approvals/);
  assert.match(fn('async function apiSend'), /Nothing has been changed/);
});

test('withdrawing asks first, and keeping is the easy answer', () => {
  const confirm = fn('function confirmWithdraw');
  assert.match(confirm, /id="withdraw-keep" class="primary"/);
  assert.match(confirm, /id="withdraw-go" class="ghost owner-danger"/);
  // what it costs, and what it does not
  assert.match(confirm, /cannot win a hat this season/);
  assert.match(confirm, /points, badge and history do not change/);
  assert.match(confirm, /go on playing/);
});

test('a refusal from the server is shown in its own words', () => {
  const send = fn('async function approveSorter');
  assert.match(send, /result\.reason/);
  const helper = fn('async function apiSend');
  assert.match(helper, /data\?\.detail/);
});

test('the owner-only styles exist, with withdraw as the quieter button', () => {
  assert.match(page, /\.owner-danger \{ color: var\(--bad\)/);
  assert.match(page, /\.approved-who b \{ display: block; font-weight: 900; overflow-wrap: anywhere; \}/);
});

test('a roster reference is escaped before it reaches the page', () => {
  assert.match(fn('async function fillEligibility'), /esc\(row\.roster_reference\)/);
  assert.match(fn('async function fillEligibility'), /esc\(row\.username\)/);
});
