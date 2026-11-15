// Case review (#11, boxes 3 and 6), built to the screen approved on
// 2026-11-15. What these mostly defend is the absence of things: there is
// no sanction on this screen, because none was ever granted.
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

const screen = () => fn('function showCases') + fn('async function fillCases')
  + fn('function confirmCloseCase') + fn('function outcomeButtons');

test('the screen says closing changes nothing about the player', () => {
  const head = fn('function showCases');
  assert.match(head, /never changes anybody’s points, badge or access/);
  assert.match(head, /opens no ticket by itself/);
});

test('a flag is called a pattern, not proof', () => {
  // said twice on purpose: once at the top, once inside the flag itself,
  // because that is where the decision is taken
  assert.match(fn('function showCases'), /not evidence that somebody cheated/);
  assert.match(fn('async function fillCases'), /not proof that anybody cheated/);
});

test('only the two approved outcomes exist, and leaving it open is said', () => {
  const outcomes = app.slice(app.indexOf('const CASE_OUTCOMES'));
  const list = outcomes.slice(0, outcomes.indexOf('];'));
  assert.match(list, /network_instability/);
  assert.match(list, /insufficient_evidence/);
  assert.equal((list.match(/\n  \['/g) || []).length, 2, 'exactly two outcomes');
  assert.match(fn('function outcomeButtons'), /leave it open\. Nothing happens until you choose/);
});

test('there is no sanction anywhere on the screen', () => {
  // `\bblock\b` rather than /block/, so the <blockquote> holding what the
  // player wrote does not read as a sanction.
  for (const forbidden of [/\bban\b/i, /suspend/i, /penalt/i, /deduct/i, /remove points/i, /\bblock\b/i, /sanction/i]) {
    assert.doesNotMatch(screen(), forbidden);
  }
});

test('how long the evidence is kept is part of the case', () => {
  // #11 box 6: the reviewer sees the retention state where they decide
  const body = fn('async function fillCases');
  assert.match(body, /While this case is open, its description and connection details are kept/);
  assert.match(body, /Fifteen days after it closes/);
  assert.match(body, /unless a case still open shares the same log/);
});

test('closing asks first, and keeping it open is the easy answer', () => {
  const confirm = fn('function confirmCloseCase');
  assert.match(confirm, /id="case-keep" class="primary"/);
  assert.match(confirm, /id="case-go" class="ghost owner-danger"/);
  assert.match(confirm, /15 days after closure/);
});

test('the confirmation says which words the player will see', () => {
  const confirm = fn('function confirmCloseCase');
  assert.match(confirm, /The player sees this outcome in those words/);
  assert.match(confirm, /not an accusation/);
});

test('a ticket with no description says so rather than showing nothing', () => {
  assert.match(fn('async function fillCases'), /They wrote no description/);
});

test('an empty queue explains how cases arrive', () => {
  const body = fn('async function fillCases');
  assert.match(body, /Tickets only appear when a player opens one/);
  assert.match(body, /a connection problem does not open a ticket by itself/);
  assert.match(body, /A flag appears only when the server notices/);
});

test('the case carries nothing else about the player', () => {
  const body = fn('async function fillCases');
  for (const forbidden of [/row\.points/, /row\.badge/, /row\.balance/, /row\.history/, /other tickets/i]) {
    assert.doesNotMatch(body, forbidden);
  }
});

test('what the player wrote is escaped before it reaches the page', () => {
  const body = fn('async function fillCases');
  assert.match(body, /esc\(row\.description\)/);
  assert.match(body, /esc\(row\.username\)/);
  assert.match(fn('function caseEvents'), /esc\(event\.kind/);
});

test('a server that cannot be reached says nothing has been changed', () => {
  assert.match(fn('async function fillCases'), /Could not load the cases. Nothing has been changed/);
});

test('the case styles exist', () => {
  assert.match(page, /\.cases li \{ border: 1px solid var\(--line\)/);
  assert.match(page, /\.case-said \{/);
  assert.match(page, /\.case-keep \{/);
});
