// What a browser tab and a shared link show for the site (issue #266): the
// title "Sort Quiz", the yellow RJ mark as the icon, and a picture when the
// address is pasted into a message.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, statSync } from 'node:fs';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const head = html.slice(0, html.indexOf('<style>'));
const asset = (name) => new URL(`../assets/${name}`, import.meta.url);

// Width and height from a PNG's IHDR chunk.
function pngSize(name) {
  const bytes = readFileSync(asset(name));
  assert.equal(bytes.subarray(1, 4).toString('latin1'), 'PNG', `${name} is not a PNG`);
  return [bytes.readUInt32BE(16), bytes.readUInt32BE(20)];
}

function meta(attribute, name) {
  const match = head.match(new RegExp(`<meta ${attribute}="${name}" content="([^"]*)">`));
  assert.ok(match, `missing <meta ${attribute}="${name}">`);
  return match[1];
}

test('the tab title is Sort Quiz and nothing else', () => {
  assert.match(head, /<title>Sort Quiz<\/title>/);
});

test('the tab icon is the RJ mark, as a vector with a PNG fallback', () => {
  assert.match(head, /<link rel="icon" type="image\/svg\+xml" href="assets\/favicon\.svg">/);
  assert.match(head, /<link rel="icon" type="image\/png" sizes="32x32" href="assets\/favicon-32\.png">/);
  const svg = readFileSync(asset('favicon.svg'), 'utf8');
  assert.match(svg, />RJ</);
  assert.match(svg, /#f4bd38/i);
  assert.deepEqual(pngSize('favicon-32.png'), [32, 32]);
});

test('a phone home screen gets a 180px icon', () => {
  assert.match(head, /<link rel="apple-touch-icon" href="assets\/apple-touch-icon\.png">/);
  assert.deepEqual(pngSize('apple-touch-icon.png'), [180, 180]);
});

test('a shared link carries a title, a description and a picture', () => {
  assert.equal(meta('property', 'og:title'), 'Sort Quiz');
  assert.equal(meta('property', 'og:type'), 'website');
  assert.equal(meta('property', 'og:url'), 'https://sortquiz.app/');
  assert.ok(meta('property', 'og:description').length > 20);
  assert.equal(meta('name', 'description'), meta('property', 'og:description'));
  assert.equal(meta('name', 'twitter:card'), 'summary_large_image');
});

test('the picture is an absolute address on the public domain, at the size messaging apps expect', () => {
  // Messaging apps fetch the picture themselves and do not resolve relative paths.
  assert.equal(meta('property', 'og:image'), 'https://sortquiz.app/assets/og-preview.png');
  assert.equal(meta('property', 'og:image:width'), '1200');
  assert.equal(meta('property', 'og:image:height'), '630');
  assert.deepEqual(pngSize('og-preview.png'), [1200, 630]);
  assert.ok(statSync(asset('og-preview.png')).size < 300 * 1024, 'the preview picture is over 300 KB');
});

test('nothing in the head points at a private or internal address', () => {
  assert.doesNotMatch(head, /azurecontainerapps|localhost|127\.0\.0\.1/);
});

// The owner unified the name on 2026-11-22: the app is "Sort Quiz" wherever
// a person reads it, not "Sort Lab" in some places and "Sort Quiz" in others.
test('the app calls itself Sort Quiz on the sign-in screen and in the header', () => {
  const auth = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
  const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
  assert.match(auth, /<h1 class="auth-title">Sort Quiz<\/h1>/);
  assert.match(app, /<span class="lab-mark">RJ<\/span> Sort Quiz<\/div>/);
  for (const source of [auth, app, html]) assert.doesNotMatch(source, /Sort Lab/);
});
