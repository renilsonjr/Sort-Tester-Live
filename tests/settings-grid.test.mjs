// The owner's screenshots of 2026-11-26: on the desktop Settings screen the
// two columns were staggered and Back sat 10px right of the title.
//
// Measured at 1440x900 before the fix, with the title at x=296:
//   Back          box x=296, arrow x=306, width 531 -- a full grid cell
//   Profile icon  x=845, on Back's own row, because Back took cell 1
//   every row below it offset by one; Delete account alone
//   the version line, the security badge and the privacy link dealt into
//   cells too, so they sat under different columns for owner and non-owner
//
// After: the arrow is at 296 with the title, Back is 77px wide, and the
// choices pair from the first row (296 | 845, three times; the owner's
// seventh sits alone at the end, which an odd count has to do somewhere).

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');
const app = readFileSync(join(root, 'src/app.js'), 'utf8');
const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('Back crosses both columns, so the choices pair from the first row', () => {
  // This is the stagger. Back is prepended to the panel, so without the
  // span it is dealt a cell and everything after it moves one place.
  assert.match(css, /\.screen-profile > #profile-panel > \.lab-back \{[^}]*grid-column: 1 \/ -1;/);
  assert.match(app, /panel\.prepend\(back\.firstElementChild\);/);
});

test('Back is pulled onto the title\'s line on every screen, hit area intact', () => {
  // The 44px target is made of padding (#331), and the left padding is what
  // pushed the arrow in. A negative margin moves the box, not the padding.
  //
  // It lives on .lab-back itself, not in the desktop block, because the
  // same 10px showed on the phone and on all twelve screens that carry a
  // Back. Putting it here twice would make it -20px on the desktop, which
  // is the mistake this test exists to catch.
  const back = css.match(/\n  \.lab-back \{([^}]*)\}/)[1];
  assert.match(back, /margin-left: -10px/);
  assert.match(back, /min-height: 44px/);
  assert.match(back, /padding: 10px 14px 10px 10px/);
  const desktop = css.match(/\.screen-profile > #profile-panel > \.lab-back \{([^}]*)\}/)[1];
  assert.doesNotMatch(desktop, /margin-left/, 'the pull is on .lab-back; here it would double');
  assert.match(desktop, /justify-self: start/);
});

test('the tail is one block under the columns, not two dealt cells', () => {
  for (const sel of ['#profile-version', '\\.profile-security', '\\.auth-footer']) {
    assert.match(css, new RegExp(`\\.screen-profile > #profile-panel > ${sel}`),
      `${sel} is still dealt into a column`);
  }
});

test('only the column rules are desktop-only; the phone keeps its flex column', () => {
  // #273's rule. The grid rules live inside the 900px block, so below it
  // the panel is the flex column it always was. The arrow's alignment is
  // deliberately NOT in there: the phone had the same indent.
  const cut = html.indexOf('@media (min-width: 900px)');
  const desktop = html.slice(cut), phone = html.slice(0, cut);
  assert.ok(desktop.includes('#profile-panel > .lab-back'), 'the column rule must sit inside the desktop block');
  assert.ok(!phone.includes('#profile-panel > .lab-back'), 'no column rule belongs outside it');
  assert.ok(phone.includes('margin-left: -10px'), 'the arrow alignment must reach the phone');
});
