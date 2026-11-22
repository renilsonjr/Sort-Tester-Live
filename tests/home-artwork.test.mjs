import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const { modules: [{ createLanguage }], cleanup } = await loadAppModules(['src/i18n.js']);
after(cleanup);

// Home opens on the Ranked card now (the poster left the screen). Read the
// actual home source, so a copy edit that loses the prize or its Spanish
// entry is caught here.
const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const home = app.slice(app.indexOf('function showStart()'), app.indexOf('async function fillLaunchCallout'));

test('Home no longer carries the poster', () => {
  assert.doesNotMatch(home, /home-podium\.jpg/);
});

test('the Ranked card states the prize in English and Spanish', () => {
  for (const sentence of ['Play for the podium', 'The top 3 win a UPS hat.']) {
    assert.ok(home.includes(`t('${sentence}')`), `Home should show: ${sentence}`);
  }
  const language = createLanguage();
  assert.match(language.text('The top 3 win a UPS hat.'), /top 3 win a UPS hat/);
  language.set('es');
  assert.match(language.text('Play for the podium'), /podio/);
  assert.match(language.text('The top 3 win a UPS hat.'), /gorra de UPS/);
});

test('the prize tile shows the cut-out cap, inside a phone download budget', () => {
  assert.match(home, /src="assets\/prize-hat\.svg"/);
  const svg = readFileSync(new URL('../assets/prize-hat.svg', import.meta.url), 'utf8');
  assert.match(svg, /<clipPath id="cap">/, 'the cap is clipped out of the photo');
  // The page's policy allows images from itself and data: only, so the photo
  // must be embedded rather than fetched from anywhere else.
  assert.doesNotMatch(svg, /href="https?:/);
  assert.ok(svg.length <= 64 * 1024, `Prize artwork is ${svg.length} bytes`);
});

test('the meter fills through the current badge, and Challenger has none', () => {
  const body = app.slice(app.indexOf('function badgeProgress(entry)'), app.indexOf('async function fillHomeIdentity'));
  const BADGE_CAP = { Iron: 1000, Bronze: 2000, Silver: 3000, Gold: 4000 };
  const badgeProgress = new Function('BADGE_CAP', `${body}; return badgeProgress;`)(BADGE_CAP);
  assert.equal(badgeProgress({ badge: 'Bronze', points: 1416 }), 42);
  assert.equal(badgeProgress({ badge: 'Iron', points: 0 }), 0);
  assert.equal(badgeProgress({ badge: 'Iron', points: -30 }), 0, 'a negative total shows an empty meter');
  assert.equal(badgeProgress({ badge: 'Gold', points: 4000 }), 100);
  assert.equal(badgeProgress({ badge: 'Challenger', points: 5200 }), null);
});
