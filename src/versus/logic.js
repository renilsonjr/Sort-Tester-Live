// Versus -- the parts with no DOM and no network, so they can be tested
// with nothing but numbers.

// How often a waiting room and a live duel ask the server where things
// stand. The Ranked heartbeat already runs at this cadence on this
// hardware, which is what made a poll (not a socket) the honest choice.
export const POLL_MS = 1000;

// How long a duel's answer review stays up before the next question. The
// server budgets three seconds per question for this; the pause sits
// inside it so a full-length duel never outruns its own deadline.
export const REVIEW_MS = 1800;

// The handler duel's mode. Expert opens at Hard's pace and keeps
// climbing: "harder and faster", which is what Versus promises.
export const HANDLER_DUEL_MODE = 'expert';

// A room code as the server stores it: letters, a dash, two digits. A
// player types what they heard across the floor -- "hat 42", "hat42",
// "HAT-42" -- and all of them are the same room.
export function normalizeCode(raw) {
  const text = String(raw ?? '').toUpperCase().replace(/[^A-Z0-9]/g, '');
  const match = /^([A-Z]+)(\d{2})$/.exec(text);
  return match ? `${match[1]}-${match[2]}` : text;
}

// The share of the tug bar that is yours, as a percentage. Level scores
// (including 0-0) sit in the middle. The share is clamped so a runaway
// lead never empties the other side completely: the bar says who is
// ahead and roughly by how much, and the numbers above it say exactly.
export const TUG_MIN = 6;
export function tugShare(you, opponent) {
  const mine = Math.max(0, Number(you) || 0);
  const theirs = Math.max(0, Number(opponent) || 0);
  if (mine + theirs === 0) return 50;
  const share = (mine / (mine + theirs)) * 100;
  return Math.round(Math.min(100 - TUG_MIN, Math.max(TUG_MIN, share)));
}

// A random source both phones can share. The handler duel deals its belt
// order from the match's seed: same seed, same sequence, so both players
// sort the same packages. mulberry32 over a hash of the seed text -- small,
// fast, and identical in every browser, which Math.random is not.
export function seededRandom(seed) {
  let state = 0x811c9dc5;
  for (const char of String(seed ?? '')) {
    state ^= char.charCodeAt(0);
    state = Math.imul(state, 0x01000193);
  }
  state >>>= 0;
  return function next() {
    state = (state + 0x6d2b79f5) >>> 0;
    let mixed = state;
    mixed = Math.imul(mixed ^ (mixed >>> 15), mixed | 1);
    mixed ^= mixed + Math.imul(mixed ^ (mixed >>> 7), mixed | 61);
    return ((mixed ^ (mixed >>> 14)) >>> 0) / 4294967296;
  };
}

// Who is ahead, in the words the bar's caption uses. Returns the key and
// the margin; the screen translates.
export function standing(you, opponent) {
  const margin = (Number(you) || 0) - (Number(opponent) || 0);
  if (margin === 0) return { key: 'level', margin: 0 };
  return { key: margin > 0 ? 'ahead' : 'behind', margin: Math.abs(margin) };
}
