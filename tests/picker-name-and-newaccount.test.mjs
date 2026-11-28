// Round 1 of the interface review, third group: the three screens that never
// got the app's structure. #331 (the test picker), #332 ("Quiz yourself" was
// the only screen with no card) and #333 (the new-account screen).
//
// Measured in the running app at 375px, 820px and 1440px, night and day,
// EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';
import { screensSource } from './helpers/screens-source.mjs';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = screensSource();
const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');
const i18n = readFileSync(join(root, 'src/i18n.js'), 'utf8');

// The comments explain the very things that were removed, so a plain search
// would match the prose saying they are gone.
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');
const js = app.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
const authJs = auth.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');

test('#331 the picker uses the app row, not a component of its own', () => {
  // .deckbtn was restyled independently in each of the four skin layers in
  // index.html and was the only list in the app that did not look like the
  // Practice tab's rows. It is gone, markup and CSS.
  assert.doesNotMatch(js, /class="deckbtn/);
  assert.doesNotMatch(css, /deckbtn/);
  assert.doesNotMatch(css, /\.dsort|\.dname|\.dblurb|\.dmeta/);
  assert.match(js, /<button class="lab-choice lab-choice-quiz" type="button" data-deck=/);
  assert.match(js, /view\.querySelectorAll\('\.lab-choice\[data-deck\]'\)/);
});

test('#331 every playable test shows the arrow, and no locked one does', () => {
  // Nothing said a test card was tappable while the identical-looking
  // Practice cards had both an icon tile and an arrow.
  const row = js.slice(js.indexOf('function deckRow'));
  assert.match(row, /<span class="lab-choice-icon" aria-hidden="true">\$\{icon\}<\/span>/);
  assert.match(row, /if \(locked\) return `<div class="lab-choice locked">\$\{body\}<\/div>`;/);
  assert.match(row, /\$\{body\}<span class="lab-arrow" aria-hidden="true">→<\/span>/);
  // A deck not yet checked against the chart is not playable, so it must not
  // be a button either.
  assert.doesNotMatch(row.slice(0, row.indexOf('return `<button')), /<button[^>]*locked/);
});

test('#331 the sort name is said once per section, not once per card', () => {
  // "TWILIGHT" repeated on all ten cards while the heading above the list
  // already said it.
  assert.doesNotMatch(js, /Twilight<\/em>/);
  assert.doesNotMatch(js, /class="dsort"/);
  assert.match(js, /<p class="lab-eyebrow">\$\{esc\(t\('Levels · Twilight'\)\)\}<\/p>/);
  assert.match(js, /<p class="lab-eyebrow">\$\{esc\(t\('Current quizzes · Twilight'\)\)\}<\/p>/);
  assert.match(i18n, /'Levels · Twilight': 'Niveles · Twilight'/);
  // The h2 that used to carry it is gone, along with its two skin rules.
  assert.doesNotMatch(js, /lab-picker-heading/);
  assert.doesNotMatch(css, /lab-picker-heading/);
});

test('#331 Back is one shared compact control, not a full-width button', () => {
  // Measured: 335x52 before -- the shape of a primary action, and the
  // heaviest thing on the picker. 88x44 after, still over the 44px minimum.
  assert.match(css, /\.lab-back \{[^}]*min-height: 44px/);
  assert.match(css, /\.lab-back \{[^}]*align-self: flex-start/);
  assert.match(css, /\.lab-back \{[^}]*background: transparent/);
  assert.match(js, /function backLink\(id\)/);
  // Both places that had a Back go through it.
  // The picker became the Practice tab on 2026-11-27 and has no Back; the
  // name screen, which is still a sub-screen, has the shared one.
  assert.match(js, /\$\{backLink\('name-back'\)\}/);
  assert.match(js, /backLink\('profile-back'\)/);
});

test('#332 the quiz-name screen has an eyebrow and a card', () => {
  // It was the only screen in the app with a bare heading and with its field
  // and buttons standing straight on the background.
  const screen = js.slice(js.indexOf('function showNameEntry'), js.indexOf('function chartRow'));
  assert.match(screen, /<p class="lab-eyebrow">\$\{esc\(t\('Practice'\)\)\}<\/p>\s*\n\s*<h1 class="lab-title">\$\{esc\(t\('Quiz yourself'\)\)\}<\/h1>/);
  assert.match(screen, /<div class="auth-card">[\s\S]*id="name"[\s\S]*id="begin"[\s\S]*<\/div>/);
  // Back is a way out, not part of the task the card holds, so it stays
  // outside it -- before the title, like every other sub-screen.
  assert.ok(screen.indexOf("backLink('name-back')") < screen.indexOf('<div class="auth-card">'),
    'Back was pulled inside the card');
  assert.doesNotMatch(screen, /id="back"/);
});

test('#333 the Quiz Code can be copied, and a refusal says so', () => {
  // This is the only time a Quiz Code is ever shown. Without this the player
  // retyped 19 characters by hand or lost the account.
  assert.match(authJs, /<button id="copy-login-id" class="code-copy" type="button">/);
  assert.match(authJs, /await navigator\.clipboard\.writeText\(field\.value\)/);
  // A browser can refuse the clipboard even in a secure context, so the
  // refusal selects the code and says to copy it by hand rather than failing
  // silently. Verified: the pane this was measured in denies clipboard-write,
  // and the fallback is the path that ran.
  assert.match(authJs, /\} catch \{\s*\n\s*field\.select\(\);/);
  assert.match(authJs, /Could not copy\. Select the code and copy it by hand\./);
});

test('#333 the confirmation is one tappable row with a real label', () => {
  // It was a raw browser checkbox, centred, with its text on the next line,
  // not tied to it -- so it had no accessible name and only the 13px box
  // itself was tappable.
  assert.doesNotMatch(authJs, /<input id="saved-check" type="checkbox"> I saved/);
  assert.match(authJs, /<label class="check-row" for="saved-check">/);
  assert.match(authJs, /<span class="check-label">\$\{forgotText\('I saved my Quiz Code'\)\}<\/span>/);
  assert.match(css, /\.check-row \{[^}]*min-height: 44px/);
  // The real input stays in the DOM for the keyboard and for screen readers;
  // only the drawn square follows it.
  // The selectors are shared with .delete-ack since #419, which gave the
  // delete acknowledgement this same control instead of the browser's, so
  // they are matched per selector rather than as one exact string.
  assert.match(css, /\.check-row input[^{]*\{ position: absolute; opacity: 0;/);
  assert.match(css, /\.check-row input:checked \+ \.check-box/);
  assert.match(css, /\.check-row input:focus-visible \+ \.check-box[^{]*\{ outline: 3px solid var\(--focus\)/);
});

test('#333 the code field still fits beside the Copy button', () => {
  // Measured at 375px: at the field's normal 18px with its 0.9px spacing the
  // code was 36px wider than the space left, so it scrolled sideways on the
  // one screen where it is ever shown. The rule has to beat
  // `.auth-screen input[readonly]`, which is why it is scoped.
  assert.match(css, /\.auth-screen \.code-row input \{[^}]*font-size: 15px/);
  assert.match(css, /\.auth-screen \.code-row input \{[^}]*letter-spacing: normal/);
  assert.match(css, /\.code-copy \{[^}]*min-height: 44px/);
});

test('#333 the whole new-account flow is in both languages', () => {
  // Translating half of it would have left "Continue" in English beside a
  // Spanish tick row, which reads worse than the all-English screen it
  // replaced.
  for (const [en, es] of [
    ['Choose a username', 'Elige un nombre de usuario'],
    ['Create account', 'Crear cuenta'],
    ['Save this Quiz Code. It will not be shown again.', 'Guarda este Quiz Code. No se volverá a mostrar.'],
    ['Your Quiz Code', 'Tu Quiz Code'],
    ['Continue', 'Continuar'],
    ['I saved my Quiz Code', 'Guardé mi Quiz Code'],
    ['Copy', 'Copiar'],
  ]) {
    assert.ok(auth.includes(`'${en}':\n    '${es}',`), `${en} has no Spanish`);
    assert.ok(authJs.includes(`forgotText('${en}')`), `${en} is not run through the translator`);
  }
});
