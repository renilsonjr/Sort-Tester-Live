// The reusable attempt client (#24, slice 7): it carries the page
// capability and a heartbeat, and keeps neither where a refresh could
// resume the attempt.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/attemptClient.js', import.meta.url), 'utf8');
const { createAttemptClient, HEARTBEAT_MS } = await import(
  `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`
);

function fakeFetch(script) {
  const calls = [];
  const fetchFn = async (url, options) => {
    calls.push({ url, options });
    const next = script.shift();
    return {
      status: next.status,
      ok: next.status >= 200 && next.status < 300,
      json: async () => next.body,
    };
  };
  return { fetchFn, calls };
}

test('the capability from start rides on every later request, in a header', async () => {
  const { fetchFn, calls } = fakeFetch([
    { status: 201, body: { attempt_id: 'att-1', capability: 'cap-xyz' } },
    { status: 200, body: { seq: 1 } },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/ranked/tiebreak/rounds/r1/attempts');
  await client.current();
  assert.equal(calls[0].options.headers['X-Attempt-Capability'], undefined);
  assert.equal(calls[1].options.headers['X-Attempt-Capability'], 'cap-xyz');
  assert.equal(client.attemptId, 'att-1');
});

test('an unreachable server is answered, not thrown', async () => {
  const client = createAttemptClient({ fetchFn: async () => { throw new TypeError('down'); } });
  const result = await client.start('/x');
  assert.equal(result.ok, false);
  assert.equal(result.status, 0);
});

test('the heartbeat fires on its interval and stops on stop', async () => {
  const { fetchFn, calls } = fakeFetch([
    { status: 201, body: { attempt_id: 'a', capability: 'c' } },
    { status: 204, body: null },
    { status: 204, body: null },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/x');
  const timers = [];
  const fakeInterval = (fn) => { timers.push(fn); return 1; };
  let cleared = null;
  client.startHeartbeat(fakeInterval);
  assert.equal(timers.length, 1);
  await timers[0]();
  assert.match(calls.at(-1).url, /\/heartbeat$/);
  client.stop((id) => { cleared = id; });
  assert.equal(cleared, 1);
});

test('the heartbeat period is one second', () => {
  assert.equal(HEARTBEAT_MS, 1000);
});

test('the capability lives only in memory, never in storage or the URL', () => {
  // a refresh must not be able to resume: there is nothing to read it from
  assert.doesNotMatch(source, /localStorage|sessionStorage|location\.|history\./);
  assert.match(source, /never storage, never the URL/);
});
