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

test('Home states the prize in English and Spanish', () => {
  // This used to read the sentence under the Ranked card's title -- "15
  // questions, ten seconds each. The top 3 win a UPS hat." -- which the
  // owner had removed as repetition. What it was guarding is that Home
  // says what the prize IS, in both languages, and Home still does: the
  // prize tile two stripes down carries the cap picture with "UPS hat"
  // over "Top 3 prize". The evidence moved; the guarantee did not.
  // The "Play for the podium" title went with the label cuts: the gold
  // eyebrow one line above already says Ranked, so the title repeated the
  // place and said no fact. The eyebrow is now the guard.
  assert.ok(home.includes("t('Ranked')"), 'Home should name the Ranked block');
  for (const label of ['UPS hat', 'Top 3 prize']) {
    assert.ok(home.includes(`t('${label}')`), `the prize tile should show: ${label}`);
  }
  const language = createLanguage();
  assert.equal(language.text('UPS hat'), 'UPS hat');
  language.set('es');
  assert.match(language.text('UPS hat'), /Gorra de UPS/);
  assert.match(language.text('Top 3 prize'), /top 3/);
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

test('the Ranked card carries the balance, the badge, the meter and the button', () => {
  // "Your climb" used to be a block of its own two stripes down. The card
  // now says all of it, so a regression that splits them again shows here.
  const hero = home.slice(home.indexOf('home-split-hero'), home.indexOf('home-split-actions'));
  for (const hook of ['id="home-ident"', 'id="home-badge"', 'id="home-progress"', 'id="home-ranked"', 'class="home-prize"']) {
    assert.ok(hero.includes(hook), `the Ranked stripe should hold ${hook}`);
  }
  assert.ok(hero.indexOf('id="home-progress"') < hero.indexOf('id="home-ranked"'), 'the meter sits above the button');
  assert.ok(hero.indexOf('id="home-ranked"') < hero.indexOf('class="home-prize"'), 'the prize line sits under the card');
  assert.doesNotMatch(home, /home-split-climb|Your climb/);
  const fill = app.slice(app.indexOf('async function fillHomeIdentity'), app.indexOf('// The season bubble (#452;'));
  for (const hook of ['#home-ident', '#home-badge', '#home-progress']) assert.ok(fill.includes(hook));
});

test('Home offers the three ways to practise in one row, in both languages', () => {
  const row = home.slice(home.indexOf('home-trio'), home.indexOf("t('Your sessions')"));
  const order = ['id="home-handler"', 'id="home-practice"', 'id="home-study"'].map((id) => row.indexOf(id));
  assert.ok(order.every((at) => at > 0) && order[0] < order[1] && order[1] < order[2]);
  for (const label of ['Handler', 'Practice', 'Chart']) assert.ok(row.includes(`t('${label}')`));
  const css = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
  assert.match(css, /\.home-trio \{ grid-template-columns: repeat\(3, minmax\(0, 1fr\)\); \}/);
  const language = createLanguage();
  language.set('es');
  assert.equal(language.text('Chart'), 'Tabla');
});
