// Round 6: #430, #431, #432 and #433, all on the owner screens, all walked
// signed in as the owner at 375x812 in both themes.
//
// #430 the destructive buttons were 39px: Delete 70x39 (x37) and Withdraw
//      93x39, because `.approved .ghost` carried `min-height: 0`, cancelling
//      the 44 that .ghost gives everything else -- while its neighbour
//      `.case-actions .ghost` kept its 44. Measured after: 70x44, rows
//      unchanged at 67px.
// #431 sentences of 19, 21 and 31 words were set in the label style
//      (.lab-study-meta, 11px uppercase). Measured after: 15px, sentence
//      case, none left on any owner screen.
// #432 section headings were 16px/900 grey -- bigger and heavier than the
//      eyebrow naming the screen. Measured after: 11px gold on all six.
// #433 the way out was a full-width ghost under six rows. Measured after:
//      the compact .lab-back, 77x44, first on all seven screens.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const owner = readFileSync(join(root, 'src/ownerScreens.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

const BACKS = ['owner-back', 'elig-back', 'acct-back', 'sel-back', 'case-back', 'rec-back', 'msg-back'];

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('#430 the owner buttons keep the app\'s minimum', () => {
  assert.match(css, /\.approved \.ghost \{ flex: none; width: auto; min-height: 44px;/);
  assert.doesNotMatch(css, /\.approved \.ghost \{[^}]*min-height: 0/);
});

test('#430 the rows stay compact', () => {
  // The small padding and 13px type stay: a list of 37 accounts still has
  // to be scannable. The minimum does the work on its own.
  assert.match(css, /\.approved \.ghost \{[^}]*padding: 9px 13px; font-size: 13px;/);
});

test('#431 the owner sentences are in the prose style', () => {
  for (const sentence of [
    'The roster reference is how you identify this person on your own roster',
    'The tag is on their profile. It is how you find the account, not proof of who they are',
    'A tie comes here only when the rules say so',
  ]) {
    const at = owner.indexOf(sentence);
    assert.notEqual(at, -1, `${sentence.slice(0, 30)}... is gone`);
    const opener = owner.lastIndexOf('<p class=', at);
    assert.match(owner.slice(opener, opener + 22), /<p class="lab-intro"/, `${sentence.slice(0, 30)}... is still a label`);
  }
  // the Case review pair, which is a ternary rather than one string
  assert.match(owner, /<p class="lab-intro">\$\{esc\(kind === 'flags'/);
});

test('#431 the label style is left to labels', () => {
  // .lab-study-meta is the app's small-label class and is still used as
  // one -- the quiz cue, the balance line. This issue was about sentences
  // wearing it, not about the class.
  assert.match(app, /<p class="lab-study-meta">\$\{esc\(t\('Your balance'\)\)\}<\/p>/);
});

test('#432 the owner headings wear the eyebrow', () => {
  assert.equal((owner.match(/<h2 class="lab-eyebrow owner-count">/g) ?? []).length, 3);
  for (const heading of ['Approve a sorter', 'Nothing waiting', 'Who is in front of you?']) {
    assert.match(owner, new RegExp(`<h2 class="lab-eyebrow">\\$\\{esc\\(t\\('${heading.replace('?', '\\?')}'\\)\\)\\}</h2>`),
      `${heading} is not an eyebrow`);
  }
});

test('#432 the old heading sizes are gone, not merely overridden', () => {
  // `.owner-form h2` was one class plus an element, so it would have BEATEN
  // .lab-eyebrow and left those three headings at 16px.
  assert.doesNotMatch(css, /\.owner-form h2 \{/);
  assert.match(css, /\.owner-count \{ margin-top: 4px; \}/);
  assert.doesNotMatch(css, /\.owner-count \{[^}]*font-size/);
});

test('#433 every owner screen has the compact Back, first', () => {
  for (const id of BACKS) {
    assert.match(owner, new RegExp(`\\$\\{backLink\\('${id}'\\)\\}`), `${id} is not a backLink`);
    assert.doesNotMatch(owner, new RegExp(`<button id="${id}" class="ghost"`), `${id} is still a full-width ghost`);
  }
});

test('#433 the menu\'s Back is inside its screen', () => {
  // Placed before the section first time round, where it rendered outside
  // the screen it belongs to.
  assert.match(owner, /<section class="lab-screen screen-owner">\s*\n\s*\$\{backLink\('owner-back'\)\}/);
});
