// The fifteen profile icons (issue #272).
//
// The account stores the key; this is the only place that turns a key into
// something to draw. A key the server does not know never gets here, and a
// key this file does not know draws nothing rather than a broken glyph.
//
// The owner approved an all-animal set on 2026-11-22: full-colour glyphs of
// similar weight on every phone, where a star or a bolt would render flat
// and smaller beside them. The keys and their order match
// backend/auth/avatars.py, and tests/avatar-list.test.mjs holds them to it.
export const AVATARS = [
  ['fox', '🦊'],
  ['panda', '🐼'],
  ['lion', '🦁'],
  ['frog', '🐸'],
  ['owl', '🦉'],
  ['octopus', '🐙'],
  ['bee', '🐝'],
  ['dinosaur', '🦖'],
  ['turtle', '🐢'],
  ['butterfly', '🦋'],
  ['penguin', '🐧'],
  ['deer', '🦌'],
  ['fish', '🐟'],
  ['raccoon', '🦝'],
  ['caterpillar', '🐛'],
];

const BY_KEY = new Map(AVATARS);

// What to draw for a key, or '' when the player has never chosen. Callers
// fall back to the initial letter they already show, so nobody is given an
// icon they did not pick.
export function avatarEmoji(key) {
  return BY_KEY.get(key) ?? '';
}
