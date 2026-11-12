import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('auth.js parses and exports expected functions', async () => {
  const source = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
  // Quick parse check by wrapping in a module and importing via data URL.
  const moduleUrl = `data:text/javascript;base64,${Buffer.from(source).toString('base64')}`;
  const auth = await import(moduleUrl);
  assert.equal(typeof auth.registerAccount, 'function');
  assert.equal(typeof auth.loginWithId, 'function');
  assert.equal(typeof auth.logout, 'function');
  assert.equal(typeof auth.fetchMe, 'function');
  assert.equal(typeof auth.createAuthPanel, 'function');
});
