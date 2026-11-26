// Handler (internal name: conveyor) stage 1 -- routing data only.
//
// This module answers one question: what does a package on the belt say, and
// which two belts does the player choose between? No clock, no score, no
// canvas, no audio, no storage. Those are #394 and #395.
//
// The chart writes a main row as a range of three-digit prefixes, like
// MA|010-024|GOLD, because that is the shape of a chart row. A package in the
// hub carries one code, so Handler draws one prefix out of the range. Two
// rules keep that draw honest:
//
//   1. A prefix that any exception row of the same service touches is removed
//      from the draw. TN|370-385 is BROWN, but TN|376-378 is BLUE, so 376, 377
//      and 378 never come out of the BROWN row. Likewise NE|575 3-6 is ORANGE
//      inside a BROWN range: a bare "575" has no single right answer, because
//      the answer turns on a fourth digit the label would not show, so 575 is
//      removed too. Those prefixes are not lost -- the exception rows carry
//      them, with the fourth digit visible and the right belt.
//   2. The excluded set is computed from the chart, never typed by hand, so
//      correcting the chart recomputes it. tests/conveyor-routes.test.mjs
//      asserts the computed set equals the exclusion_refs the owner reviewed
//      in backend/data/ranked/routes-v1.json.
//
// Rows whose code is not a range (109, 034 0, 575 3-6, MEXICO, WORLD) are
// shown exactly as the chart writes them. Nothing here invents a five-digit
// ZIP: the repository has no ZIP list, and the chart routes by prefix.
import { CHART } from './../chart.js?v=chart-destination-20261108-r2';
import { LEVEL_DECKS } from './../levels.js?v=sort-change-20261116-r1';

export const SERVICE_NAMES = {
  GND: 'Ground',
  GRD: 'Ground',
  NDA: 'Next Day Air',
  '2DA': '2 Day Air',
  '3DS': '3 Day Select',
};

const RANGE = /^(\d{3})\s*[–-]\s*(\d{3})$/;
const PREFIX = /^(\d{3})\b/;

export function parseRange(code) {
  const match = RANGE.exec(String(code).trim());
  if (!match) return null;
  const from = Number(match[1]);
  const to = Number(match[2]);
  return to >= from ? { from, to } : null;
}

function leadingPrefix(code) {
  const match = PREFIX.exec(String(code).trim());
  return match ? Number(match[1]) : null;
}

// Every prefix any exception row of this service speaks about, whether it
// names a range (376-378), a prefix with a fourth digit (148 1, 575 3-6) or a
// bare prefix. Rows that are not about a ZIP at all -- "ends 2S", "WORLD" --
// touch no prefix and are skipped: a termination overrides the range wherever
// it appears, so it cannot be pinned to one row.
export function shadowedPrefixes(service) {
  const section = CHART[service];
  const shadowed = new Set();
  if (!section) return shadowed;
  for (const row of section.exceptions) {
    const range = parseRange(row[1]);
    if (range) {
      for (let prefix = range.from; prefix <= range.to; prefix += 1) shadowed.add(prefix);
      continue;
    }
    const prefix = leadingPrefix(row[1]);
    if (prefix !== null) shadowed.add(prefix);
  }
  return shadowed;
}

// One drawable route per deck card. A range card carries the prefixes that
// survive rule 1; every other card carries its code verbatim.
export function routePool(deckId) {
  const deck = LEVEL_DECKS.find(entry => entry.id === deckId);
  if (!deck) throw new Error(`Unknown deck: ${deckId}`);
  const shadowedByService = new Map();
  const pool = [];
  for (const card of deck.cards) {
    const service = SERVICE_NAMES[card.svc];
    if (!shadowedByService.has(service)) shadowedByService.set(service, shadowedPrefixes(service));
    const range = parseRange(card.code);
    if (!range) {
      pool.push({ card, service, labels: [String(card.code).trim()] });
      continue;
    }
    const shadowed = shadowedByService.get(service);
    const labels = [];
    for (let prefix = range.from; prefix <= range.to; prefix += 1) {
      if (!shadowed.has(prefix)) labels.push(String(prefix).padStart(3, '0'));
    }
    // A range entirely covered by exceptions has nothing honest to show.
    if (labels.length) pool.push({ card, service, labels });
  }
  return pool;
}

// Draw one package: a card, a concrete label, and the two belts offered. The
// correct belt comes from the chart and is never randomized; only which side
// it lands on is. The wrong belt is a real belt from the card's own confusion
// list, so it is never CHECK and never equal to the answer.
export function drawRoute(pool, rand = Math.random) {
  if (!pool.length) throw new Error('Empty route pool');
  const entry = pool[Math.floor(rand() * pool.length)];
  const label = entry.labels[Math.floor(rand() * entry.labels.length)];
  const wrong = entry.card.confusions[Math.floor(rand() * entry.card.confusions.length)];
  const correctOnLeft = rand() < 0.5;
  return {
    id: entry.card.id,
    service: entry.service,
    svc: entry.card.svc,
    state: entry.card.state,
    code: label,
    chartCode: entry.card.code,
    belt: entry.card.belt,
    why: entry.card.why,
    options: correctOnLeft
      ? [{ belt: entry.card.belt, correct: true }, { belt: wrong, correct: false }]
      : [{ belt: wrong, correct: false }, { belt: entry.card.belt, correct: true }],
  };
}

// The four modes the owner settled on 2026-11-24. Speed is pixels per second
// at the belt; progress is 0 at the start of the round and 1 at the end.
// Easy, Medium and Hard reuse the existing level decks rather than classifying
// routing content again. Expert opens at Hard's pace and keeps climbing, and
// its routing content hardens a third of the way in.
//
// Every number here is an assistant proposal, never measured. #397 tunes them
// after the owner plays, which is why they live in one place.
export const EXPERT_DECK_SWITCH = 1 / 3;
// Raised by about a fifth on 2026-11-26, when the round became one minute and
// the owner asked for every mode to run a little faster (was 42, 60, 84 and
// 84 + 48p). Expert still opens at Hard's speed and climbs by a little over
// half again.
export const MODES = {
  easy: { deck: () => 'level-basic', speed: () => 50 },
  medium: { deck: () => 'level-medium', speed: () => 72 },
  hard: { deck: () => 'level-hard', speed: () => 100 },
  expert: {
    deck: progress => (progress < EXPERT_DECK_SWITCH ? 'level-medium' : 'level-hard'),
    speed: progress => 100 + 58 * Math.min(1, Math.max(0, progress)),
  },
};

export const MODE_ORDER = ['easy', 'medium', 'hard', 'expert'];

export function modeDecks(mode) {
  const definition = MODES[mode];
  if (!definition) throw new Error(`Unknown mode: ${mode}`);
  return [...new Set([definition.deck(0), definition.deck(1)])];
}
