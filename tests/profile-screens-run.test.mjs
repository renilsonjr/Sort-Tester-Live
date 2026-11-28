// The player's own screens, actually run.
//
// Most tests of these screens read the source as text, which says the words
// are there and nothing about whether a screen can be drawn. When the
// screens moved out of app.js into src/profileScreens.js, every name they
// used had to arrive through `deps` or an import; a name left behind would
// be a ReferenceError on Settings, or on the screen that deletes an account.
//
// So this builds the screens with stand-ins for everything app.js hands
// over, presses every button each screen wires up, and checks that all ten
// screens were drawn without anything throwing -- once with the server
// answering, once with it refusing.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';
import { standInPage } from './helpers/stand-in-page.mjs';

const { modules: [profileScreens], cleanup } = await loadAppModules(['src/profileScreens.js']);
test.after(cleanup);

const ATTEMPT = {
  id: 'a1', attempt_id: 'a1', mode: 'ranked', correct: 12, total: 15, points_delta: 30,
  started_at: '2026-11-01T10:00:00Z', finished_at: '2026-11-01T10:03:00Z', final_outcome: 'completed',
};
const TICKET = { id: 't1', attempt_id: 'a1', opened_at: '2026-11-02T10:00:00Z', closed_at: null, outcome: null };
const ANSWERS = {
  '/auth/me': { username: 'Ana', tag: 'K7Q2MX', avatar: 'fox', is_owner: true },
  '/ranked/entry': { points: 1200, badge: 'Bronze', eligible: true },
  '/ranked/profile/stats': { best_ranked: { correct: 14, total: 15 }, place: 3, attempts: 9 },
  '/ranked/history': [ATTEMPT],
  '/ranked/season': { phase: 'official', status: 'open', label: 'Season 1' },
};

async function walk(serverAnswers) {
  const page = standInPage();
  const titles = new Set();
  let account = { username: 'Ana', tag: 'K7Q2MX', avatar: 'fox' };
  const sent = async () => (serverAnswers ? { ok: true, status: 200, data: { login_id: 'river-42' } } : { ok: false, status: 0, reason: '' });
  // the three things these screens reach past app.js for
  const browser = {
    document: { createElement: () => page.element() },
    navigator: { clipboard: { writeText: async () => {} } },
    fetch: async (url) => {
      if (!serverAnswers) throw new Error('unreachable');
      const body = String(url).endsWith('/tickets') ? [TICKET] : { version: '0.1.0' };
      return { ok: true, status: String(url).includes('/delete') ? 202 : 200, headers: { get: () => 'application/json' }, json: async () => body };
    },
  };
  const before = Object.fromEntries(Object.keys(browser).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(browser)) Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  try {
    const screens = profileScreens.createProfileScreens({
      labPage: (html) => {
        titles.add(html.match(/class="lab-title"[^>]*>([^<$]*)/)?.[1].trim());
        return page.element();
      },
      t: (text) => text,
      esc: (text) => String(text ?? ''),
      ICONS: new Proxy({}, { get: () => '' }),
      language: { code: 'en', date: String, dateTime: String, number: String },
      backLink: (id) => `<button id="${id}"></button>`,
      log: { available: true, all: () => [] },
      api: async (path) => (serverAnswers ? ANSWERS[path] ?? null : null),
      apiSend: sent,
      apiSendOwner: sent,
      account: () => account,
      forgetAccount: () => { account = null; },
      stopQuizClock() {},
      logout: async () => {},
      signOut: async () => {},
      showOwnerTools() {},
      badgeArt: () => 'badge.png',
      badgeProgress: () => ({ percent: 20, next: 'Silver', left: 800 }),
      badgeTrail: () => '',
      balanceLine: () => 'Bronze',
      fillLaunchCallout() {},
    });
    for (const tab of [undefined, 'history', 'settings']) screens.showProfile(tab);
    await page.pressEverything();
    // the screens that wait a tick before going back to Settings
    await new Promise((resolve) => setTimeout(resolve, 5));
  } finally {
    for (const [key, descriptor] of Object.entries(before)) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
  return [...titles];
}

const EVERY_SCREEN = [
  'Ana', 'Ranked history', 'Settings', 'Tickets', 'Create ticket', 'Ticket sent',
  'Choose a profile icon', 'Sign out other devices', 'Change Quiz Code',
  'Are you sure you want to proceed with deleting this account?', 'Deletion accepted',
];

test('every profile screen can be drawn and every button pressed', async () => {
  const titles = await walk(true);
  for (const title of EVERY_SCREEN) assert.ok(titles.includes(title), `never drawn: ${title} (drew ${titles.join(' | ')})`);
});

test('a server that refuses everything breaks no screen', async () => {
  const titles = await walk(false);
  for (const title of ['Ana', 'Ranked history', 'Settings', 'Tickets', 'Choose a profile icon',
    'Sign out other devices', 'Change Quiz Code', 'Are you sure you want to proceed with deleting this account?']) {
    assert.ok(titles.includes(title), `never drawn: ${title} (drew ${titles.join(' | ')})`);
  }
});

test('app.js hands over every name the profile screens ask for', () => {
  // The walk above uses stand-ins, so it cannot see what app.js really
  // passes. This reads the two lists and compares them.
  const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
  const names = (text) => [...text.matchAll(/([A-Za-z]+)\s*(?=[,:}])/g)].map((m) => m[1]);
  const asked = names(read('../src/profileScreens.js').match(/const \{([^}]*)\} = deps;/)[1]);
  const handed = names(read('../src/app.js').match(/createProfileScreens\(\{([\s\S]*?)\n    \}\);/)[1]
    .replace(/(=>|\{).*$/gm, ''));
  assert.ok(asked.length >= 15, 'could not read the list the screens ask for');
  assert.deepEqual(asked.filter((name) => !handed.includes(name)), []);
});
