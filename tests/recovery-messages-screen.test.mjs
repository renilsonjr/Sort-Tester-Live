// The owner's recovery-message inbox (issue #251). A message is typed by
// somebody who is not signed in, so the screen treats it as untrusted text
// and says plainly that it proves nothing.
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

test('Owner tools reaches the inbox and says when something is waiting', () => {
  const tools = fn('function showOwnerTools');
  assert.match(tools, /id="owner-messages"/);
  assert.match(tools, /addEventListener\('click', \(\) => showRecoveryMessages\(\)\)/);
  assert.match(tools, /\/ranked\/owner\/recovery-messages/);
  assert.match(tools, /owner-messages-count/);
});

test('message text is escaped, never rendered as markup', () => {
  const list = fn('async function fillRecoveryMessages');
  assert.match(list, /esc\(row\.body\)/);
  assert.doesNotMatch(list, /\$\{row\.body\}/);
});

test('the screen says a message proves nothing and where recovery happens', () => {
  const screen = fn('function showRecoveryMessages');
  assert.match(screen, /proves nothing about who wrote it/);
  assert.match(screen, /Access recovery/);
  assert.match(screen, /showRecovery\(\)/);
});

test('resolving is one call without the reauth gate, and reloads the list', () => {
  const list = fn('async function fillRecoveryMessages');
  assert.match(list, /apiSend\('POST', `\/ranked\/owner\/recovery-messages\/\$\{.+\}\/resolve`\)/);
  assert.doesNotMatch(list, /apiSendOwner/);
  assert.match(list, /fillRecoveryMessages\(panel\)/);
});

test('the list shows text and dates, and nothing about any account', () => {
  const list = fn('async function fillRecoveryMessages');
  for (const forbidden of [/row\.username/, /row\.tag/, /row\.points/, /login_id/]) {
    assert.doesNotMatch(list, forbidden);
  }
  assert.match(list, /row\.created_at/);
  assert.match(list, /row\.resolved_at/);
});

test('a server that cannot be reached says nothing has been changed', () => {
  assert.match(fn('async function fillRecoveryMessages'), /Nothing has been changed/);
});

test('every new owner-screen sentence has a Spanish translation', () => {
  for (const sentence of [
    'Recovery messages',
    'Left on the sign-in screen by people who are locked out.',
    'A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.',
    'Open Access recovery',
    'Mark as resolved',
    'No messages.',
    'resolved',
    'received',
    'Could not load the messages. Nothing has been changed.',
    '1 message waiting.',
    'messages waiting.',
  ]) {
    assert.ok(i18n.includes(`'${sentence}':`), `no Spanish for: ${sentence}`);
  }
});
