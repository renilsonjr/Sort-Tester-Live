// The owner's access-recovery screen (#11, box 2), built to the screen
// approved on 2026-11-15. Most of these hold promises about what the
// screen SAYS, because the thing that matters most here cannot be checked
// by any code: that the person in front of the owner is who they claim.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('Owner tools reaches recovery, and it is no longer a stub', () => {
  const tools = fn('function showOwnerTools');
  assert.match(tools, /id="owner-recovery"/);
  assert.doesNotMatch(tools, /Access recovery'\)\}<\/strong><small>\$\{esc\(t\('In person only\. Not built yet/);
  assert.match(fn('function showOwnerTools'), /addEventListener\('click', \(\) => showRecovery\(\)\)/);
});

test('finding an account is a separate step from issuing anything', () => {
  // Opening a recovery asserts nothing; it must not hand over a login ID.
  const find = fn('async function findForRecovery');
  assert.match(find, /POST', '\/ranked\/owner\/recoveries'/);
  assert.doesNotMatch(find, /handover/);
  assert.match(find, /showRecoveryCheck/);
});

test('the second step says what the screen cannot prove', () => {
  const check = fn('function showRecoveryCheck');
  assert.match(check, /Check in person first/);
  assert.match(check, /Nothing on this screen proves who is standing in front of you/);
  assert.match(check, /username and tag are public, so neither is evidence/);
});

test('the button says what pressing it asserts', () => {
  const check = fn('function showRecoveryCheck');
  assert.match(check, /I have checked them in person/);
  // not a bare Confirm, which would ask for agreement rather than a claim
  assert.doesNotMatch(check, />\$\{esc\(t\('Confirm'\)\)\}</);
});

test('the second step says what a handover costs before it happens', () => {
  const check = fn('function showRecoveryCheck');
  assert.match(check, /signs them out everywhere/);
  assert.match(check, /points, badge and history do not change/);
  assert.match(check, /approves nothing for prizes/);
});

test('the login ID is shown once and the screen says so', () => {
  const shown = fn('function showHandover');
  assert.match(shown, /shown once and cannot be shown again/);
  assert.match(shown, /every signed-in device stopped working/);
});

test('the handover screen never stores or re-fetches the login ID', () => {
  const shown = fn('function showHandover');
  assert.doesNotMatch(shown, /localStorage|sessionStorage|api\(|apiSend\(/);
});

test('the login ID is readable at arm’s length', () => {
  assert.match(page, /\.handover-id \{ font: 900 26px/);
  assert.match(page, /user-select: all/);
});

test('a refusal is shown in the server’s own words, not guessed at', () => {
  const check = fn('function showRecoveryCheck');
  assert.match(check, /result\.reason/);
  const find = fn('async function findForRecovery');
  assert.match(find, /result\.reason/);
});

test('the recent list says who and when, and nothing about playing', () => {
  const list = fn('async function fillRecoveries');
  assert.match(list, /row\.username/);
  assert.match(list, /not completed/);
  for (const forbidden of [/row\.points/, /row\.badge/, /login_id/, /row\.history/]) {
    assert.doesNotMatch(list, forbidden);
  }
});

test('a server that cannot be reached says nothing has been changed', () => {
  assert.match(fn('async function fillRecoveries'), /Nothing has been changed/);
});

test('names and tags are escaped before they reach the page', () => {
  assert.match(fn('async function fillRecoveries'), /esc\(row\.username\)/);
  assert.match(fn('function showHandover'), /esc\(handover\.login_id\)/);
  assert.match(fn('function showRecoveryCheck'), /esc\(request\.username\)/);
});
