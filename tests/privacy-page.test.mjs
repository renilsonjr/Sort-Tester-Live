// The privacy page: one file per language, linked from the sign-in footer
// and from Settings, and true to what the app keeps.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8');
const app = read('src/app.js');
const auth = read('src/auth.js');
const i18n = read('src/i18n.js');
const pages = { en: read('assets/privacy/privacy-en.html'), es: read('assets/privacy/privacy-es.html') };

test('the sign-in footer and Settings link to it, in the reader\'s language', () => {
  assert.match(auth, /<a id="auth-privacy" class="auth-footer-link" href="\$\{privacyHref\(\)\}" target="_blank" rel="noopener">\$\{forgotText\('Privacy'\)\}<\/a>/);
  assert.match(auth, /assets\/privacy\/privacy-\$\{forgotText\('Privacy'\) === 'Privacy' \? 'en' : 'es'\}\.html/);
  assert.match(app, /<a id="profile-privacy" class="auth-footer-link" href="assets\/privacy\/privacy-\$\{language\.code === 'es' \? 'es' : 'en'\}\.html" target="_blank" rel="noopener">/);
});

test('the link text has Spanish in both tables', () => {
  assert.match(auth, /'Privacy': 'Privacidad',/);
  assert.match(i18n, /'Privacy': 'Privacidad',/);
});

test('each page is self-contained: no script, nothing from another site', () => {
  for (const [code, html] of Object.entries(pages)) {
    assert.match(html, new RegExp(`<html lang="${code}">`));
    assert.doesNotMatch(html, /<script|<link |src="https?:|url\(https?:/i, code);
  }
});

test('both pages say the same things', () => {
  for (const html of Object.values(pages)) {
    for (const fact of ['15', '30', '7', 'renilson.rjwork@gmail.com', 'Renilson Rodrigues']) {
      assert.ok(html.includes(fact), fact);
    }
    assert.equal((html.match(/<section>/g) || []).length, 4);
  }
});
