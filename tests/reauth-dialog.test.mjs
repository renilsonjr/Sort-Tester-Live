// The login-ID prompt for the owner's guarded actions (#11 box 5).
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

test('a 428 asks for the login ID and repeats the action exactly once', () => {
  const owner = fn('async function apiSendOwner');
  assert.match(owner, /first\.status !== 428/);
  assert.match(owner, /askForLoginId/);
  assert.equal((owner.match(/apiSend\(method, path, body\)/g) || []).length, 2,
    'one first try and one retry, never a loop');
});

test('cancelling changes nothing and says so', () => {
  assert.match(fn('async function apiSendOwner'), /Cancelled\. Nothing has been changed/);
});

test('the three guarded actions go through the prompt', () => {
  assert.match(app, /apiSendOwner\('POST', '\/ranked\/owner\/approvals'/);
  assert.match(app, /apiSendOwner\('DELETE', `\/ranked\/owner\/approvals\//);
  assert.match(app, /apiSendOwner\('POST', `\/ranked\/owner\/recoveries\/\$\{request\.id\}\/handover`\)/);
});

test('the login ID field cannot be read over the owner’s shoulder', () => {
  const dialog = fn('function askForLoginId');
  assert.match(dialog, /type="password"/);
  // and a password manager can fill it, which is where the owner keeps it
  assert.match(dialog, /autocomplete="current-password"/);
});

test('the typed login ID is cleared as soon as it is sent', () => {
  assert.match(fn('function askForLoginId'), /input\.value = ''/);
});

test('the prompt says what confirming buys, and for how long', () => {
  assert.match(fn('function askForLoginId'), /five minutes/);
});

test('too many tries is told apart from a wrong login ID', () => {
  assert.match(fn('function askForLoginId'), /result\.status === 429/);
});

test('the prompt is announced as a dialog', () => {
  const dialog = fn('function askForLoginId');
  assert.match(dialog, /role', 'dialog'/);
  assert.match(dialog, /aria-modal', 'true'/);
});

test('the dialog styles exist', () => {
  assert.match(page, /\.reauth-dialog \{ position: fixed/);
  assert.match(page, /\.reauth-card \{/);
});
