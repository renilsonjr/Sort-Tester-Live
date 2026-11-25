// "Sign out my other devices" in Profile (issue #270).
//
// The investigation found that an account may be signed in on five devices
// at once, on purpose, and that a player who feared somebody else had their
// Quiz Code had no remedy of their own. This is it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('Profile offers it, next to Log out', () => {
  const settings = fn('async function fillSettings');
  assert.match(settings, /id="profile-signout-others"/);
  assert.match(settings, /t\('Sign out my other devices'\)/);
  // The sentence used to be repeated on the row as well. It was removed
  // there with the other sub-labels, and it is NOT lost: the screen the
  // row opens carries the same words before anything happens, which is
  // where the person is when they have to decide. Asserted there now.
  assert.doesNotMatch(settings, /t\('Ends every other phone or computer/);
  const screen = fn('function showSignOutOthers');
  assert.match(screen, /t\('Ends every other phone or computer signed in to your account\. This one stays\.'\)/);
  assert.ok(
    settings.indexOf('profile-signout-others') > settings.indexOf('profile-logout'),
    'it sits after Log out, not before it',
  );
  assert.match(settings, /showSignOutOthers/);
});

test('it asks before doing anything', () => {
  const screen = fn('function showSignOutOthers');
  assert.match(screen, /id="signout-others-go"/);
  assert.match(screen, /id="signout-others-cancel"/);
  assert.match(screen, /t\('Your Quiz Code keeps working\. Anyone using it elsewhere has to enter it again\.'\)/);
});

test('it says what to do when somebody else knows the Quiz Code', () => {
  const screen = fn('function showSignOutOthers');
  assert.match(screen, /t\('If someone else knows your Quiz Code, ask the owner in person for a new one\.'\)/);
});

test('it goes through the Quiz Code gate and the right route', () => {
  const screen = fn('function showSignOutOthers');
  // apiSendOwner is the wrapper that answers the server's 428 by asking for
  // the Quiz Code and trying once more
  assert.match(screen, /apiSendOwner\('POST', '\/auth\/sessions\/revoke-others'\)/);
});

test('it says what happened, including when there was nothing to end', () => {
  const screen = fn('function showSignOutOthers');
  assert.match(screen, /result\.data\?\.ended/);
  assert.match(screen, /t\('No other device was signed in\.'\)/);
  // one device and several are different sentences, chosen inside t(...)
  const counted = screen.slice(screen.indexOf('t(ended === 1'));
  assert.match(counted, /'{count} other device was signed out\.'/);
  assert.match(counted, /'{count} other devices were signed out\.'/);
  assert.match(counted, /\{ count: ended \}/);
});

test('a refusal is reported, never passed off as success', () => {
  const screen = fn('function showSignOutOthers');
  assert.match(screen, /result\.ok/);
  assert.match(screen, /t\('Nothing was changed\.'\)/);
  // and it does not wear the colour of a result that worked
  assert.match(screen, /said\.classList\.remove\('done'\)/);
  assert.match(screen, /said\.classList\.add\('done'\)/);
});

test('every sentence has Spanish', () => {
  for (const key of [
    'Sign out my other devices',
    'Ends every other phone or computer signed in to your account. This one stays.',
    'Your Quiz Code keeps working. Anyone using it elsewhere has to enter it again.',
    'If someone else knows your Quiz Code, ask the owner in person for a new one.',
    'No other device was signed in.',
    '{count} other device was signed out.',
    '{count} other devices were signed out.',
    'Nothing was changed.',
  ]) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(i18n, new RegExp(`'${escaped}': '`), `no Spanish for ${key}`);
  }
});
