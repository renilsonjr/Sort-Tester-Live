// #341: the four header controls measured 40x38 in the running app, below
// the 44x44 touch minimum.
//
// The source was not the obvious place to look: two earlier rules in this
// file already set 44x44 on these four, and a later compact-header layer was
// quietly undoing both. Measured, not read.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');

const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('#341 no rule shrinks the header controls below the minimum', () => {
  // This is the one that was winning. Any rule that sets a size on these
  // two selectors has to keep them at 44 or more.
  assert.doesNotMatch(css, /\.lab-language button, \.lab-theme-btn \{ width: 40px; min-height: 38px;/);
  for (const m of css.matchAll(/\.lab-language button, \.lab-theme-btn \{([^}]*)\}/g)) {
    const w = m[1].match(/width: (\d+)px/);
    const h = m[1].match(/min-height: (\d+)px/);
    if (w) assert.ok(Number(w[1]) >= 44, `a rule sets width ${w[1]}px`);
    if (h) assert.ok(Number(h[1]) >= 44, `a rule sets min-height ${h[1]}px`);
  }
});

test('#341 the narrow phone drops the wordmark, not the targets', () => {
  // Measured at 320px: the header row has 284px to give, and the brand plus
  // four 44px controls want 321px. It already overflowed BEFORE this change,
  // at 303px, with the theme button clipped at the right edge -- so this is
  // a fix for a pre-existing bug as much as for the new width.
  // Targets win over the wordmark; the RJ mark stays.
  assert.match(css, /@media \(max-width: 360px\) \{[\s\S]{0,120}\.lab-wordmark \{ display: none; \}/);
  // The wordmark was a bare text node, which CSS cannot reach on its own.
  assert.match(app, /<span class="lab-mark">RJ<\/span> <span class="lab-wordmark">Sort Quiz<\/span>/);
});

test('#341 the app is still named where the wordmark is hidden', () => {
  // Hiding it on a 320px phone is only acceptable because the name is still
  // on the sign-in screen and in the page title.
  const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');
  assert.match(html, /<title>Sort Quiz<\/title>/);
  assert.match(auth, /<h1 class="auth-title">Sort Quiz<\/h1>/);
});
