// #452: the season bubble on Home, login and profile.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createLanguage } from '../src/i18n.js';
import { seasonBubbleCopy, showSeasonBubble, longDate } from '../src/seasonNotice.js';

const START = '2026-12-01T05:00:00+00:00';  // Dec 1, 2026, midnight Eastern
const END = '2027-01-01T04:59:00+00:00';
const before = { started: false, label: null, started_at: null, closes_at: null, announced_start: START, announced_end: END };
const live = { started: true, label: 'Season 1', started_at: START, closes_at: END, announced_start: START, announced_end: END };

function lang(code) {
  const l = createLanguage(null);
  l.set(code);
  return { t: (k, v) => l.text(k, v), locale: l.locale };
}

test('before the launch it announces December 1 at midnight Eastern and the reset', () => {
  const copy = seasonBubbleCopy(before, { ...lang('en'), signedIn: false, now: Date.parse('2026-11-24') });
  assert.equal(copy.title, 'The official season starts December 1, 2026');
  assert.match(copy.text, /^It starts at 12:00 AM EST\. Pre-Season points go back to 0 that day\.$/);
});

test('the date is read in Eastern time, not the phone\'s zone', () => {
  // 05:00 UTC is still November 30 in Los Angeles; the season's date is Eastern
  assert.equal(longDate(START, 'en-US'), 'December 1, 2026');
});

test('once launched it says the season is live and when it ends', () => {
  const copy = seasonBubbleCopy(live, { ...lang('en'), signedIn: true, now: Date.parse('2026-12-05') });
  assert.equal(copy.title, 'The official season is live');
  assert.equal(copy.text, 'It ends December 31, 2026. Everyone began again at 0 points and Iron.');
});

test('after its end it says it ended', () => {
  const copy = seasonBubbleCopy(live, { ...lang('en'), signedIn: false, now: Date.parse('2027-01-02') });
  assert.equal(copy.title, 'The official season has ended');
});

test('no notice, or no announced date, shows nothing', () => {
  assert.equal(seasonBubbleCopy(null, { ...lang('en'), signedIn: false }), null);
  assert.equal(seasonBubbleCopy({ started: false }, { ...lang('en'), signedIn: false }), null);
});

test('every bubble sentence has Spanish', () => {
  const es = lang('es');
  const copy = seasonBubbleCopy(before, { ...es, signedIn: false });
  assert.equal(copy.title, 'La temporada oficial empieza el 1 de diciembre de 2026');
  assert.match(copy.text, /Ese día los puntos de la pretemporada vuelven a 0\./);
  const source = readFileSync(new URL('../src/seasonNotice.js', import.meta.url), 'utf8');
  for (const m of source.matchAll(/\bt\('((?:[^'\\]|\\.)*)'/g)) {
    assert.notEqual(es.t(m[1]), m[1], `no Spanish for: ${m[1]}`);
  }
  for (const key of ['Everyone began again at 0 points and Iron.', 'Log in to play for points this season.']) {
    assert.notEqual(es.t(key), key);
  }
});

function fakeBox() {
  const parts = { title: { textContent: '' }, text: { textContent: '' }, close: { setAttribute() {}, onclick: null } };
  return {
    hidden: true,
    parts,
    querySelector(sel) {
      return sel === '[data-bubble-title]' ? parts.title : sel === '[data-bubble-text]' ? parts.text : parts.close;
    },
  };
}

function memory() {
  const m = new Map();
  return { getItem: (k) => m.get(k) ?? null, setItem: (k, v) => m.set(k, v) };
}

test('the X closes it on this device, and the live bubble comes back after the launch', () => {
  const storage = memory();
  const upcoming = seasonBubbleCopy(before, { ...lang('en'), signedIn: false });
  const box = fakeBox();
  showSeasonBubble(box, upcoming, { storage });
  assert.equal(box.hidden, false);
  box.parts.close.onclick();
  assert.equal(box.hidden, true);

  const again = fakeBox();
  showSeasonBubble(again, upcoming, { storage });
  assert.equal(again.hidden, true, 'closed stays closed');

  const liveBox = fakeBox();
  showSeasonBubble(liveBox, seasonBubbleCopy(live, { ...lang('en'), signedIn: true, now: Date.parse('2026-12-05') }), { storage });
  assert.equal(liveBox.hidden, false, 'a new state shows again');
});
