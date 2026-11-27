// The sign-in screen ends with a quiet link to the author's own site, for
// anyone who wants to know who made the app (issue #267).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

const panel = auth.slice(auth.indexOf('container.innerHTML = `'), auth.indexOf('`;', auth.indexOf('container.innerHTML = `')));

test('the link sits at the foot of the sign-in screen, after everything else', () => {
  const footer = panel.indexOf('class="auth-footer"');
  assert.notEqual(footer, -1, 'the sign-in screen has no footer');
  assert.ok(footer > panel.indexOf('id="auth-message"'), 'the footer comes last');
});

test('it goes to the author site in a new tab, without handing the opener over', () => {
  const link = panel.match(/<a [^>]*class="auth-footer-link"[^>]*>/);
  assert.ok(link, 'no footer link');
  assert.match(link[0], /href="https:\/\/renilsonjr\.pages\.dev"/);
  assert.match(link[0], /target="_blank"/);
  assert.match(link[0], /rel="noopener noreferrer"/);
});

test('the words are in both languages', () => {
  assert.match(panel, /forgotText\('Made by RJ\. Meet the person behind the app'\)/);
  assert.match(auth, /'Made by RJ\. Meet the person behind the app':\s*'[^']*RJ[^']+'/);
});

test('it is styled as a small, quiet line with a visible keyboard focus', () => {
  assert.match(html, /\.auth-footer\s*\{[^}]*font-size:\s*12/);
  assert.match(html, /\.auth-footer-link:focus-visible\s*\{[^}]*outline/);
});

test('the panel imports only common.js, which imports nothing', () => {
  const imports = auth.match(/^import .+$/gm) ?? [];
  assert.deepEqual(imports, ["import { escapeHtml, SECURITY_REPORT_URL } from './common.js';"]);
  const common = readFileSync(new URL('../src/common.js', import.meta.url), 'utf8');
  assert.doesNotMatch(common, /^import /m);
});
