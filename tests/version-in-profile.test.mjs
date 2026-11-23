// The version shown in Profile (issue #274).
//
// It is read from /health, not written into the page, so what a player reads
// is the version actually serving them — not the one that happened to be in
// the file when the page was built.
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

test('Settings carries the line', () => {
  const settings = fn('async function fillSettings');
  assert.match(settings, /id="profile-version"/);
});

test('the number comes from the server, not from the page', () => {
  const settings = fn('async function fillSettings');
  assert.match(settings, /fetch\('\/health'/);
  assert.doesNotMatch(app, /0\.1\.0/, 'a version number is hard-coded in the app');
});

test('it asks the route where /health actually is', () => {
  // api() prefixes /api, and /health is not under it: api('/health') 404s.
  // This was the first way it was written, and the line came up empty.
  // without stripping comments this matches the note that explains the bug
  const code = fn('async function fillSettings')
    .split('\n').filter((line) => !/^\s*\/\//.test(line)).join('\n');
  assert.doesNotMatch(code, /api\('\/health'\)/);
});

test('it says nothing at all when the server does not answer', () => {
  // an unreachable server must not leave a half-written line on screen
  const settings = fn('async function fillSettings');
  assert.match(settings, /catch/);
});

test('the label has Spanish', () => {
  assert.match(i18n, /'Version': '/);
});
