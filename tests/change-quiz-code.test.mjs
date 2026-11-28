// Change my Quiz Code (owner decision 2026-11-25): a Settings row opens a
// screen that asks the server for a new code behind the re-entry gate,
// shows it once beside the username in one form, and has Spanish text.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { screensSource } from './helpers/screens-source.mjs';

const app = screensSource();
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');
const screen = app.slice(app.indexOf('function showChangeCode()'), app.indexOf('function showDeleteAccount()'));

test('Settings has a row that opens the screen', () => {
  assert.match(app, /id="profile-change-code"/);
  assert.match(app, /#profile-change-code'\)\.addEventListener\('click', showChangeCode\)/);
});

test('the change goes through the re-entry gate', () => {
  assert.match(screen, /apiSendOwner\('POST', '\/auth\/login-id\/change'\)/);
});

test('the new code is shown once with the username in one form a browser can save', () => {
  assert.match(screen, /<form id="change-code-form"/);
  assert.match(screen, /autocomplete="username"/);
  assert.match(screen, /autocomplete="new-password"/);
  assert.match(screen, /esc\(result\.data\.login_id\)/);
  assert.match(screen, /Save this Quiz Code\. It will not be shown again\./);
  // nothing keeps the code once it is on screen
  assert.doesNotMatch(screen, /localStorage|sessionStorage/);
});

test('every new line has Spanish', () => {
  for (const line of [
    'Change Quiz Code',
    'You get a new Quiz Code. The old one stops working at once.',
    'Every other phone or computer signed in to your account is signed out. This one stays.',
    'Your new Quiz Code',
    'Username',
    'Copy',
    'Copied',
    'I saved my Quiz Code',
  ]) {
    assert.ok(i18n.includes(`'${line}':`), line);
  }
});

test('the save forms add no box, so the card layout reaches their fields', () => {
  // The forms exist only so a password manager sees username + code as a
  // pair. Without this the Continue/Done buttons lost their full width and
  // the card's spacing (found while retaking the manual's screenshots).
  const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.match(html, /#register-save-form, #change-code-form, #change-code-result \{ display: contents; \}/);
  assert.match(html, /\.auth-screen input#generated-username \{ font-family: inherit;/);
});
