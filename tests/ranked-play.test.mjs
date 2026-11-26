// Playing Ranked and promotion (built to the screens approved in #17).
// This is what #95's promotion celebration was waiting on: it triggers
// only after the server confirms a promotion, which needs a promotion
// attempt to be playable at all.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const page = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

test('the Ranked screen starts a real attempt, not a placeholder', () => {
  const filled = fn('async function fillRanked');
  assert.match(filled, /startRankedAttempt\('normal'\)/);
  assert.match(filled, /showPromotionOffer\(entry\)/);
  // the "being built" placeholder is gone
  assert.doesNotMatch(app, /Playing a Ranked quiz is being built/);
});

test('at a cap the only way in is the promotion offer, which starts nothing', () => {
  const offer = fn('function showPromotionOffer');
  assert.match(offer, /Opening this screen has not started anything/);
  assert.match(offer, /id="pr-start"/);
  assert.match(offer, /id="pr-not-now"/);
  // the offer itself never calls start; only its button does
  const beforeHandlers = offer.slice(0, offer.indexOf("addEventListener"));
  assert.doesNotMatch(beforeHandlers, /startRankedAttempt/);
});

test('the promotion offer names the next badge and what passing sets', () => {
  const offer = fn('function showPromotionOffer');
  assert.match(offer, /nextBadgeName\(entry\.badge\)/);
  assert.match(offer, /BADGE_CAP\[entry\.badge\][^)]*\) \+ 1/);
  assert.match(offer, /You need every one of them right/);
});

test('a question is served by the server, with its belts and its deadline', () => {
  const play = fn('async function playRankedAttempt');
  assert.match(play, /attempt\.current\(\)/);
  assert.match(play, /q\.options \|\| \[\]/);
  assert.match(play, /new Date\(q\.deadline_at\)\.getTime\(\)/);
  // ten seconds is the server's, shown as a countdown; the page never
  // decides when a question is over
  assert.match(play, /startCountdown\(new Date\(q\.deadline_at\)\.getTime\(\), 10000\)/);
});

test('an answer locks every belt and marks the one that was picked', () => {
  const play = fn('async function playRankedAttempt');
  assert.match(play, /b\.disabled = true/);
  assert.match(play, /classList\.toggle\('picked'/);
  assert.match(page, /\.belts \.belt\.picked \{/);
});

test('feedback waits for Next, and Next is what sends the following question', () => {
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /id="rq-next"/);
  assert.match(feedback, /await attempt\.advance\(\)/);
  assert.match(feedback, /playRankedAttempt\(attempt, mode, tally\)/);
});

test('ordinary feedback shows the worth and the right belt; promotion does not promise points', () => {
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /response\.worth/);
  assert.match(feedback, /response\.correct_belt/);
  assert.match(feedback, /A right answer in promotion adds no points/);
});

test('a wrong promotion answer ends the promotion there and then', () => {
  // owner decision (#268): the engine completes a promotion at its first
  // miss, so the page says it is over, promises nothing more will be asked,
  // and leads to the result instead of a next question
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /This promotion ends here/);
  assert.match(feedback, /it stops at the first miss/);
  assert.match(feedback, /Reach the cap again to try next time/);
  // the label is now three ways: a lost promotion, the last answer of an
  // ordinary quiz ('Finish quiz', owner report 2026-11-26), and the rest
  assert.match(feedback, /promoLost \? 'See the result' :/);
  // the page never decides the ending by itself: it follows the server
  assert.match(feedback, /if \(response\.finished\) \{\s*attempt\.stop\(\);\s*showRankedResult/);
  assert.doesNotMatch(app, /plays out|still takes points off your balance/);
});

test('the promotion rules shown before starting say it ends at the first miss', () => {
  assert.match(app, /One wrong answer or timeout ends the promotion right there, and that mistake deducts its points\./);
});

test('a timeout says no choice was sent, instead of inventing one', () => {
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /none sent in time/);
});

test('the final answer goes to the result the server settled, never a guess', () => {
  const feedback = fn('function showRankedFeedback');
  assert.match(feedback, /response\.finished/);
  // the attempt id rides along so the #95 celebration plays once per
  // attempt; the result itself is still the server's, never a guess
  assert.match(feedback, /showRankedResult\(mode, response\.result, tally, \{ attemptId: attempt\.attemptId \}\)/);
});

test('the result keeps the raw and applied numbers from #17', () => {
  const sum = fn('function rankedSum');
  assert.match(sum, /result\.points_before/);
  assert.match(sum, /result\.raw_score/);
  assert.match(sum, /result\.points_after/);
});

test('the breakdown separates the answers, the quit penalty and the cap', () => {
  // the mock shows these as their own lines; lumping them into one net
  // number would hide where the points went
  const sum = fn('function rankedSum');
  assert.match(sum, /Right before you quit/);
  assert.match(sum, /Quitting costs/);
  assert.match(sum, /Did not fit in/);
  assert.match(sum, /overflow < 0/);
});

test('a badge that dropped is named, and only when points actually fell', () => {
  const result = fn('function showRankedResult');
  assert.match(result, /badge_after !== result\.badge_before/);
  assert.match(result, /points_after < result\.points_before/);
});

test('a passed promotion shows the new badge the server confirmed', () => {
  const promo = fn('function showPromotionResult');
  assert.match(promo, /result\.badge_after !== result\.badge_before/);
  assert.match(promo, /badgeArt\(result\.badge_after\)/);
  assert.match(promo, /15 \$\{esc\(t\('of'\)\)\} 15/);
});

test('a failed promotion says all fifteen were needed, and what it cost', () => {
  const promo = fn('function showPromotionResult');
  assert.match(promo, /promotion needs all 15/);
  assert.match(promo, /points to the cap again/);
  // the quit penalty is its own line, never folded into what the wrong
  // answers cost
  assert.match(promo, /Wrong answers and timeouts/);
  assert.match(promo, /Quitting costs/);
});

test('quitting asks first, and continuing is the primary answer', () => {
  const quit = fn('function showQuitConfirm');
  assert.match(quit, /id="qc-stay" class="primary"/);
  assert.match(quit, /id="qc-quit" class="ghost owner-danger"/);
  assert.match(quit, /10 points are taken off it/);
  assert.match(quit, /cannot resume this attempt/);
});

test('the play screens are styled', () => {
  assert.match(page, /\.rq-verdict\.good \{/);
  assert.match(page, /\.rq-cmp > div \{/);
  assert.match(page, /\.sum \.total \{/);
});
