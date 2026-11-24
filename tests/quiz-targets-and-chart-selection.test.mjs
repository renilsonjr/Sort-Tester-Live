// Round 3 of the interface review, the two HIGH findings: #379 (the quiz's
// own header kept its language buttons at 40px wide) and #380 (on the chart
// you could not tell which service you were reading).
//
// Measured in the running app at 320, 375 and 1440, night and day, EN and ES.

import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const root = join(dirname(fileURLToPath(import.meta.url)), '..');
const html = readFileSync(join(root, 'index.html'), 'utf8');

const css = html.replace(/\/\*[\s\S]*?\*\//g, '');

test('#379 no rule leaves the quiz language buttons under 44px wide', () => {
  // #341 raised the main header's four. The quiz has a header of its own,
  // and two separate rules were holding these two at 38px and 40px. Both are
  // raised, including the one that does not win today -- leaving a smaller
  // number behind is exactly the trap #341 fell into.
  const rules = [...css.matchAll(/\.quiz-topline \.lab-language button \{([^}]*)\}/g)];
  assert.ok(rules.length >= 2, 'the quiz header rules are gone');
  for (const m of rules) {
    const w = m[1].match(/width: (\d+)px/);
    assert.ok(w, `a quiz header rule sets no width: ${m[1]}`);
    assert.ok(Number(w[1]) >= 44, `a quiz header rule sets width ${w[1]}px`);
  }
  // Measured after: 44x44 on the question screen and the feedback screen, at
  // 320 and 375 and 1440, both themes, both languages, with the top line
  // never overflowing and no two controls touching.
});

test('#380 the selected service is marked by what it has, not what it lacks', () => {
  // It used to be var(--accent) on both the fill and the border, which meant
  // selecting a chip took its outline away and lifted the fill by 1.20:1 at
  // night and 1.18:1 in day. Marking by subtraction, as in #337.
  const rule = css.match(/\.lab-service-tabs button\[aria-pressed="true"\] \{([^}]*)\}/g);
  assert.ok(rule, 'the selected-service rule is gone');
  const live = rule[rule.length - 1];
  assert.match(live, /background: var\(--gold\)/);
  assert.match(live, /color: #38261b/);
  // The border is the darker gold, NOT the fill repeated: measured, the gold
  // fill separates selected from unselected by 10.04:1 at night but only
  // 2.84:1 in day, under the 3:1 a state difference needs. The edge carries
  // it at 3.89:1 without darkening the fill, which would have taken the
  // label below its own 4.5:1 (it measures 4.88:1 in day, 8.34:1 at night).
  assert.match(live, /border-color: var\(--gold-line\)/);
  assert.doesNotMatch(live, /border-color: var\(--gold\)\s*;/);
});

test('#380 this is the treatment the app already uses for "this one"', () => {
  // Gold fill, #38261b label -- the same pair the bottom dock uses for the
  // current tab, so the app says "selected" one way, not two.
  assert.match(css, /\.lab-nav button\[aria-current="page"\] \{[^}]*background: var\(--gold\)[^}]*color: #38261b/);
});
