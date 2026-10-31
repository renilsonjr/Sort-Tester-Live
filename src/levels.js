import { BELTS } from './belts.js';
import { CHART } from './chart.js';

const SERVICE_CODES = {
  Ground: 'GND',
  'Next Day Air': 'NDA',
  '2 Day Air': '2DA',
  '3 Day Select': '3DS',
};

function cardsFromChart(service, includeExceptions = false, filter = () => true) {
  const section = CHART[service];
  const rows = includeExceptions
    ? [...section.main, ...section.exceptions]
    : section.main;
  return rows.filter((row) => !(row[0] === 'NJ' && row[1] === '070–089'))
    .filter(filter).map(([state, code, belt, detail], index) => ({
    id: `chart-${SERVICE_CODES[service]}-${index}-${state.replace(/[^A-Z]/g, '')}-${code.replace(/[^0-9A-Z]/g, '')}`,
    svc: SERVICE_CODES[service],
    state: state === '*' ? 'All states' : state,
    code,
    belt,
    confusions: BELTS.filter((other) => other !== belt && other !== 'CHECK'),
    why: detail
      ? `${detail}. On the Twilight ${service} chart, ${state} ${code} goes to ${belt}.`
      : `On the Twilight ${service} chart, ${state} ${code} goes to ${belt}. Check the service and the range before choosing a belt.`,
    tags: detail ? ['chart', 'exception'] : ['chart'],
  }));
}

const basicStates = new Set(['MA', 'NJ', 'NY', 'PA', 'GA', 'FL', 'AL', 'TN', 'OH', 'IN', 'MI', 'CA']);
const basicMain = cardsFromChart('Ground', false, ([state]) => state.split(', ').some((code) => basicStates.has(code)));
const basicNj = cardsFromChart('Ground', true, ([state, code]) => state === 'NJ' && code === '079 9');
const mediumServices = ['Ground', '2 Day Air', '3 Day Select', 'Next Day Air'];

export const LEVEL_DECKS = [
  {
    id: 'level-basic', name: 'Basic', sort: 'Twilight',
    blurb: 'Ground routes and the New Jersey exception',
    verified: true, questionCount: 15,
    cards: [...basicMain, ...basicNj],
  },
  {
    id: 'level-medium', name: 'Medium', sort: 'Twilight',
    blurb: 'Ground, 2 Day Air, 3 Day Select, and selected Next Day Air',
    verified: true, questionCount: 20,
    cards: mediumServices.flatMap((service) => cardsFromChart(service, false)),
  },
  {
    id: 'level-hard', name: 'Hard', sort: 'Twilight',
    blurb: 'The full chart, service splits, and single-code exceptions',
    verified: true, questionCount: 30,
    cards: mediumServices.flatMap((service) => cardsFromChart(service, true)),
  },
];

// Every run gets a new selection. Spread questions across services and cap how
// often one belt can be right, so a quiz cannot be passed by repeating a belt.
export function selectLevelCards(deck, rand = Math.random) {
  if (!deck.questionCount) return deck.cards;
  const shuffle = (items) => {
    const out = [...items];
    for (let i = out.length - 1; i > 0; i--) {
      const j = Math.floor(rand() * (i + 1));
      [out[i], out[j]] = [out[j], out[i]];
    }
    return out;
  };
  const groups = new Map();
  for (const card of deck.cards) {
    if (!groups.has(card.svc)) groups.set(card.svc, []);
    groups.get(card.svc).push(card);
  }
  for (const [service, cards] of groups) groups.set(service, shuffle(cards));
  const services = [...groups.keys()];
  const picked = [];
  const beltCounts = new Map();
  const beltCap = Math.ceil(deck.questionCount / 3);
  while (picked.length < deck.questionCount) {
    let added = false;
    for (const service of services) {
      if (picked.length >= deck.questionCount) break;
      const cards = groups.get(service);
      const index = cards.findIndex((card) => (beltCounts.get(card.belt) || 0) < beltCap);
      if (index < 0) continue;
      const [card] = cards.splice(index, 1);
      picked.push(card);
      beltCounts.set(card.belt, (beltCounts.get(card.belt) || 0) + 1);
      added = true;
    }
    if (!added) throw new Error(`Not enough varied cards for ${deck.id}`);
  }
  return picked;
}
