// Know the chart, regrouped (2026-11-28). Measured on a 390x844 phone
// before the change: 8,844px of page, the first route at y=607, and the
// service chips and the search scrolling away with it.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

const study = (() => {
  const from = app.slice(app.indexOf('function showStudy()'));
  return from.slice(0, from.indexOf('\n}\n'));
})();

test('the filters stay on the screen while the list scrolls', () => {
  // 68px is the app header, which is sticky and 67px tall here.
  assert.match(html, /\n  \.chart-aside \{\n    display: block; position: sticky; top: 68px; z-index: 6;/);
  assert.match(html, /\n  \.chart-aside \{[^}]*background: var\(--bg\);/s, 'the bar must be opaque');
  // One line that scrolls sideways, instead of four chips over two lines.
  assert.match(html, /\n  \.chart-aside \.lab-service-tabs \{ display: flex; flex-wrap: nowrap; overflow-x: auto;/);
});

test('the desktop column keeps its own shape', () => {
  const desk = html.slice(html.lastIndexOf('@media (min-width: 900px)'));
  assert.match(desk, /\.screen-chart > \.chart-aside \{[^}]*margin: 0;[^}]*background: none;[^}]*border-bottom: 0;/s);
  assert.match(desk, /\.screen-chart > \.chart-aside \{[^}]*position: sticky;/s);
});

test('nothing on the screen says the same thing twice', () => {
  // The heading named the service the pressed chip already names, and
  // "Twilight chart" what the eyebrow already says.
  assert.doesNotMatch(study, /lab-chart-heading|service-title/);
  // The count moved under the search, where the search changes it.
  assert.ok(study.indexOf('id="chart-search"') < study.indexOf('id="chart-count"'));
  assert.match(study, /<p id="chart-count" class="lab-chart-count" role="status">/);
});

test('the search keeps its label for a screen reader', () => {
  assert.match(study, /<label class="lab-search-label" for="chart-search">/);
  assert.match(html, /\n  \.chart-aside \.lab-search-label \{\n    position: absolute; width: 1px; height: 1px;/);
});

test('the routes are one card of rows, the code first', () => {
  assert.match(html, /\n  #chart-rows \{ display: flex; flex-direction: column; gap: 2px; padding: 6px; border-radius: var\(--r-md\);/);
  assert.match(html, /\n  #chart-rows \.lab-chart-row \{ margin: 0; padding: 8px 10px;[^}]*border: 0;/);
  assert.match(html, /\n  #chart-rows \.lab-chart-row strong \{ order: 1;/);
  assert.match(html, /\n  #chart-rows \.lab-chart-state \{ order: 2;/);
  // a route with a note keeps the note on its own line
  assert.match(html, /\n  #chart-rows \.lab-chart-row small \{ order: 3; flex-basis: 100%;/);
});

test('the title is a title, not a page heading', () => {
  assert.match(html, /\n  \.screen-chart > \.lab-title \{ font-size: 24px; \}/);
});
