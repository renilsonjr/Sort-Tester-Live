// The visual backlog: six issues left open across rounds 3 to 7, walked at
// 375x812 in both themes, with a real tie-break round opened in the local
// database to reach the three that need one.
//
// #436 the tie-break block was the only one on Ranked with no eyebrow --
//      measured [Ranked, Standings, Season] with the row loose between the
//      last two. After: [Ranked, Prize tie-break, Standings, Season].
// #435 its route prompt had `background: rgba(0,0,0,0)` and `border: 0`
//      while the Ranked question's is a bordered card. After: the same card.
// #437 a 12-word rule sat in the label style, 11px uppercase. After: 15px,
//      sentence case.
// #400 the submitted screen's way out was a 335x52 ghost. After: the
//      compact Back, 77x44, first, and no full-width button left.
// #414 the Ranked history borrowed the overview's header, so its title was
//      the username. After: "Ranked history" / "Historial de Clasificatorio".
// #412 one unbroken 40-character badge ID pushed the Shift log 240px
//      sideways at 375. After: 0, the name wrapping inside its column, also
//      measured at 320.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#436 the tie-break row sits in a named stripe', () => {
  const at = app.indexOf("id=\"tiebreak-go\"");
  const block = app.slice(app.lastIndexOf('box.innerHTML', at), at);
  assert.match(block, /<section class="home-stripe">/);
  assert.match(block, /<p class="lab-eyebrow">\$\{esc\(t\('Prize tie-break'\)\)\}<\/p>/);
});

test('#435 the tie-break route wears the same card as the Ranked one', () => {
  assert.match(app, /<div class="rq-prompt rq-route home-spot">\s*\n\s*<p class="rq-service">\$\{esc\(where\.service\)\}<\/p>\s*\n\s*<p class="rq-code">\$\{esc\(where\.code\)\}<\/p>\s*\n\s*<\/div>\s*\n\s*<p class="lab-eyebrow rq-cue">/);
  // and the bare one is gone
  assert.doesNotMatch(app, /<div class="rq-prompt">/);
});

test('#437 the tie-break rule is prose, not a label', () => {
  assert.match(app, /<p class="lab-intro">\$\{esc\(t\('No feedback: whether you were right stays hidden until the round closes\.'\)\)\}<\/p>/);
});

test('#400 the submitted screen uses the compact Back, first', () => {
  const start = app.indexOf('function showTiebreakSubmitted(');
  const body = app.slice(start, app.indexOf('\nfunction ', start + 1));
  assert.match(body, /<section class="lab-screen">[\s\S]{0,420}?\$\{backLink\('tb-back'\)\}/);
  assert.doesNotMatch(body, /<button id="tb-back" class="ghost">/);
  assert.match(body, /view\.querySelector\('#tb-back'\)/);
});

test('#414 the history names itself, and only the overview keeps the card', () => {
  const start = app.indexOf('function showProfile(');
  const body = app.slice(start, app.indexOf('\n// The name and tag come from', start));
  assert.match(body, /\$\{tab !== 'overview' \? `/);
  assert.match(body, /t\(tab === 'settings' \? 'Settings' : 'Ranked history'\)/);
  assert.match(body, /<div class="pf-ident">/);
});

test('#414 the title has Spanish, and says which history', () => {
  // Not "Shift history": the Shift log is the practice list this phone
  // keeps, and these are the Ranked attempts the server settled.
  assert.match(i18n, /'Ranked history': 'Historial de Clasificatorio',/);
});

test('#412 a long badge ID can break inside the log row', () => {
  // A grid item will not go below its own content, so the column needs the
  // smaller min-width as well as the break.
  assert.match(css, /\.logl \.who \{ overflow-wrap: anywhere; min-width: 0; \}/);
});
