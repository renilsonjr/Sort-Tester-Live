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

test('start can carry a body, for starting a promotion attempt', async () => {
  const { fetchFn, calls } = fakeFetch([
    { status: 201, body: { attempt_id: 'att-2', capability: 'cap-2' } },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/ranked/attempts', { mode: 'promotion' });
  assert.equal(calls[0].options.body, JSON.stringify({ mode: 'promotion' }));
});

test('result() reads the settled outcome of an already-ended attempt', async () => {
  const { fetchFn, calls } = fakeFetch([
    { status: 201, body: { attempt_id: 'att-3', capability: 'cap-3' } },
    { status: 200, body: { final_outcome: 'completed' } },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/x');
  const result = await client.result();
  assert.match(calls.at(-1).url, /\/attempts\/att-3\/result$/);
  assert.equal(result.data.final_outcome, 'completed');
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

// An attempt can end while the page only watches a question: the season
// launches, or the server's own clock ends it. The heartbeat is the one
// request still going, so its 410 is how the page finds out.
test('a heartbeat answered 410 tells the page once that the attempt is gone', async () => {
  const { fetchFn } = fakeFetch([
    { status: 201, body: { attempt_id: 'a', capability: 'c' } },
    { status: 204, body: null },
    { status: 410, body: { detail: 'Gone' } },
    { status: 410, body: { detail: 'Gone' } },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/x');
  const timers = [];
  client.startHeartbeat((fn) => { timers.push(fn); return 1; });
  let gone = 0;
  client.onGone(() => { gone += 1; });
  await timers[0]();
  assert.equal(gone, 0, 'a live attempt is not reported gone');
  await timers[0]();
  assert.equal(gone, 1);
  await timers[0]();
  assert.equal(gone, 1, 'the page is told once, not every second');
});

test('stopping the attempt forgets who to tell', async () => {
  const { fetchFn } = fakeFetch([
    { status: 201, body: { attempt_id: 'a', capability: 'c' } },
    { status: 410, body: { detail: 'Gone' } },
  ]);
  const client = createAttemptClient({ fetchFn });
  await client.start('/x');
  const timers = [];
  client.startHeartbeat((fn) => { timers.push(fn); return 1; });
  let gone = 0;
  client.onGone(() => { gone += 1; });
  client.stop(() => {});
  await timers[0]();
  assert.equal(gone, 0);
});
