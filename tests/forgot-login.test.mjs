// "Forgot my Quiz Code?" on the sign-in screen (issue #251). The form leaves the
// owner a message and nothing else: it must never say whether an account
// exists, and it must say the same fixed sentence for every accepted message.
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [auth], cleanup } = await loadAppModules(['src/auth.js']);
after(cleanup);
const source = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');

function fakeElement() {
  const children = new Map();
  const listeners = {};
  return {
    hidden: false, value: '', textContent: '', className: '', disabled: false,
    focus() {},
    set innerHTML(_markup) { children.clear(); },
    get innerHTML() { return ''; },
    querySelector(selector) {
      if (!children.has(selector)) children.set(selector, fakeElement());
      return children.get(selector);
    },
    addEventListener(type, handler) { listeners[type] = handler; },
    async fire(type) { await listeners[type]?.(); },
  };
}

async function openForm(fetchFn, language = null) {
  const calls = [];
  // Newer Node versions define localStorage as an accessor on globalThis, so
  // it is replaced by descriptor rather than by assignment.
  const originalFetch = globalThis.fetch;
  const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
  globalThis.fetch = async (url, options) => { calls.push({ url, options }); return fetchFn(); };
  Object.defineProperty(globalThis, 'localStorage', {
    value: { getItem: () => language }, configurable: true, writable: true,
  });
  const panel = fakeElement();
  auth.createAuthPanel(panel, () => {}, () => {});
  await panel.querySelector('#auth-forgot-btn').fire('click');
  const form = panel.querySelector('#auth-form');
  const restore = () => {
    globalThis.fetch = originalFetch;
    if (originalStorage) Object.defineProperty(globalThis, 'localStorage', originalStorage);
    else delete globalThis.localStorage;
  };
  return { panel, form, calls, restore };
}

const created = () => ({ ok: true, status: 201, headers: { get: () => null } });
const refused = (status) => () => ({ ok: false, status, headers: { get: () => null } });

test('the link opens the form in place of the entry choices', async () => {
  const { panel, form, restore } = await openForm(created);
  try {
    assert.equal(panel.querySelector('#auth-choices').hidden, true);
    assert.equal(form.hidden, false);
  } finally { restore(); }
});

test('sending posts the trimmed text and nothing else', async () => {
  const { form, calls, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = '  I am Sam, night sort  ';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(calls.length, 1);
    assert.equal(calls[0].url, '/api/auth/recovery-messages');
    assert.equal(calls[0].options.method, 'POST');
    assert.deepEqual(JSON.parse(calls[0].options.body), { message: 'I am Sam, night sort' });
  } finally { restore(); }
});

test('an empty message is not sent', async () => {
  const { panel, form, calls, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = '   ';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(calls.length, 0);
    assert.match(panel.querySelector('#auth-message').textContent, /Write a message/);
  } finally { restore(); }
});

test('success closes the form and says the owner recovers access in person', async () => {
  const { panel, form, restore } = await openForm(created);
  try {
    form.querySelector('#forgot-message').value = 'help';
    await form.querySelector('#forgot-send').fire('click');
    assert.equal(form.hidden, true);
    assert.equal(panel.querySelector('#auth-choices').hidden, false);
    assert.match(panel.querySelector('#auth-message').textContent, /in person/);
  } finally { restore(); }
});

test('too many messages and a dead server each get their own sentence', async () => {
  for (const [fetchFn, expected] of [
    [refused(429), /Too many messages/],
    [() => { throw new Error('offline'); }, /Could not reach the server/],
    [refused(422), /could not be sent/],
  ]) {
    const { panel, form, restore } = await openForm(fetchFn);
    try {
      form.querySelector('#forgot-message').value = 'help';
      await form.querySelector('#forgot-send').fire('click');
      assert.match(panel.querySelector('#auth-message').textContent, expected);
      assert.equal(form.hidden, false, 'the text is kept so it can be sent again');
    } finally { restore(); }
  }
});

test('the new sentences are in Spanish when Spanish is chosen', async () => {
  const { panel, form, restore } = await openForm(created, 'es');
  try {
    form.querySelector('#forgot-message').value = 'ayuda';
    await form.querySelector('#forgot-send').fire('click');
    assert.match(panel.querySelector('#auth-message').textContent, /en persona/);
  } finally { restore(); }
});

test('every new English sentence has a Spanish one, and none is Portuguese', () => {
  const table = source.slice(source.indexOf('const FORGOT_ES'), source.indexOf('function forgotText'));
  const pairs = [...table.matchAll(/^\s*'((?:[^'\\]|\\.)+)':\s*\n?\s*'((?:[^'\\]|\\.)+)',?$/gm)];
  assert.ok(pairs.length >= 9, `expected the whole table, found ${pairs.length}`);
  for (const [, english, spanish] of pairs) assert.notEqual(english, spanish);
  assert.doesNotMatch(table, /\b(você|não|responsável|pessoalmente|esqueci)\b/i);
});

test('the form never reports on an account', () => {
  const body = source.slice(source.indexOf("'#auth-forgot-btn'"), source.indexOf("'#auth-guest-btn'"));
  assert.doesNotMatch(body, /result\.data/);
  assert.doesNotMatch(body, /username|#\$\{/);
  assert.match(body, /maxlength="500"/);
});
