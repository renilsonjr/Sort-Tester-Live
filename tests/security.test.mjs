import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';
const shiftLogSource = readFileSync(new URL('../src/shiftLog.js', import.meta.url));
const { createShiftLog } = await import(`data:text/javascript;base64,${shiftLogSource.toString('base64')}`);
import { loadAppModules } from './helpers/load-app-modules.mjs';
const { modules: [{ createLanguage }, { SERVICE_LABEL }, destination], cleanup } = await loadAppModules([
  'src/i18n.js', 'src/questions.js', 'src/destination.js',
]);
after(cleanup);

// Exercise the real log renderer with a minimal DOM sink. Passive markup is
// enough to detect HTML interpretation; no executable payload is needed.
const source = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8')
  .replace(/^import .+;\r?\n/gm, '')
  .replace(/\nshowStart\(\);\s*$/, '');

function renderSavedLog(overrides = {}) {
  const entry = {
    name: 'Practice user', total: 1, correct: 1, totalMs: 1000,
    takenAt: 1700000000000, missed: [], ...overrides,
  };
  const values = new Map([['sortTest.shiftLog.v1', JSON.stringify([entry])]]);
  const storage = {
    getItem: (key) => values.get(key) ?? null,
    setItem: (key, value) => values.set(key, value),
  };
  let markup;
  const view = {
    classList: { contains: () => false },
    querySelectorAll: () => [],
    querySelector: (selector) => selector === '#back' ? { addEventListener() {} } : null,
  };
  const app = { replaceChildren() {} };
  const document = {
    documentElement: {},
    getElementById: () => app,
    addEventListener() {},
    createElement: () => ({
      set innerHTML(value) { markup = value; },
      content: { firstElementChild: view },
    }),
  };
  runInNewContext(`${source}\nshowLog();`, {
    document, window: { scrollTo() {} }, localStorage: storage,
    createShiftLog, createLanguage, SERVICE_LABEL, ...destination,
  });
  return markup;
}

test('saved numeric scores still render normally', () => {
  assert.match(renderSavedLog(), /<span class="sc">1\/1<\/span>/);
});

test('stored score fields render as text, never markup', () => {
  const marker = '<b data-security-probe>text</b>';
  const markup = renderSavedLog({ correct: marker, total: marker });
  assert.ok(!markup.includes(marker));
  assert.match(markup, /&lt;b data-security-probe&gt;text&lt;\/b&gt;/);
});

test('names remain escaped when loaded from local storage', () => {
  const marker = '<b data-security-probe>name</b>';
  const markup = renderSavedLog({ name: marker });
  assert.ok(!markup.includes(marker));
  assert.match(markup, /&lt;b data-security-probe&gt;name&lt;\/b&gt;/);
});

test('stored service and destination modifier stay escaped in saved missorts', () => {
  const service = '<b data-security-probe>service</b>';
  const modifier = '<b data-security-probe>modifier</b>';
  const markup = renderSavedLog({ missed: [{ svc: service, destinationModifier: modifier, state: 'NY', code: '109', outcome: 'wrong', answered: 'BLUE', correctBelt: 'PURPLE' }] });
  assert.ok(!markup.includes(service));
  assert.ok(!markup.includes(modifier));
  assert.match(markup, /&lt;b data-security-probe&gt;service&lt;\/b&gt;/);
  assert.match(markup, /&lt;b data-security-probe&gt;modifier&lt;\/b&gt;/);
});
