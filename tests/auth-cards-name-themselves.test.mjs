// Round 4: #422. The login card opens with `<p class="auth-eyebrow">Log in`.
// The two cards reached from it had no heading at all -- their first child
// was a field label, "Choose a username" and "Message for the owner" -- and
// the h1 above all three is the product name on every one.
//
// These are the screens a new employee meets before they have an account.
// Walked in the running app at 375x812: LOG IN / NEW ACCOUNT / RECOVER YOUR
// ACCESS, and in Spanish Cuenta nueva / Recupera tu acceso.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');

function form(after) {
  const at = auth.indexOf(after);
  assert.notEqual(at, -1, `${after} is gone`);
  return auth.slice(at, at + 700);
}

test('#422 the new-account card names itself first', () => {
  const body = form("'#auth-register-btn'");
  assert.match(body, /form\.innerHTML = `\s*<p class="auth-eyebrow">\$\{forgotText\('New account'\)\}<\/p>/);
});

test('#422 the recovery card names itself first', () => {
  const body = form("'#auth-forgot-btn'");
  assert.match(body, /form\.innerHTML = `\s*<p class="auth-eyebrow">\$\{forgotText\('Recover your access'\)\}<\/p>/);
});

test('#422 it is the same eyebrow the login card uses', () => {
  // Not a new heading style: the class the login card has always had, so
  // all three cards are labelled the same way.
  assert.match(auth, /<p class="auth-eyebrow">Log in<\/p>/);
});

test('#422 both names have Spanish', () => {
  // This file carries its own table: it is loaded on its own and imports
  // nothing, so i18n.js cannot reach it.
  assert.match(auth, /'New account':\s*\n?\s*'Cuenta nueva',/);
  assert.match(auth, /'Recover your access':\s*\n?\s*'Recupera tu acceso',/);
});

test('#422 the field labels are still there', () => {
  // The eyebrow is added above them, not instead of them.
  assert.match(auth, /\$\{forgotText\('Choose a username'\)\}/);
  assert.match(auth, /\$\{forgotText\('Message for the owner'\)\}/);
});
