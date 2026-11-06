import test from 'node:test';
import assert from 'node:assert/strict';
import { setTimeout as delay } from 'node:timers/promises';
import { checkHealth, readConfig } from '../dev/health-client.mjs';

const local = { pageOrigin: 'http://127.0.0.1:8000', apiBaseUrl: 'http://127.0.0.1:18765' };
const jsonResponse = (value, status = 200) => new Response(JSON.stringify(value), {
  status, headers: { 'Content-Type': 'application/json' },
});

test('health success uses the configured endpoint without credentials or redirects', async () => {
  let requested;
  const result = await checkHealth({ ...local, fetchImpl: async (url, options) => {
    requested = { url, options };
    return jsonResponse({ status: 'ok' });
  } });
  assert.equal(result.kind, 'success');
  assert.match(result.message, /ok/);
  assert.equal(requested.url, 'http://127.0.0.1:18765/health');
  assert.equal(requested.options.credentials, 'omit');
  assert.equal(requested.options.redirect, 'error');
  assert.equal(requested.options.cache, 'no-store');
});

test('a non-200 response is invalid even when the body says ok', async () => {
  const result = await checkHealth({ ...local, fetchImpl: async () => jsonResponse({ status: 'ok' }, 503) });
  assert.equal(result.kind, 'invalid-response');
  assert.match(result.message, /503/);
});

test('bad JSON, wrong content type, and wrong health structure never report success', async (t) => {
  const responses = [
    new Response('{', { headers: { 'Content-Type': 'application/json' } }),
    new Response('{"status":"ok"}', { headers: { 'Content-Type': 'text/html' } }),
    ...[null, [], { status: 'down' }, { status: 'ok', extra: true }, '<b>ok</b>'].map(value => jsonResponse(value)),
  ];
  for (const [index, response] of responses.entries()) {
    await t.test(`invalid response ${index + 1}`, async () => {
      const result = await checkHealth({ ...local, fetchImpl: async () => response });
      assert.equal(result.kind, 'invalid-response');
      assert.ok(!result.message.includes('<b>'));
    });
  }
});

test('network failure gives server and CORS troubleshooting rather than a diagnosis', async () => {
  const result = await checkHealth({ ...local, fetchImpl: async () => { throw new TypeError('Failed to fetch'); } });
  assert.equal(result.kind, 'unavailable');
  assert.match(result.message, /server/i);
  assert.match(result.message, /CORS/);
});

test('an unresponsive request reaches its deadline and is aborted', async () => {
  let signal;
  const result = await checkHealth({ ...local, timeoutMs: 20, fetchImpl: (_url, options) => {
    signal = options.signal;
    return new Promise(() => {});
  } });
  assert.equal(result.kind, 'unavailable');
  assert.match(result.message, /timed out/i);
  assert.equal(signal.aborted, true);
});

test('the deadline also covers a stalled response body', async () => {
  const result = await checkHealth({ ...local, timeoutMs: 20, fetchImpl: async () => new Response(
    new ReadableStream({ start() {} }), { headers: { 'Content-Type': 'application/json' } },
  ) });
  assert.equal(result.kind, 'unavailable');
  assert.match(result.message, /timed out/i);
});

test('a settled request clears its deadline instead of aborting later', async () => {
  let signal;
  const result = await checkHealth({ ...local, timeoutMs: 20, fetchImpl: async (_url, options) => {
    signal = options.signal;
    return jsonResponse({ status: 'ok' });
  } });
  assert.equal(result.kind, 'success');
  await delay(40);
  assert.equal(signal.aborted, false);
});

test('hosted and unexpected page origins cannot initiate any API request', async () => {
  let calls = 0;
  for (const pageOrigin of ['https://renilsonjr.github.io', 'null', 'http://localhost:8000', 'http://127.0.0.1:8001']) {
    const result = await checkHealth({ ...local, pageOrigin, fetchImpl: async () => { calls++; } });
    assert.equal(result.kind, 'configuration');
  }
  assert.equal(calls, 0);
});

test('configuration cannot redirect checks to arbitrary servers or URL paths', async () => {
  let calls = 0;
  for (const apiBaseUrl of [undefined, '', 'https://example.com', 'http://localhost:18765',
    'http://127.0.0.1:18765/', 'http://127.0.0.1:18765/path',
    'http://user:password@127.0.0.1:18765', 'http://127.0.0.1:18765?secret=x']) {
    const result = await checkHealth({ ...local, apiBaseUrl, fetchImpl: async () => { calls++; } });
    assert.equal(result.kind, 'configuration');
  }
  assert.equal(calls, 0);
});

test('local configuration reads the API address from the separate file', async () => {
  assert.deepEqual(await readConfig(jsonResponse({ apiBaseUrl: local.apiBaseUrl })), { apiBaseUrl: local.apiBaseUrl });
});

test('missing or malformed local configuration gives setup instructions', async () => {
  for (const response of [new Response('Not Found', { status: 404 }), new Response('{'),
    jsonResponse(null), jsonResponse({}), jsonResponse({ apiBaseUrl: 123 }),
    jsonResponse({ apiBaseUrl: local.apiBaseUrl, password: 'do-not-use' })]) {
    await assert.rejects(readConfig(response), /config\.example\.json.*config\.local\.json/);
  }
});
