// The owner's screens, actually run.
//
// The other owner tests read the source as text, which says the words are
// there and says nothing about whether a screen can be drawn. These screens
// are behind the owner's own sign-in, so nobody but the owner walks them,
// and when they moved out of app.js into src/ownerScreens.js every name
// they used had to arrive through `deps`. A name left behind would be a
// ReferenceError on a screen only one person ever opens.
//
// So this builds the screens with stand-ins for everything app.js hands
// over, presses every button each screen wires up, and checks that all
// fifteen screens were drawn without anything throwing -- once with the
// server answering, once with it refusing.
import test from 'node:test';
import assert from 'node:assert/strict';
import { loadAppModules } from './helpers/load-app-modules.mjs';
import { standInPage } from './helpers/stand-in-page.mjs';

const { modules: [ownerScreens], cleanup } = await loadAppModules(['src/ownerScreens.js']);
test.after(cleanup);

const ROW = {
  id: 'a1', account_id: 'a1', attempt_id: 'a1', group_id: 'a1',
  username: 'Ana', tag: 'K7Q2MX', roster_reference: 'badge 1', body: 'locked out',
  created_at: '2026-11-01T10:00:00Z', opened_at: '2026-11-01T10:00:00Z',
  flagged_at: '2026-11-01T10:00:00Z', first_loss_at: '2026-11-01T10:00:00Z',
  last_loss_at: '2026-11-01T10:05:00Z', completed_at: null, resolved_at: null,
  description: 'it froze', events: [{ kind: 'connection_lost', occurred_at: '2026-11-01T10:00:00Z' }],
  approved: true, has_played: true, is_owner: false,
  login_id: 'river-42', label: 'Season 1', closes_at: '2026-12-31T00:00:00Z',
};
const ANSWERS = {
  '/ranked/season': { phase: 'pre_season' },
  '/ranked/entry': { points: 0, badge: 'Iron' },
  '/ranked/owner/approvals': { approvals_open: true, approvals: [ROW] },
  '/ranked/owner/accounts': { accounts: [ROW] },
  '/ranked/owner/recoveries': { recoveries: [ROW] },
  '/ranked/owner/recovery-messages': { open: 1, messages: [ROW] },
  '/ranked/owner/selections': {
    cases: [{ group_id: 'a1', hats: 1, tied_points: 900, players: [{ ...ROW, history: [{ outcome: 'completed', round: 1, score: 4 }] }] }],
  },
  '/ranked/flags': [ROW],
  '/ranked/support/review': [ROW],
};

async function walk(serverAnswers) {
  // every data-* attribute reads as the one row's id, except the label a
  // case button carries, which becomes that screen's title
  const { element, pressEverything } = standInPage({
    data: (key) => (key === 'label' ? 'Close · network instability' : 'a1'),
  });
  const titles = new Set();
  const send = async () => (serverAnswers ? { ok: true, data: ROW } : { ok: false, reason: '' });
  const screens = ownerScreens.createOwnerScreens({
    labPage: (html) => {
      titles.add(html.match(/class="lab-title">([^<$]*)/)?.[1].trim());
      return element();
    },
    t: (text) => text,
    esc: (text) => String(text ?? ''),
    ICONS: new Proxy({}, { get: () => '' }),
    language: { date: String, dateTime: String, number: String },
    backLink: (id) => `<button id="${id}"></button>`,
    api: async (path) => (serverAnswers ? ANSWERS[path] ?? null : null),
    apiSend: send,
    apiSendOwner: send,
    clearReadCache() {},
    stopQuizClock() {},
    showSettings() {},
  });
  screens.showOwnerTools();
  await pressEverything();
  return [...titles];
}

const EVERY_SCREEN = [
  'Owner tools', 'Prize eligibility', 'Withdraw', 'Accounts', 'Delete this account?',
  'Start the official season', 'The official season has started',
  'Prize selection', 'Give the hat to', 'Case review', 'Close · network instability?',
  'Access recovery', 'Recovery messages', 'Ana · #K7Q2MX', 'Hand this over now',
];

test('every owner screen can be drawn and every button pressed', async () => {
  const titles = await walk(true);
  for (const title of EVERY_SCREEN) assert.ok(titles.some((drawn) => drawn.startsWith(title)), `never drawn: ${title}`);
});

test('a server that refuses everything breaks no screen', async () => {
  const titles = await walk(false);
  // with nothing loaded there are no rows to press, so only the screens
  // reached from the menu itself are expected
  for (const title of ['Owner tools', 'Prize eligibility', 'Accounts', 'Start the official season',
    'Prize selection', 'Case review', 'Access recovery', 'Recovery messages']) {
    assert.ok(titles.includes(title), `never drawn: ${title}`);
  }
});

test('app.js hands over every name the owner screens ask for', async () => {
  // The walk above uses stand-ins, so it cannot see what app.js really
  // passes. This reads the two lists and compares them.
  const { readFileSync } = await import('node:fs');
  const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8');
  const names = (text) => [...text.matchAll(/([A-Za-z]+)\s*(?=[,:}])/g)].map((m) => m[1]);
  const asked = read('../src/ownerScreens.js').match(/const \{([^}]*)\} = deps;/)[1];
  const handed = read('../src/app.js').match(/createOwnerScreens\(\{([\s\S]*?)\n    \}\);/)[1]
    .replace(/=>.*$/gm, '');
  const missing = names(asked).filter((name) => !names(handed).includes(name));
  assert.ok(names(asked).length >= 10, 'could not read the list the screens ask for');
  assert.deepEqual(missing, []);
});
