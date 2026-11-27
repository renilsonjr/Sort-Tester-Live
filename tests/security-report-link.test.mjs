// Settings links to the public result of the outside security test. A plain
// link: no script or image from another site is loaded for it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');

test('the badge links to the public ImmuniWeb result for this site', () => {
  assert.match(app, /const SECURITY_REPORT_URL = 'https:\/\/www\.immuniweb\.com\/websec\/sortquiz\.app\/[A-Za-z0-9]+\/';/);
});

const LINK = /<a class="security-badge-link" href="\$\{SECURITY_REPORT_URL\}" target="_blank" rel="noopener noreferrer"><img class="security-badge" src="assets\/immuniweb-badge\.png" width="150" height="50" alt="/;

test('it is ImmuniWeb\'s badge image, served from here, opening in a new tab', () => {
  assert.match(app, LINK);
  assert.match(auth, LINK);
  const png = readFileSync(new URL('../assets/immuniweb-badge.png', import.meta.url));
  assert.equal(png.subarray(1, 4).toString(), 'PNG');
  assert.equal(png.readUInt32BE(16), 300); // ImmuniWeb's large badge, drawn at half size
  assert.equal(png.readUInt32BE(20), 100);
});

test('it sits in Settings, under the version line', () => {
  const versionAt = app.indexOf('<p class="profile-version" id="profile-version"></p>');
  const linkAt = app.indexOf('<p class="profile-security">');
  assert.ok(versionAt > 0 && linkAt > versionAt && linkAt - versionAt < 120);
});

test('the sentence has Spanish', () => {
  assert.match(app, /alt="\$\{esc\(t\('Security tested: grade A by ImmuniWeb'\)\)\}"/);
  assert.match(i18n, /'Security tested: grade A by ImmuniWeb': 'Seguridad probada: calificación A de ImmuniWeb',/);
});

test('nothing from the tester is loaded into the page', () => {
  assert.doesNotMatch(html, /immuniweb|ywxi|trustedsite/i);
  for (const source of [app, auth]) {
    // the badge image is a local file; nothing is fetched from their servers
    assert.doesNotMatch(source, /<script[^>]*immuniweb|<img[^>]*src="https?:|ywxi|trustedsite/i);
  }
});

test('the sign-in screen shows it in its footer, under the maker line', () => {
  const makerAt = auth.indexOf("forgotText('Privacy')}</a></p>");
  const linkAt = auth.indexOf('<p class="auth-footer auth-footer-security"><a class="security-badge-link"');
  assert.ok(makerAt > 0 && linkAt > makerAt && linkAt - makerAt < 80);
  assert.match(auth, /alt="\$\{forgotText\('Security tested: grade A by ImmuniWeb'\)\}"/);
  assert.match(auth, /'Security tested: grade A by ImmuniWeb': 'Seguridad probada: calificación A de ImmuniWeb',/);
});

test('the sign-in screen and Settings link to the same report', () => {
  const url = (source) => source.match(/const SECURITY_REPORT_URL = '([^']+)';/)[1];
  assert.equal(url(auth), url(app));
});
