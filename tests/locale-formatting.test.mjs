// #442: every date, time and grouped number in the app was formatted with
// no locale, so it followed the language of the PHONE rather than the EN/ES
// switch. Measured in the running app at 375x812, on a US English machine:
//
//   EN  "It started on 11/13/2026."
//   ES  "Empezó el 11/13/2026."      <- day 11 of month 13, which is not a date
//
// Thirty-eight call sites in src/app.js, one of which -- the Shift log's
// timestamp -- had already been given `es-US` by hand. That one site is why
// the locale below is es-US and not something else: somebody had already
// made the call, and this spreads it rather than overruling it.
//
// Measured before choosing, because the Spanish variants disagree:
//
//   es-ES   13/11/2026   1.234.567   24-hour
//   es-US   13/11/2026   1,234,567   12-hour, a.m./p.m.
//   es-419  13/11/2026   1,234,567   12-hour
//
// Only the day and month order was ever wrong for these players. They work
// in New Jersey, so the comma and the 12-hour clock are what they read
// everywhere else, including on their colleagues' English screens.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

test('#442 nothing in the app formats a date or a number on its own', () => {
  // The guard that matters. A new screen that reaches for toLocaleDateString
  // fails here, which is the only way this does not drift back.
  assert.doesNotMatch(app, /toLocaleDateString|toLocaleTimeString|toLocaleString/,
    'a call site is formatting without the app language');
});

test('#442 the formatters live beside the words they are read with', () => {
  assert.match(i18n, /date\(value\) \{/);
  assert.match(i18n, /dateTime\(value\) \{/);
  assert.match(i18n, /number\(value\) \{/);
  // All three read the same table, so they cannot drift apart.
  assert.equal((i18n.match(/LOCALES\[code\]/g) ?? []).length, 4);
});

test('#442 Spanish is American Spanish, with fallbacks', () => {
  // es-US first; es-419 and es for an engine that does not know it. An
  // engine that knows none of them still gets the day before the month,
  // which is the part that was wrong.
  assert.match(i18n, /const LOCALES = \{ en: \['en-US'\], es: \['es-US', 'es-419', 'es'\] \};/);
});

test('#442 a value that is not a date does not reach the screen as one', () => {
  // Found by running the helper rather than by reading it: the first
  // version guarded NaN only, and `new Date(null)` is not NaN -- it is the
  // epoch. A ticket with no resolved_at rendered as "31/12/1969" inside a
  // sentence. The API sends null for every absent date, so this is the
  // common case, not the edge one.
  assert.match(i18n, /if \(value === null \|\| value === undefined \|\| value === ''\) return null;/);
  assert.match(i18n, /return when === null \? '' : when\.toLocaleDateString\(LOCALES\[code\]\);/);
  assert.match(i18n, /return when === null \? '' : when\.toLocaleString\(LOCALES\[code\]\);/);
  assert.match(i18n, /Number\.isFinite\(n\) \? n\.toLocaleString\(LOCALES\[code\]\) : ''/);
});

test('#442 the helper behaves, run rather than read', async () => {
  // Through the sandbox loader rather than a bare import: a plain
  // `import('../src/i18n.js')` is read as CommonJS on a machine with a
  // package.json above the repo, which is how the two long-standing local
  // failures happen. This one should not join them.
  const { modules, cleanup } = await loadAppModules(['src/i18n.js']);
  const { createLanguage } = modules[0];
  const language = createLanguage(null);
  const when = '2026-11-13T15:59:29Z';

  assert.equal(language.date(when), new Date(when).toLocaleDateString(['en-US']));
  language.set('es');
  assert.equal(language.date(when), new Date(when).toLocaleDateString(['es-US', 'es-419', 'es']));

  // The day comes before the month in Spanish and after it in English:
  // the whole point of the issue, asserted on the parts rather than on a
  // literal, so it holds wherever the suite runs.
  const es = language.date(when).split('/');
  language.set('en');
  const en = language.date(when).split('/');
  assert.equal(es[0], en[1], 'the Spanish date should lead with the day');
  assert.equal(es[1], en[0], 'the English date should lead with the month');

  for (const empty of [null, undefined, '', 'nonsense', NaN]) {
    assert.equal(language.date(empty), '', `date(${String(empty)}) should be empty`);
    assert.equal(language.dateTime(empty), '', `dateTime(${String(empty)}) should be empty`);
  }
  assert.equal(language.number('nonsense'), '');
  assert.equal(language.number(0), '0');
  assert.equal(language.number(-145), '-145');
  await cleanup();
});

test('#442 the deadline a player can miss goes through it', () => {
  // The tie-break round is played once, before it closes. A deadline read
  // in the wrong day/month order is a missed round, which is why this one
  // is pinned by name rather than left to the sweep above.
  assert.match(app, /const closes = language\.dateTime\(round\.deadline_at\);/);
});

test('#442 the season notice, where this was found, is formatted too', () => {
  // #452 moved the notice's wording to seasonNotice.js, which formats every
  // date in the player's locale, read in Eastern time.
  const notice = readFileSync(new URL('../src/seasonNotice.js', import.meta.url), 'utf8');
  assert.match(notice, /const started = longDate\(notice\.started_at, locale\);/);
  assert.match(notice, /const closes = notice\.closes_at \? longDate\(notice\.closes_at, locale\) : null;/);
  assert.match(app, /seasonBubbleCopy\(notice, \{ t, locale: language\.locale/);
});

test('#442 the exported workbook follows the player too', () => {
  // It is the one place the formatting leaves the app, and a spreadsheet
  // full of US dates handed to a Spanish reader is the same defect.
  assert.equal((app.match(/Taken: language\.dateTime\(s\.takenAt\)/g) ?? []).length, 2);
});
