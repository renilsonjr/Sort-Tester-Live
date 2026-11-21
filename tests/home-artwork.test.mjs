import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ createLanguage }], cleanup } = await loadAppModules(['src/i18n.js']);
after(cleanup);

// Read the actual home alt source so the translation check also catches
// a copy edit that accidentally loses its Spanish dictionary entry.
const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const home = app.slice(app.indexOf('function showStart()'), app.indexOf('async function fillLaunchCallout'));
const poster = home.match(/<img src="assets\/home-podium\.jpg"[^>]*alt="\$\{esc\(t\(\s*'([^']+)'/);

test('the home poster describes its message in English and Spanish', () => {
  assert.ok(poster, 'The home artwork needs localized alternative text');
  const language = createLanguage();
  assert.match(language.text(poster[1]), /Reach the top 3/);
  assert.match(language.text(poster[1]), /Win a UPS hat/);
  language.set('es');
  const spanish = language.text(poster[1]);
  assert.match(spanish, /Llega al top 3/);
  assert.match(spanish, /Gana una gorra de UPS/);
  assert.match(spanish, /podio dorado/);
});

test('the shipped home artwork stays inside a 150 KiB phone download budget', () => {
  const jpeg = readFileSync(new URL('../assets/home-podium.jpg', import.meta.url));
  assert.equal(jpeg.readUInt16BE(0), 0xffd8, 'Ship the optimized JPEG');
  assert.ok(jpeg.length <= 150 * 1024, `Home artwork is ${jpeg.length} bytes`);
});
