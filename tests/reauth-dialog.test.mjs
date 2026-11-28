// The login-ID prompt for the owner's guarded actions (#11 box 5).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
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

test('a 428 asks for the Quiz Code and repeats the action exactly once', () => {
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
  assert.match(owner, /apiSendOwner\('POST', '\/ranked\/owner\/approvals'/);
  assert.match(owner, /apiSendOwner\('DELETE', `\/ranked\/owner\/approvals\//);
  assert.match(owner, /apiSendOwner\('POST', `\/ranked\/owner\/recoveries\/\$\{request\.id\}\/handover`\)/);
});

test('the Quiz Code field cannot be read over the owner’s shoulder', () => {
  const dialog = fn('function askForLoginId');
  assert.match(dialog, /type="password"/);
  // and a password manager can fill it, which is where the owner keeps it
  assert.match(dialog, /autocomplete="current-password"/);
});

test('the typed Quiz Code is cleared as soon as it is sent', () => {
  assert.match(fn('function askForLoginId'), /input\.value = ''/);
});

test('the prompt says what confirming buys, and for how long', () => {
  assert.match(fn('function askForLoginId'), /five minutes/);
});

test('too many tries is told apart from a wrong Quiz Code', () => {
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
