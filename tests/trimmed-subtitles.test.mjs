// The owner walked the live app on his phone and circled the sub-labels he
// wanted gone: seventeen of them, across Home, Profile, Practice, Ranked
// and Settings. They were the second line under a title -- "Support / Your
// tickets.", "Leaderboard / See the standings.", "Know the chart / Browse
// every service by state and ZIP range." -- saying in a sentence what the
// title above already said in two words.
//
// This file guards the removal, and, more usefully, guards the three places
// where the removed words carried something the title does not say and had
// to survive somewhere else.

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

function body(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.notEqual(start, -1, `${name} is gone`);
  const next = app.indexOf('\nfunction ', start + 1);
  return app.slice(start, next === -1 ? app.length : next);
}

test('the stylesheet has no unbalanced comment', () => {
  const style = html.slice(html.indexOf('<style>'), html.indexOf('</style>'));
  assert.equal((style.match(/\/\*/g) ?? []).length, (style.match(/\*\//g) ?? []).length);
  assert.doesNotMatch(style.replace(/\/\*[\s\S]*?\*\//g, ''), /\*\//);
});

test('every circled sub-label is gone from the app', () => {
  const circled = [
    'Browse every service by state and ZIP range.',
    'Start with Ground, then build up to the full chart.',
    'Prize eligibility, access recovery, case review.',
    'Your tickets.',
    'Ends this session on this device. Your points and history stay.',
    'Removes your profile, history and points.',
    'See the standings.',
    'Practice never changes Ranked points.',
    'Your practice results saved on this phone.',
    'Practices counts the sessions in the Shift log on this device.',
    '15 questions, ten seconds each.',
    'The top 3 win a UPS hat.',
    // Not in the screenshots -- it is below the fold on Profile -- but it
    // was the last one of this kind, and the owner asked for it once it
    // was pointed out.
    'Your Ranked quizzes, one by one.',
  ];
  for (const text of circled) {
    assert.ok(!app.includes(`t('${text}')`), `still shown: ${text}`);
  }
});

test('the sign-in screen lost its two lines too', () => {
  // Asked for after the first pass, from a screenshot of the live site.
  // These two are in auth.js, which the sign-in page loads on its own --
  // they were hardcoded English, with no Spanish to orphan.
  const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');
  assert.doesNotMatch(auth, /Learn the chart\. Play Ranked\. Climb the leaderboard\./);
  assert.doesNotMatch(auth, /Ranked needs a Quiz Code\. Guests get Practice only\./);
  // .auth-sub had nothing left to style; .auth-note still carries the
  // copy-status line and the two on the recovery form, so it stays.
  assert.doesNotMatch(css, /\.auth-sub/);
  assert.match(css, /\.auth-note \{/);
  assert.ok(auth.includes('class="auth-note"'), 'auth-note is still used');
});

test('the sign-in screen keeps the two links that are the way forward', () => {
  // "Continue as guest" no longer explains that a guest gets Practice
  // only. The two links under it are the only route for somebody without
  // a code, so they must not be swept next.
  const auth = readFileSync(join(root, 'src/auth.js'), 'utf8');
  assert.match(auth, /Need a Quiz Code\? Create an account/);
  assert.match(auth, /Forgot my Quiz Code\?/);
});

test('the sub-labels that are NOT repetition stayed', () => {
  // Worth pinning, because the sweep above invites someone to finish the
  // job. These are not second lines repeating a title:
  //
  //   the owner menu's rows explain administrative actions whose names
  //   give nothing away -- "Prize selection" does not tell you it is the
  //   ties the rules send you;
  //   Support's Create ticket says what a ticket may be about, and the
  //   locked state says why there is none;
  //   and the rest are captions for values -- a tag, a date, a balance.
  for (const kept of [
    'Who may win a hat this season.',
    'In person, for a sorter who lost their Quiz Code.',
    'Tickets players opened, and connection flags.',
    'Remove an account that should not exist.',
    'About one of your own Ranked attempts.',
  ]) {
    assert.ok(app.includes(`t('${kept}')`), `should have stayed: ${kept}`);
  }
});

test('their Spanish went with them', () => {
  // A translation with nothing to translate is what the coverage test
  // flags, and what quietly rots otherwise.
  for (const key of ['Your tickets.', 'See the standings.', '15 questions, ten seconds each.',
    'The top 3 win a UPS hat.', 'Practice never changes Ranked points.']) {
    assert.ok(!i18n.includes(`\n  '${key}':`), `orphan Spanish left for: ${key}`);
  }
});

test('the rules that styled them went too', () => {
  // Three classes had nothing left to style. `.tab-intro` is NOT one of
  // them: the Ranked tab still uses it for the season line.
  for (const dead of ['.home-spot-desc', '.pf-stats-note', '.rk-fine']) {
    assert.ok(!css.includes(dead), `dead rule left behind: ${dead}`);
    assert.ok(!app.includes(dead.slice(1)), `dead class still rendered: ${dead}`);
  }
  assert.match(css, /\.tab-intro \{/);
  assert.match(app, /class="lab-intro tab-intro"/);
});

// The three that carried more than repetition.

test('Delete account still states what it removes, on the screen that does it', () => {
  // The row's sub-label said "Removes your profile, history and points."
  // The screen behind it says more, before the tick-box, which is where
  // the person is when the decision is actually made.
  assert.match(app, /const DELETE_CONSEQUENCE = 'After deletion is completed, your profile, quiz history and points are removed\./);
  const screen = body('showDeleteAccount');
  assert.match(screen, /t\(DELETE_CONSEQUENCE\)/);
  assert.match(screen, /t\(DELETE_DISCLOSURE\)/);
});

test('Sign out my other devices still says what it does, before it does it', () => {
  const screen = body('showSignOutOthers');
  assert.match(screen, /t\('Ends every other phone or computer signed in to your account\. This one stays\.'\)/);
});

test('Profile icon still says where the icon shows, on its own screen', () => {
  const screen = body('showAvatarPicker');
  assert.match(screen, /t\('Shown on your profile and the leaderboard\.'\)/);
});

test('Log out is the one with nowhere else to say it', () => {
  // Flagged rather than fixed, because fixing it is a change the owner did
  // not ask for. Log out has no screen of its own -- the row signs the
  // player out on the tap -- so "your points and history stay" is not said
  // anywhere now. If this test starts failing because a confirm screen
  // appeared, that is the fix landing, not a regression.
  assert.match(app, /#profile-logout'\)\.addEventListener\('click', \(\) => signOut\(\)\)/);
  assert.ok(!app.includes("t('Ends this session on this device. Your points and history stay.')"));
});
