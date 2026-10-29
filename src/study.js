import { deckById } from './decks.js';

const preload = deckById('common-preload');
const twilight = deckById('common-twilight');

// These are selected routes from the existing quiz bank, not a complete chart.
// Reusing card objects keeps the study answer and quiz answer in sync.
export const STUDY_SECTIONS = [
  {
    id: 'new-jersey',
    title: 'New Jersey split',
    subtitle: 'Compare Preload and Twilight before choosing a belt.',
    sorts: ['Preload', 'Twilight'],
    cardsBySort: {
      Preload: preload.cards.filter((card) => card.state === 'NJ'),
      Twilight: twilight.cards.filter((card) => card.state === 'NJ'),
    },
  },
  {
    id: 'new-york',
    title: 'New York boundaries',
    subtitle: 'Watch the single codes and service exceptions.',
    sorts: ['Twilight'],
    cardsBySort: { Twilight: deckById('new-york').cards },
  },
  {
    id: 'common-missorts',
    title: 'Common missorts',
    subtitle: 'Routes shared by both sorts, including 1S and 2S.',
    sorts: ['Both'],
    cardsBySort: { Both: preload.cards.filter((card) => card.state !== 'NJ') },
  },
  ...[
    ['next-day-air', 'Next Day Air', 'Service exceptions that change the belt.'],
    ['two-day-air', '2 Day Air', 'Where 2 Day differs from Ground.'],
    ['three-day-select', '3 Day Select', 'Boundaries and service differences.'],
  ].map(([id, title, subtitle]) => ({
    id,
    title,
    subtitle,
    sorts: ['Twilight'],
    cardsBySort: { Twilight: deckById(id).cards },
  })),
];

export function cardsForStudy(section, sort = section.sorts[0]) {
  return section.cardsBySort[sort] ?? [];
}
