// A server that does not answer at all is a different failure from one that
// answers badly, and it used to be the one nothing handled: fetch rejects,
// the promise behind the screen rejects with it, and the screen sits on
// "Loading..." for ever with no notice and no way to retry. Found while
// walking issue #10 against a real server.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

async function load(name) {
  const source = readFileSync(new URL(`../src/${name}`, import.meta.url), 'utf8');
  return import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);
}

const unreachable = () => {
  globalThis.fetch = async () => {
    throw new TypeError('Failed to fetch');
  };
};

test('support.js answers a dead server instead of throwing', async () => {
  const support = await load('support.js');
  unreachable();
  for (const call of [
    () => support.listTickets(),
    () => support.createTicket('attempt-1', 'It cut out.'),
    () => support.readTicket('ticket-1'),
  ]) {
    const result = await call();
    assert.equal(result.ok, false);
    // Status 0 says no answer came back, which is not any HTTP status.
    assert.equal(result.status, 0);
    assert.equal(result.data, null);
  }
});

test('auth.js answers a dead server instead of throwing', async () => {
  const auth = await load('auth.js');
  unreachable();
  for (const call of [
    () => auth.loginWithId('ABCD-EFGH-JKLM-NPQR'),
    () => auth.registerAccount('walker_1'),
    () => auth.logout(),
    () => auth.fetchMe(),
  ]) {
    const result = await call();
    assert.equal(result.ok, false);
    assert.equal(result.status, 0);
  }
});

test('a dead server never tells the player their Quiz Code is wrong', async () => {
  const source = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
  // The message for status 0 has to be the one about reaching the server:
  // blaming a correct Quiz Code sends people to re-type a good credential.
  assert.match(source, /status === 0/);
  assert.match(source, /Could not reach the server\. Your Quiz Code is fine/);
  assert.match(source, /Could not reach the server\. Nothing was created/);
});

test('app.js returns null for a dead server so screens show their notice', () => {
  const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  const helper = source.slice(source.indexOf('async function apiRead(path)'));
  const body = helper.slice(0, helper.indexOf('\n}\n'));
  assert.match(body, /try \{/);
  assert.match(body, /catch \{\s*\n\s*return null;/);
});

test('a session the server has already ended sends the player to the entry screen', () => {
  const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  assert.match(source, /response\.status === 401 && signedIn\(\)/);
  assert.match(source, /signOut\(/);
});

test('logging out clears this device even when the server cannot be reached', () => {
  const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  const fn = source.slice(source.indexOf('async function signOut'));
  const body = fn.slice(0, fn.indexOf('\n}\n'));
  // session is cleared before the call, so a failed call cannot leave the
  // player looking at a signed-in app.
  assert.ok(body.indexOf('session = null') < body.indexOf('await logout()'));
  assert.match(body, /showSortLabEntry/);
});

test('the Settings tab offers a way out', () => {
  const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  assert.match(source, /id="profile-logout"/);
  assert.match(source, /Log out/);
  assert.match(source, /#profile-logout'\)\.addEventListener\('click', \(\) => signOut\(\)\)/);
});
