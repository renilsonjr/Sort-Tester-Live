// The owner deleting an account that should not exist (issue #271).
//
// Two steps on purpose: the owner types a tag and reads back who it is,
// before anything is deleted. The screen never deletes on the first press.
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

test('Owner tools offers it, and says what it is for', () => {
  const tools = fn('function showOwnerTools');
  assert.match(tools, /id="owner-delete"/);
  assert.match(tools, /t\('Delete an account'\)/);
  assert.match(tools, /t\('Remove a test, duplicate or former sorter’s account\.'\)/);
  assert.match(tools, /showOwnerDeleteAccount/);
});

test('it asks for a tag and looks it up before deleting anything', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /id="od-tag"/);
  assert.match(screen, /id="od-look"/);
  assert.match(screen, /apiSendOwner\('POST', '\/ranked\/owner\/deletions\/lookup'/);
});

test('the account is shown and checked before the deletion is offered', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /id="od-found"/);
  assert.match(screen, /found\.username/);
  assert.match(screen, /found\.tag/);
  assert.match(screen, /found\.finished_attempts/);
  assert.match(screen, /found\.approved_for_prizes/);
  // the delete control exists only once an account has been read back
  assert.ok(
    screen.indexOf('id="od-found"') < screen.indexOf('id="od-go"'),
    'the delete button is not behind the look-up',
  );
});

test('it warns that this changes the leaderboard when the account has played', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /t\('{count} finished Ranked matches will leave the leaderboard\.', \{ count:/);
  assert.match(screen, /t\('This account is approved for prizes this season\.'\)/);
});

test('deleting needs a deliberate acknowledgement', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /id="od-ack"/);
  assert.match(screen, /t\('I understand this cannot be undone\.'\)/);
  assert.match(screen, /acknowledge: true/);
  assert.match(screen, /apiSendOwner\('POST', '\/ranked\/owner\/deletions'/);
});

test('it reports the outcome, and a refusal as a refusal', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /t\('Account deleted\.'\)/);
  assert.match(screen, /result\.ok/);
  assert.match(screen, /result\.reason/);
});

test('the name and tag come from the server, escaped', () => {
  const screen = fn('function showOwnerDeleteAccount');
  assert.match(screen, /esc\(found\.username\)/);
  assert.match(screen, /esc\(found\.tag\)/);
});

test('every sentence has Spanish', () => {
  for (const key of [
    'Delete an account',
    'Remove a test, duplicate or former sorter’s account.',
    'Player tag',
    'Look up',
    'I understand this cannot be undone.',
    'Account deleted.',
    '{count} finished Ranked matches will leave the leaderboard.',
    'This account is approved for prizes this season.',
    'Deleting removes the account, its points and its history. It cannot be undone.',
  ]) {
    const escaped = key.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    assert.match(i18n, new RegExp(`'${escaped}': '`), `no Spanish for ${key}`);
  }
});
