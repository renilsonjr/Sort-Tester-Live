import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

// The kept reads (balance and season) are cut out of app.js and run against
// a counting fake server and a clock the test moves by hand.
const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const profile = readFileSync(new URL('../src/profileScreens.js', import.meta.url), 'utf8');
const start = source.indexOf('const CACHED_READS');
const end = source.indexOf('// Recent reauthentication');
assert.ok(start > 0 && end > start, 'the read cache and apiSend are where the test expects');
const block = source.slice(start, end);

function page({ answer = () => ({ points: 10 }) } = {}) {
  const calls = [];
  const clock = { now: 1000 };
  const context = {
    Date: { now: () => clock.now },
    Map, Set, JSON,
    signedIn: () => true,
    signOut() {},
    t: (text) => text,
    fetch: async (url, options = {}) => {
      calls.push(`${options.method ?? 'GET'} ${url}`);
      const body = answer(url, calls.length);
      if (body === null) throw new Error('offline');
      return { ok: true, status: 200, json: async () => body };
    },
  };
  runInNewContext(`${block}\nthis.api = api; this.apiSend = apiSend; this.clearReadCache = clearReadCache;`, context);
  return { ...context, calls, clock };
}

test('the balance is asked for once across screens that open close together', async () => {
  const p = page();
  await p.api('/ranked/entry');
  await p.api('/ranked/entry');
  assert.deepEqual(p.calls, ['GET /api/ranked/entry']);
});

test('two screens asking at the same moment share one request', async () => {
  const p = page();
  await Promise.all([p.api('/ranked/entry'), p.api('/ranked/entry')]);
  assert.equal(p.calls.length, 1);
});

test('the kept answer expires', async () => {
  const p = page();
  await p.api('/ranked/entry');
  p.clock.now += 15001;
  await p.api('/ranked/entry');
  assert.equal(p.calls.length, 2);
});

test('a write empties the kept answers', async () => {
  const p = page();
  await p.api('/ranked/entry');
  await p.apiSend('POST', '/ranked/support/tickets', {});
  await p.api('/ranked/entry');
  assert.deepEqual(p.calls, [
    'GET /api/ranked/entry', 'POST /api/ranked/support/tickets', 'GET /api/ranked/entry',
  ]);
});

test('a failed read is not kept', async () => {
  const p = page({ answer: (_url, n) => (n === 1 ? null : { points: 10 }) });
  assert.equal(await p.api('/ranked/entry'), null);
  assert.deepEqual(JSON.parse(JSON.stringify(await p.api('/ranked/entry'))), { points: 10 });
  assert.equal(p.calls.length, 2);
});

test('other reads are never kept', async () => {
  const p = page();
  await p.api('/ranked/leaderboard');
  await p.api('/ranked/leaderboard');
  assert.equal(p.calls.length, 2);
});

test('an attempt and a change of session empty the kept answers', () => {
  assert.match(source, /createAttemptClient\(\{ fetchFn: attemptFetch \}\)/);
  assert.doesNotMatch(source, /createAttemptClient\(\)/);
  for (const name of ['function setSession', 'async function signOut', 'async function attemptFetch']) {
    const fn = source.slice(source.indexOf(name));
    assert.match(fn.slice(0, fn.indexOf('\n}\n')), /clearReadCache\(\)/, name);
  }
  // A deleted account is dropped from the profile screens' own file, through
  // the one function app.js hands them, and that function empties the cache.
  const deleted = profile.slice(profile.indexOf('function showDeletionAccepted'));
  assert.match(deleted.slice(0, deleted.indexOf('\n  }\n')), /forgetAccount\(\)/);
  assert.match(source, /forgetAccount: \(\) => \{ session = null; clearReadCache\(\); \}/);
});

test('the profile shows the name from the session without asking the server first', () => {
  const fn = profile.slice(profile.indexOf('async function fillProfile'));
  const body = fn.slice(0, fn.indexOf('\n  }\n'));
  assert.doesNotMatch(body, /await api\('\/auth\/me'\)/);
  assert.match(profile, /id="profile-name">\$\{esc\(account\(\)\?\.username/);
  assert.match(source, /account: \(\) => session,/);
});
