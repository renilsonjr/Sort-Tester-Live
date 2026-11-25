// #334: creating an account and pressing Continue put the new player back
// on the sign-in screen, with the code they had just been given to type in
// by hand. Confirmed twice against the local database and in the code --
// Continue called closeForm(), which only hides the form.
//
// Verified in the running app: Continue now lands in the app signed in (all
// four dock tabs, which only appear when signed in), and with the login call
// forced to fail the screen stays put with the code still on it.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');
const js = auth.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('#334 Continue signs the new player in', () => {
  assert.match(js, /const newLoginId = result\.data\.login_id;/);
  assert.match(js, /const signedIn = await loginWithId\(username, newLoginId\);/);
  assert.match(js, /if \(onLoggedIn\) onLoggedIn\(signedIn\.data\);/);
  // The old behaviour was this and only this.
  assert.doesNotMatch(js, /done\.addEventListener\('click', \(\) => closeForm/);
});

test('#334 a failed sign-in leaves the player where they can still act', () => {
  // The code disappears from this screen for ever once it closes, so a
  // failure must not close it, must not swallow the reason, and must leave
  // the button usable.
  const handler = js.slice(js.indexOf("done.addEventListener('click'"));
  const body = handler.slice(0, handler.indexOf('\n        });'));
  assert.match(body, /done\.disabled = false;/);
  assert.match(body, /showMessage\(forgotText\('Your account was created\. Sign in with your username and the Quiz Code above\.'\), true\);/);
  // closeForm happens only on the success branch.
  const close = body.indexOf('closeForm');
  assert.ok(close !== -1 && close < body.indexOf('done.disabled = false'),
    'the form is closed outside the success branch');
});

test('#334 the new message has Spanish, like the rest of this flow', () => {
  assert.match(auth, /'Your account was created\. Sign in with your username and the Quiz Code above\.':\s*\n\s*'Tu cuenta se creó\. Inicia sesión con tu nombre de usuario y el Quiz Code de arriba\.',/);
});
