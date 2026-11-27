// The promotion celebration (issue #95). It shows a promotion the server
// has already settled; it never decides one, and it never stands between
// the player and the result screen #17 settled.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');
const es = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('it plays only for a promotion the server settled as a promotion', () => {
  const result = fn('function showPromotionResult');
  // the same test the result screen itself uses: the server's own
  // badge_before/badge_after, never anything the page worked out
  assert.match(result, /const passed = !quit && result\.badge_after !== result\.badge_before/);
  assert.match(result, /if \(passed && !celebrationSeen\(attemptId\)\) \{/);
  assert.match(result, /showPromotionCelebration\(result, tally, attemptId\)/);
});

test('it shows the badge and rank name the result carries', () => {
  const cheer = fn('function showPromotionCelebration');
  assert.match(cheer, /const badge = result\.badge_after/);
  assert.match(cheer, /badgeArt\(badge\)/);
  assert.match(cheer, /t\('You are'\)\)\} \$\{esc\(badge\)/);
});

test('the rank is announced, not only drawn', () => {
  const cheer = fn('function showPromotionCelebration');
  assert.match(cheer, /role="status"/);
  assert.match(cheer, /t\('Promoted to'\)/);
  // the badge image is decorative: the name beside it is the information
  assert.match(cheer, /class="cheer-badge" src="\$\{badgeArt\(badge\)\}" alt=""/);
});

test('nothing loops, and the glow and sparks are one burst', () => {
  assert.doesNotMatch(page, /animation:[^;]*infinite/);
  assert.match(page, /@keyframes cheer-badge-in/);
  assert.match(page, /@keyframes cheer-glow/);
  assert.match(page, /@keyframes cheer-spark/);
});

test('with the motion switched off what is left is the finished state', () => {
  // the badge rests visible and the decoration rests invisible, so
  // "animation: none" -- reduced motion, or Skip -- lands on the end state
  assert.match(page, /\.cheer-glow \{[^}]*opacity: 0;/);
  assert.match(page, /\.cheer-spark \{[^}]*opacity: 0;/);
  assert.match(page, /@keyframes cheer-badge-in \{ from \{ opacity: 0;[^}]*\} to \{ opacity: 1;/);
  // This used to assert the blanket `* { animation: none !important }`, which
  // also switched off every transition in the app -- colour included. The
  // block now names the celebration specifically, which is what stills it.
  assert.match(page, /@media \(prefers-reduced-motion: reduce\) \{[\s\S]*?\.promo-cheer \.cheer-badge,\s*\n\s*\.promo-cheer \.cheer-glow,\s*\n\s*\.promo-cheer \.cheer-spark \{ animation: none; \}/);
  assert.match(page, /\.promo-cheer\.skipped \.cheer-badge,[\s\S]*?animation: none;/);
});

test('Skip ends the motion at once and leaves the keyboard somewhere useful', () => {
  const cheer = fn('function showPromotionCelebration');
  assert.match(cheer, /classList\.add\('skipped'\)/);
  assert.match(cheer, /skip\.hidden = true/);
  assert.match(cheer, /#cheer-continue'\)\.focus\(\)/);
});

test('Continue goes to the result screen #17 settled, with its numbers', () => {
  const cheer = fn('function showPromotionCelebration');
  assert.match(cheer, /showPromotionResult\(result, tally, \{ attemptId \}\)/);
  // and that screen still carries the balance and the cap line
  const result = fn('function showPromotionResult');
  // Grouped through language.number since #442, so the separator follows
  // the app's language rather than the phone's. Same number, same place.
  assert.match(result, /language\.number\(result\.points_after\)/);
  assert.match(result, /balanceLine\(\{ badge: result\.badge_after/);
});

test('it plays once per attempt, and a phone that saves nothing still gets it', () => {
  const seen = fn('function celebrationSeen');
  const mark = fn('function markCelebrated');
  assert.match(seen, /celebrated\.has\(attemptId\)/);
  assert.match(seen, /localStorage\.getItem\(CELEBRATED_KEY\)/);
  assert.match(seen, /catch \{\s*return false;/);
  assert.match(mark, /celebrated\.add\(attemptId\)/);
  assert.match(mark, /localStorage\.setItem\(CELEBRATED_KEY, attemptId\)/);
  // marked as it opens, so a re-render -- a language switch -- is not a replay
  const cheer = fn('function showPromotionCelebration');
  assert.match(cheer, /^\s*markCelebrated\(attemptId\);/m);
});

test('the attempt it belongs to is carried from the attempt itself', () => {
  assert.match(app, /showRankedResult\(mode, response\.result, tally, \{ attemptId: attempt\.attemptId \}\)/);
  assert.match(app, /function showRankedResult\(mode, result, tally, \{ quit = false, attemptId = null \} = \{\}\)/);
});

test('a quit or a failed promotion never celebrates', () => {
  const result = fn('function showPromotionResult');
  assert.match(result, /const passed = !quit/);
});

test('its copy exists in Spanish', () => {
  for (const key of ['Skip animation', 'Promoted to', 'Fifteen out of fifteen. The new badge is yours.']) {
    assert.ok(es.includes(`'${key}'`), `${key} is missing from the Spanish copy`);
  }
});
