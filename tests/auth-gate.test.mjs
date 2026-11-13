import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [auth], cleanup } = await loadAppModules(['src/auth.js']);
after(cleanup);

// A tiny fake DOM: each selector returns one stable element whose click
// handlers can be fired by the test.
function fakeElement() {
  const children = new Map();
  const listeners = {};
  return {
    hidden: false,
    value: '',
    textContent: '',
    className: '',
    disabled: false,
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

function fakePage() {
  const panel = fakeElement();
  panel.hidden = true;
  const app = fakeElement();
  const doc = { getElementById: (id) => ({ 'auth-panel': panel, app }[id] ?? null) };
  return { doc, panel, app };
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    headers: { get: () => 'application/json' },
    json: async () => body,
  };
}

// Route fake fetch calls: /health plus the auth API used by the panel.
function fakeFetch({ health = jsonResponse(200, { status: 'ok' }), me = jsonResponse(401, {}), login } = {}) {
  return async (url) => {
    if (url === '/health') {
      if (health instanceof Error) throw health;
      return health;
    }
    if (url === '/api/auth/me') return me;
    if (url === '/api/auth/login') return login;
    throw new Error(`unexpected request ${url}`);
  };
}

async function withGlobalFetch(fetchFn, run) {
  const original = globalThis.fetch;
  globalThis.fetch = fetchFn;
  try { return await run(); } finally { globalThis.fetch = original; }
}

test('backend answers /health: the login screen covers the app', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch();
  const shown = await withGlobalFetch(fetchFn, () => auth.startAuthGate({ doc, fetchFn }));
  assert.equal(shown, true);
  assert.equal(panel.hidden, false);
  assert.equal(app.hidden, true);
});

test('no backend (GitHub Pages 404): the page stays exactly as it was', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch({ health: { ok: false, status: 404, json: async () => { throw new Error('html'); } } });
  assert.equal(await auth.startAuthGate({ doc, fetchFn }), false);
  assert.equal(panel.hidden, true);
  assert.equal(app.hidden, false);
});

test('network error or wrong /health body: no login screen', async () => {
  for (const health of [new Error('offline'), jsonResponse(200, { status: 'nope' })]) {
    const { doc, panel, app } = fakePage();
    assert.equal(await auth.startAuthGate({ doc, fetchFn: fakeFetch({ health }) }), false);
    assert.equal(panel.hidden, true);
    assert.equal(app.hidden, false);
  }
});

test('a /health that never answers gives up after the timeout', async () => {
  const { doc } = fakePage();
  const hanging = (_url, { signal }) => new Promise((_resolve, reject) => {
    signal.addEventListener('abort', () => reject(new Error('aborted')));
  });
  assert.equal(await auth.startAuthGate({ doc, fetchFn: hanging, timeoutMs: 20 }), false);
});

test('Continue as guest opens the app', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch();
  await withGlobalFetch(fetchFn, () => auth.startAuthGate({ doc, fetchFn }));
  await panel.querySelector('#auth-guest-btn').fire('click');
  assert.equal(panel.hidden, true);
  assert.equal(app.hidden, false);
});

test('a successful login opens the app', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch({ login: jsonResponse(200, { username: 'alice', tag: '1234' }) });
  await withGlobalFetch(fetchFn, async () => {
    await auth.startAuthGate({ doc, fetchFn });
    await panel.querySelector('#auth-login-btn').fire('click');
    const form = panel.querySelector('#auth-form');
    form.querySelector('#login-id-input').value = 'ABCD-EFGH-JKLM-NPQR';
    await form.querySelector('#login-submit').fire('click');
  });
  assert.equal(panel.hidden, true);
  assert.equal(app.hidden, false);
});

test('a failed login keeps the login screen', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch({ login: jsonResponse(401, {}) });
  await withGlobalFetch(fetchFn, async () => {
    await auth.startAuthGate({ doc, fetchFn });
    await panel.querySelector('#auth-login-btn').fire('click');
    await panel.querySelector('#auth-form').querySelector('#login-submit').fire('click');
  });
  assert.equal(panel.hidden, false);
  assert.equal(app.hidden, true);
});

test('an existing session skips the login screen', async () => {
  const { doc, panel, app } = fakePage();
  const fetchFn = fakeFetch({ me: jsonResponse(200, { username: 'alice', tag: '1234' }) });
  await withGlobalFetch(fetchFn, () => auth.startAuthGate({ doc, fetchFn }));
  assert.equal(panel.hidden, true);
  assert.equal(app.hidden, false);
});
