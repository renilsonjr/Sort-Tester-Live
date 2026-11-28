import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';

test('auth.js parses and exports expected functions', async () => {
  // Loaded as the browser loads it, from a file, so its one import resolves.
  const { modules: [auth], cleanup } = await loadAppModules(['src/auth.js']);
  await cleanup();
  assert.equal(typeof auth.registerAccount, 'function');
  assert.equal(typeof auth.loginWithId, 'function');
  assert.equal(typeof auth.logout, 'function');
  assert.equal(typeof auth.fetchMe, 'function');
  assert.equal(typeof auth.createAuthPanel, 'function');
});
