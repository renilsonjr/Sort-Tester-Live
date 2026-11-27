// The end of a Ranked quiz (owner report, 2026-11-26).
//
// Three things about the fifteenth question: its feedback is shown like any
// other and is not overtaken by the attempt ending, the button there says
// the quiz is over rather than "Next", and a request that is not a question
// is never drawn as one.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.ok(start >= 0, `${name} not found`);
  return app.slice(start, app.indexOf('\nfunction ', start + 1));
}

test('the last answer says so on the button', () => {
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /response\.finished \? 'Finish' : 'Next'/);
  assert.ok(i18n.includes("'Finish': '"), 'no Spanish for Finish');
});

test('the feedback still carries the route, the verdict, the points and the right belt', () => {
  const feedback = fn('function showRankedFeedback');
  // the same screen the other fourteen questions get, on the last one too
  assert.match(feedback, /rq-route/);
  assert.match(feedback, /rq-verdict/);
  assert.match(feedback, /rq-worth/);
  assert.ok(feedback.includes("t('Correct belt')"));
  assert.match(feedback, /response\.correct_belt/);
});

test('the attempt ending cannot overtake the last feedback', () => {
  // Sending an answer disarms the handler the heartbeat uses, BEFORE the
  // request goes. The attempt can only be reported gone once that answer
  // has completed it, so after this line the two paths cannot race.
  const play = fn('async function playRankedAttempt');
  const submit = play.slice(play.indexOf('async function submit(choice, button)'));
  const disarm = submit.indexOf('attempt.onGone(() => {})');
  const send = submit.indexOf('await attempt.answer(');
  assert.ok(disarm >= 0, 'the handler is never disarmed');
  assert.ok(disarm < send, 'disarming after the answer still leaves the race');
});

test('a read that was overtaken does not draw over the screen that replaced it', () => {
  // the feedback can draw while a read started by the heartbeat is still in
  // flight; that read must not then put the result on top of it
  const play = fn('async function playRankedAttempt');
  assert.match(play, /const mine = \+\+rankedScreen;\s*const current = await attempt\.current\(\);\s*if \(mine !== rankedScreen\) return;/);
  assert.match(fn('function showRankedFeedback'), /rankedScreen \+= 1;/);
});

test('a refusal is never drawn as a question', () => {
  const play = fn('async function playRankedAttempt');
  assert.match(play, /!current\.ok \|\| !current\.data \|\| current\.data\.seq === undefined/);
  // and the old shape, which let a 403 body through, is gone
  assert.doesNotMatch(play, /current\.status === 410 \|\| current\.status === 204 \|\| !current\.data/);
});

test('the result is read before the capability is put away', () => {
  const play = fn('async function playRankedAttempt');
  const read = play.indexOf('await attempt.result()');
  const stop = play.indexOf('attempt.stop()');
  assert.ok(read >= 0 && stop >= 0, 'both calls should be there');
  assert.ok(read < stop, 'stopping first makes the result request fail with 403');
});
