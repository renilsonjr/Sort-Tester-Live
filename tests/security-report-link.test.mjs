// Settings links to the public result of the outside security test. A plain
// link: no script or image from another site is loaded for it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('the link points at the public ImmuniWeb result for this site', () => {
  assert.match(app, /const SECURITY_REPORT_URL = 'https:\/\/www\.immuniweb\.com\/websec\/sortquiz\.app\/[A-Z0-9]+\/';/);
});

test('it opens in a new tab that cannot reach back into the app', () => {
  assert.match(app, /<a href="\$\{SECURITY_REPORT_URL\}" target="_blank" rel="noopener noreferrer">/);
});

test('it sits in Settings, under the version line', () => {
  const versionAt = app.indexOf('<p class="profile-version" id="profile-version"></p>');
  const linkAt = app.indexOf('<p class="profile-security">');
  assert.ok(versionAt > 0 && linkAt > versionAt && linkAt - versionAt < 120);
});

test('the sentence has Spanish', () => {
  assert.match(app, /t\('Security tested: grade A by ImmuniWeb'\)/);
  assert.match(i18n, /'Security tested: grade A by ImmuniWeb': 'Seguridad probada: calificación A de ImmuniWeb',/);
});

test('nothing from the tester is loaded into the page', () => {
  assert.doesNotMatch(html, /immuniweb|ywxi|trustedsite/i);
  assert.doesNotMatch(app, /<script[^>]*immuniweb|<img[^>]*immuniweb/i);
});
