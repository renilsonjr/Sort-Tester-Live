// The sign-up confirmation draws the username and the new Quiz Code into
// markup. Both are escaped, rather than trusted because the server only
// accepts safe characters today.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
const { escapeHtml } = await import('../src/common.js');

test('both values on the confirmation are escaped', () => {
  assert.match(auth, /readonly value="\$\{escapeHtml\(username\)\}">/);
  assert.match(auth, /readonly value="\$\{escapeHtml\(result\.data\.login_id\)\}">/);
  assert.doesNotMatch(auth, /value="\$\{(?!escapeHtml\()/);
});

test('the escape covers every character that can break out of markup', async () => {
  assert.equal(escapeHtml(`"><img src=x onerror='a'>&`), '&quot;&gt;&lt;img src=x onerror=&#39;a&#39;&gt;&amp;');
  assert.equal(escapeHtml('pt_player_1'), 'pt_player_1');
  assert.equal(escapeHtml(undefined), '');
});
