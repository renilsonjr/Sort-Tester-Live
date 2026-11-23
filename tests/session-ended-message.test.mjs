// What a device is told when its session ends (issue #270, last box).
//
// Since "Sign out my other devices" exists, a 401 from the server no longer
// means "this phone sat untouched": it can equally mean the player ended
// this device from another one. The page cannot tell which, and the server's
// 401 does not say, so it must not name a reason it does not know. The app's
// own idle timer does know, and keeps saying so.
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

test('a 401 from the server blames nothing it cannot know', () => {
  const api = fn('async function apiRead');
  assert.match(api, /response\.status === 401 && signedIn\(\)/);
  assert.match(api, /t\('Your session ended\. Log in to carry on\.'\)/);
  assert.doesNotMatch(api, /sat untouched/);
  // and the sentence that named a reason is gone from the app entirely
  assert.doesNotMatch(app, /Your session ended because the app sat untouched/);
});

test('the app’s own idle timer still says it was idleness', () => {
  const idle = fn('function checkIdle');
  assert.match(idle, /t\('You were logged out because the app sat untouched for 15 minutes\.'\)/);
});

test('the neutral sentence has Spanish', () => {
  assert.match(i18n, /'Your session ended\. Log in to carry on\.': '/);
});
