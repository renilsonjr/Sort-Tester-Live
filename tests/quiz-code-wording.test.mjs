// The login secret is called a "Quiz Code" everywhere a person reads it
// (issue #265). One name, in English and in Spanish, where it stays
// untranslated by the owner's choice. Code identifiers and comments keep
// "login ID": only what reaches the screen is checked here.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const auth = read('src/auth.js');
const app = read('src/app.js');
const i18n = read('src/i18n.js');

// Everything but whole-line comments: what is left is code and the strings
// that end up on screen.
function withoutComments(source) {
  return source.split('\n').filter((line) => !/^\s*(\/\/|\*|\/\*)/.test(line)).join('\n');
}

const OLD_WORDING = /login ID|Login ID|Log in with ID|Need an ID\?|Forgot my login\?|ID de acceso/;

test('the sign-in panel says Quiz Code', () => {
  assert.match(auth, />Log in with Quiz Code</);
  assert.match(auth, /placeholder="Your Quiz Code"/);
  assert.match(auth, />Need a Quiz Code\? Create an account</);
  assert.match(auth, /forgotText\('Forgot my Quiz Code\?'\)/);
  assert.match(auth, /Save this Quiz Code\. It will not be shown again\./);
  assert.match(auth, /I saved my Quiz Code/);
  assert.match(auth, /Invalid username or Quiz Code\. Please try again\./);
});

test('no screen text in the sign-in panel uses the old name', () => {
  assert.doesNotMatch(withoutComments(auth), OLD_WORDING);
});

test('no screen text in the app uses the old name', () => {
  assert.doesNotMatch(withoutComments(app), OLD_WORDING);
});

test('the dictionary has no old name on either side', () => {
  assert.doesNotMatch(withoutComments(i18n), OLD_WORDING);
});

test('Spanish keeps the name untranslated', () => {
  assert.match(i18n, /'Your Quiz Code': 'Tu Quiz Code'/);
  assert.match(i18n, /'Quiz Code': 'Quiz Code'/);
  assert.match(auth, /'Forgot my Quiz Code\?':\s*'[^']*Quiz Code[^']*'/);
});

test('the optional practice name is a different thing and keeps its wording', () => {
  assert.match(app, /t\('Name or ID \(optional\)'\)/);
});
