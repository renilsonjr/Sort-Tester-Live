// The owner's launch screen (#258). The launch is the one irreversible
// action in the app, so what this file guards is: it cannot be reached by
// accident, it cannot be fired without the word typed, and the row stops
// existing once the season it starts is open.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The owner's screens are in src/ownerScreens.js, inside a factory, so
// each function starts two spaces in.
const app = readFileSync(new URL('../src/ownerScreens.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function body(name) {
  const start = app.indexOf(`function ${name}(`);
  assert.ok(start >= 0, `${name} not found`);
  const end = app.indexOf('\n  function ', start + 1);
  return app.slice(start, end === -1 ? undefined : end);
}

test('the row is hidden until the app says the Pre-Season is running', () => {
  const tools = body('showOwnerTools');
  assert.match(tools, /id="owner-launch"[^>]*hidden/);
  // shown only on the answer from the server, never assumed
  assert.match(tools, /api\('\/ranked\/season'\)/);
  assert.match(tools, /season\?\.phase === 'pre_season'/);
  assert.match(tools, /launch\.hidden = false/);
});

test('the screen states the four things the launch does', () => {
  const screen = body('showOwnerLaunch');
  for (const line of [
    'Every quiz being played right now ends with no score.',
    'Every balance goes to 0 and everybody is Iron again.',
    'Pre-Season history is kept: everybody can still read their own.',
    'The official season opens and runs to its closing date. It can only be started once.',
  ]) {
    assert.ok(screen.includes(`t('${line}')`), `the screen does not say: ${line}`);
  }
  assert.match(screen, /This cannot be undone/);
});

test('the button is dead until LAUNCH is typed and a name is there', () => {
  const screen = body('showOwnerLaunch');
  assert.match(screen, /id="launch-go"[^>]*disabled/);
  assert.match(screen, /word\.value\.trim\(\)\.toUpperCase\(\) === LAUNCH_WORD/);
  assert.match(screen, /label\.value\.trim\(\) !== ''/);
  // and it goes dead again when the server refuses, instead of staying live
  assert.match(screen, /refresh\(\);\n\s*error\.textContent/);
});

test('the launch goes through the owner path, which asks for the Quiz Code', () => {
  const screen = body('showOwnerLaunch');
  assert.match(screen, /apiSendOwner\('POST', '\/ranked\/season\/launch'/);
  assert.match(screen, /confirm: LAUNCH_WORD/);
});

test('a kept copy of the season or the balance is thrown away after a launch', () => {
  // both are cached reads; without this the screen that proves the
  // Pre-Season ended would be drawn from the Pre-Season's own answer
  assert.match(body('showOwnerLaunch'), /clearReadCache\(\);\n\s*showLaunchDone/);
});

test('the result screen reads the balance back instead of claiming it', () => {
  const done = body('showLaunchDone');
  assert.match(done, /api\('\/ranked\/entry'\)/);
  assert.ok(done.includes("t('Your points are now')"));
  assert.ok(done.includes("t('Your points could not be read just now.')"));
});

test('the launch screens use the app language for dates and numbers', () => {
  const screens = body('showOwnerLaunch') + body('showLaunchDone');
  assert.doesNotMatch(screens, /toLocale/);
  assert.match(screens, /language\.dateTime\(/);
  assert.match(screens, /language\.number\(/);
});

test('every word of the launch screens has Spanish', () => {
  const screens = body('showOwnerLaunch') + body('showLaunchDone') + body('showOwnerTools');
  for (const [, key] of screens.matchAll(/t\('((?:[^'\\]|\\.)*)'\)/g)) {
    const plain = key.replace(/\\'/g, "'").replace(/\\u2019/g, '’');
    assert.ok(
      i18n.includes(`'${key}': '`) || i18n.includes(`'${plain}': '`),
      `no Spanish for: ${plain}`,
    );
  }
});
