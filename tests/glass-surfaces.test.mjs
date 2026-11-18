// The glass rule names the surfaces that get the blurred, translucent
// treatment. A class listed there that nothing ever renders is the worst
// kind of CSS bug: nothing breaks, no error appears, and the screen it
// was meant for simply keeps its old look.
//
// That happened with `.leaderboard-card`, which was written into the
// glassmorphism redesign while the leaderboard actually renders
// `<ol class="board">` with one `<li>` per player. The rule was correct
// CSS pointing at an element that does not exist.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync } from 'node:fs';

// Every module, not just app.js: `.auth-card` is rendered by auth.js, and
// a guard that read one file would have called it dead.
const srcDir = new URL('../src/', import.meta.url);
const app = readdirSync(srcDir)
  .filter((name) => name.endsWith('.js'))
  .map((name) => readFileSync(new URL(name, srcDir), 'utf8'))
  .join('\n');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function glassSelector() {
  // Anchored on a surface only this rule names. Matching "the first rule
  // using --glass-surface-sub" broke the moment a second rule used it:
  // the guard then inspected `.ghost` and reported the real rule missing.
  const match = page.match(/^\s*([^\n{]*,\s*\.board li)\s*\{/m);
  assert.ok(match, 'the multi-surface glass rule is missing from index.html');
  return match[1];
}

test('every surface the glass rule names is actually rendered', () => {
  const selectors = glassSelector()
    .split(',')
    .map((s) => s.trim())
    .filter(Boolean);
  assert.ok(selectors.length > 3, 'expected several surfaces in the rule');

  for (const selector of selectors) {
    // `.board li` and the like: the class is what gets rendered, the
    // element part is structure the selector adds.
    const klass = selector.split(/\s+/)[0].replace(/^\./, '');
    const rendered =
      app.includes(`"${klass}`) ||
      app.includes(`'${klass}`) ||
      app.includes(` ${klass}`) ||
      page.includes(`class="${klass}`) ||
      page.includes(`class="${klass} `);
    assert.ok(
      rendered,
      `the glass rule styles .${klass}, but nothing renders that class`,
    );
  }
});

test('the leaderboard rows are the glass surface, not a wrapper', () => {
  // The leaderboard has no single card: its rows are the cards. Naming a
  // wrapper here is how the rule came to target nothing.
  assert.match(glassSelector(), /\.board li/);
  assert.doesNotMatch(page, /\.leaderboard-card/);
});

test('a row paints no opaque background over its own glass', () => {
  // An opaque fill on the row sits on top of the translucent one and
  // hides the blur, so the row stops matching every other surface.
  const rowRule = page.match(/^\s*\.board li \{[^}]*\}/m);
  assert.ok(rowRule, '.board li rule is missing');
  assert.doesNotMatch(rowRule[0], /background:/);
});

test('the highlighted rows stay translucent', () => {
  // A tie marker and a hat winner are the same surface lit differently,
  // not a different material.
  for (const state of ['board-tied', 'board-hat']) {
    const rule = page.match(new RegExp(`\\.board li\\.${state} \\{[^}]*\\}`));
    assert.ok(rule, `.board li.${state} rule is missing`);
    assert.match(
      rule[0],
      /background: rgba\(/,
      `.${state} uses an opaque background, which hides the blur`,
    );
  }
});

// --- the entry screen ---

test('the guest card is the same material as the card beside it', () => {
  // `.auth-card.guest` outranks the glass rule, so an opaque fill here
  // is not overridden: it simply wins, and one card reads as solid next
  // to a frosted one.
  const rule = page.match(/\.auth-card\.guest \{[^}]*\}/);
  assert.ok(rule, '.auth-card.guest rule is missing');
  assert.match(rule[0], /background: rgba\(/);
});

test('text inputs are frosted, not opaque panels', () => {
  const rule = page.match(/^\s*input \{[^}]*\}/m);
  assert.ok(rule, 'the input rule is missing');
  assert.match(rule[0], /var\(--glass-surface-sub\)/);
  assert.match(rule[0], /backdrop-filter/);
});

test('the secondary button is glass', () => {
  const rule = page.match(/^\s*\.ghost \{[^}]*\}/m);
  assert.ok(rule, '.ghost rule is missing');
  assert.match(rule[0], /var\(--glass-surface-sub\)/);
});

function primaryRules() {
  // EVERY rule, not the first one. `.primary` is declared twice: an early
  // block sets the shape and a later one sets the colour, and in CSS the
  // later one wins. A guard that matched once inspected a declaration
  // that no longer had any effect, and would have passed while the button
  // was turned to glass further down the file.
  return [...page.matchAll(/^\s*\.primary \{[^}]*\}/gm)].map((m) => m[0]);
}

test('no rule turns the primary action into glass', () => {
  // A call to action made of the same material as the panel behind it
  // stops being a call to action. The mockup keeps `.btn-primary` opaque
  // for the same reason.
  const rules = primaryRules();
  assert.ok(rules.length > 0, '.primary rule is missing');
  for (const rule of rules) {
    assert.doesNotMatch(rule, /backdrop-filter|--glass-surface/);
  }
});

test('the rule that actually wins paints the gold gradient', () => {
  // Checked on the last declaration, because that is the one the browser
  // uses. The mockup's `.btn-primary` gradient with a light edge.
  const rules = primaryRules();
  const effective = rules[rules.length - 1];
  assert.match(effective, /linear-gradient\(135deg, var\(--gold\)/);
  assert.match(effective, /border: 1px solid rgba\(255, 255, 255/);
});
