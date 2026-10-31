import { BELTS } from './belts.js';

export const CARD_SECONDS = 15;

export function shuffle(items, rand = Math.random) {
  const out = items.slice();
  for (let i = out.length - 1; i > 0; i--) {
    const j = Math.floor(rand() * (i + 1));
    [out[i], out[j]] = [out[j], out[i]];
  }
  return out;
}

export function buildOptions(card, rand = Math.random) {
  const pool = [...new Set(card.confusions)].filter((belt) => belt !== card.belt);
  const decoys = shuffle(pool, rand).slice(0, 3);

  if (decoys.length < 3) {
    const filler = shuffle(
      BELTS.filter((belt) => belt !== card.belt && !decoys.includes(belt)),
      rand,
    );
    decoys.push(...filler.slice(0, 3 - decoys.length));
  }

  return shuffle([card.belt, ...decoys], rand);
}

export function createRun({ name, cards, seconds = CARD_SECONDS, rand = Math.random }) {
  const prepared = shuffle(cards, rand).map((card) => ({
    card,
    options: buildOptions(card, rand),
  }));

  return {
    name,
    seconds,
    cards: prepared,
    index: 0,
    responses: [],
    finished: prepared.length === 0,
  };
}

export function currentCard(run) {
  return run.finished ? null : run.cards[run.index];
}

function record(run, outcome, answered, elapsedMs) {
  const { card } = run.cards[run.index];
  const response = {
    id: card.id,
    svc: card.svc,
    state: card.state,
    code: card.code,
    correctBelt: card.belt,
    why: card.why,
    answered,
    outcome,
    elapsedMs,
  };

  run.responses.push(response);
  run.index += 1;
  if (run.index >= run.cards.length) run.finished = true;
  return response;
}

export function answerCard(run, belt, elapsedMs) {
  if (run.finished) throw new Error('run is finished');
  const { card } = run.cards[run.index];
  return record(run, belt === card.belt ? 'correct' : 'wrong', belt, elapsedMs);
}

export function timeoutCard(run) {
  if (run.finished) throw new Error('run is finished');
  return record(run, 'timeout', null, run.seconds * 1000);
}

export function summarize(run, takenAt) {
  return {
    name: run.name,
    total: run.cards.length,
    correct: run.responses.filter((r) => r.outcome === 'correct').length,
    totalMs: run.responses.reduce((sum, r) => sum + r.elapsedMs, 0),
    missed: run.responses.filter((r) => r.outcome !== 'correct'),
    takenAt,
  };
}
