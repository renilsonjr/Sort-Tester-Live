import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/support.js', import.meta.url), 'utf8');
const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
const support = await import(moduleUrl);

test('support.js exports the calls the screens need', () => {
  for (const name of ['listTickets', 'createTicket', 'readTicket']) {
    assert.equal(typeof support[name], 'function', name);
  }
});

test('an open ticket says its evidence is kept while the case is open', () => {
  assert.equal(
    support.retentionLine({ closed_at: null }),
    'Your evidence is kept while this case is open.',
  );
});

test('a closed ticket shows the date its evidence goes', () => {
  const line = support.retentionLine(
    { closed_at: '2026-11-01T00:00:00Z', evidence_deleted_at: '2026-11-16T00:00:00Z' },
    () => 'example date 9',
  );
  assert.equal(
    line,
    'Description and connection details are deleted on example date 9.',
  );
});

test('a held log says a linked case is open, and nothing about it', () => {
  const line = support.retentionLine({
    closed_at: '2026-11-01T00:00:00Z',
    evidence_held_by_open_case: true,
    evidence_deleted_at: null,
  });
  assert.match(line, /shared with another case that is still open/);
  // never which case, never whose
  assert.doesNotMatch(line, /#|ticket \d|player|username|tag/i);
});

test('outcomes are named in words, never by code', () => {
  assert.equal(support.outcomeLabel({ closed_at: null }), 'Open');
  assert.equal(
    support.outcomeLabel({ closed_at: 'x', outcome: 'network_instability' }),
    'Closed · network instability',
  );
  assert.equal(
    support.outcomeLabel({ closed_at: 'x', outcome: 'insufficient_evidence' }),
    'Closed · not enough evidence',
  );
});

test('insufficient evidence never reads as an accusation', () => {
  const label = support.outcomeLabel({ closed_at: 'x', outcome: 'insufficient_evidence' });
  assert.doesNotMatch(label, /cheat|suspic|fraud|abuse/i);
});

test('a blank description is sent as no description', async () => {
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push(JSON.parse(options.body));
    return new Response('{}', { headers: { 'content-type': 'application/json' } });
  };
  await support.createTicket('attempt-1', '   ');
  await support.createTicket('attempt-2', 'It cut out.');
  await support.createTicket('attempt-3');
  assert.deepEqual(calls[0], { attempt_id: 'attempt-1' });
  assert.deepEqual(calls[1], { attempt_id: 'attempt-2', description: 'It cut out.' });
  assert.deepEqual(calls[2], { attempt_id: 'attempt-3' });
});

test('requests carry the session cookie and nothing else', async () => {
  let seen;
  globalThis.fetch = async (url, options) => {
    seen = { url, options };
    return new Response('[]', { headers: { 'content-type': 'application/json' } });
  };
  await support.listTickets();
  assert.equal(seen.url, '/api/ranked/support/tickets');
  assert.equal(seen.options.credentials, 'same-origin');
});
