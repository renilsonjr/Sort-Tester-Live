// Practice answer feedback (issue #263). The button turned red and played the
// wrong-answer sound on every tap, right or not: the screen read `.belt` off
// what currentCard() returns, which is { card, options }, so the comparison
// was always against undefined. The engine's own verdict was never wrong.
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { loadAppModules } from './helpers/load-app-modules.mjs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const { modules: [quiz], cleanup } = await loadAppModules(['src/quiz.js']);
after(cleanup);

function practiceHandler() {
  const start = app.indexOf('function showCard');
  assert.notEqual(start, -1, 'showCard is missing');
  const body = app.slice(start);
  const handler = body.slice(body.indexOf("view.querySelectorAll('.belt')"));
  return handler.slice(0, handler.indexOf('function tick'));
}

// The expression the screen uses to decide the colour and the sound, lifted
// from the source so the test runs the real rule and not a copy of it.
function screenRule() {
  const match = practiceHandler().match(/const isRight = ([^;]+);/);
  assert.ok(match, 'the Practice handler no longer computes isRight');
  // eslint-disable-next-line no-new-func
  return new Function('current', 'button', `return ${match[1]};`);
}

const CARDS = [
  { id: 'a', svc: 'Ground', state: 'NJ', code: '070', belt: 'GOLD', why: '' },
  { id: 'b', svc: 'Ground', state: 'NY', code: '100', belt: 'PINK', why: '' },
];

test('currentCard hands back the card wrapped with its options', () => {
  const run = quiz.createRun({ name: 'x', cards: CARDS });
  const current = quiz.currentCard(run);
  assert.equal(current.belt, undefined);
  assert.ok(current.card.belt);
  assert.ok(Array.isArray(current.options));
});

test('the screen and the engine agree on every option of every card', () => {
  const isRight = screenRule();
  const run = quiz.createRun({ name: 'x', cards: CARDS });
  while (!run.finished) {
    const current = quiz.currentCard(run);
    const verdicts = current.options.map((belt) => Boolean(isRight(current, { dataset: { belt } })));
    assert.equal(verdicts.filter(Boolean).length, 1, 'exactly one option is shown as right');
    const right = current.options[verdicts.indexOf(true)];
    assert.equal(quiz.answerCard(run, right, 100).outcome, 'correct');
  }
});

test('right gets the green class and the correct sound, wrong the red and the other', () => {
  const handler = practiceHandler();
  assert.match(handler, /if \(isRight\) \{\s*button\.classList\.add\('belt-correct'\);\s*playCorrectSfx\(\);/);
  assert.match(handler, /else \{\s*button\.classList\.add\('belt-incorrect'\);\s*playIncorrectSfx\(\);/);
});
