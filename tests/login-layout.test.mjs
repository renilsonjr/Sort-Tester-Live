import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The login screen as the owner approved it on 2026-11-27 (proposal B).
// Measured in the running app at 390 x 844: the screen is 741px tall (it was
// 876px and scrolled), the card is 32 / 16 / 16, and the two secondary
// buttons are 154px each. At 320px they stack.

const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const panel = auth.slice(auth.indexOf('container.innerHTML = `'), auth.indexOf('`;', auth.indexOf('container.innerHTML = `')));

test('the mark and the name share one line', () => {
  assert.match(panel, /<div class="auth-brand">\s*<div class="brandmark" aria-hidden="true">RJ<\/div>\s*<h1 class="auth-title">Sort Quiz<\/h1>\s*<\/div>/);
  assert.match(html, /\n  \.auth-brand \{ display: flex; align-items: center;/);
});

test('Create account stands beside the guest button, and comes first', () => {
  const pair = panel.slice(panel.indexOf('class="auth-pair"'), panel.indexOf('id="auth-forgot-btn"'));
  assert.match(pair, /<button id="auth-register-btn" class="ghost" type="button">Create account<\/button>/);
  assert.match(pair, /<button id="auth-guest-btn" class="ghost" type="button">Play as guest<\/button>/);
  assert.ok(pair.indexOf('auth-register-btn') < pair.indexOf('auth-guest-btn'));
  // The primary action is still the one above them.
  assert.ok(panel.indexOf('id="auth-login-btn"') < panel.indexOf('class="auth-pair"'));
});

test('the two stack on a narrow phone instead of breaking their words', () => {
  assert.match(html, /\n  \.auth-pair \{ display: grid; grid-template-columns: repeat\(auto-fit, minmax\(128px, 1fr\)\); gap: 8px; \}/);
});

test('the card is concentric with the fields and buttons inside it', () => {
  // --r-sm (16px) inside 16px of padding
  assert.match(html, /--r-sm:\s*16px/);
  assert.match(html, /\n  #auth-panel \.auth-card \{ border-radius: 32px; padding: 16px; gap: 12px; \}/);
});

test('an open form takes the card\'s place, above How to play', () => {
  assert.ok(panel.indexOf('id="auth-choices"') < panel.indexOf('id="auth-form"'));
  assert.ok(panel.indexOf('id="auth-form"') < panel.indexOf('id="auth-howto"'));
});

test('Show is not light gold on the cream field', () => {
  assert.match(html, /\n  html\[data-theme="day"\] \.code-eye \{ color: var\(--gold-ring\); \}/);
});

test('the maker line and Privacy share the last line of text', () => {
  const links = panel.slice(panel.indexOf('class="auth-footer auth-footer-links"'), panel.indexOf('class="auth-footer auth-footer-security"'));
  assert.match(links, /renilsonjr\.pages\.dev/);
  assert.match(links, /id="auth-privacy"/);
});
