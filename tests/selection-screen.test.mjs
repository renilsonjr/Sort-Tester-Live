// The owner's prize-selection screen (#24, slice 6), built to the screen
// approved on 2026-11-15: the owner sees each player's tie-break history,
// and the choice is final.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

// The owner's screens are in src/ownerScreens.js, inside a factory, so
// each function ends two spaces in.
const app = readFileSync(new URL('../src/ownerScreens.js', import.meta.url), 'utf8');

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n  }\n'));
}

test('Owner tools reaches the selection, and says when a tie is waiting', () => {
  const tools = fn('function showOwnerTools');
  assert.match(tools, /id="owner-select"/);
  assert.match(tools, /1 tie waiting for you/);
});

test('each player shows their tie-break history, in words', () => {
  const fill = fn('async function fillSelection');
  assert.match(fill, /p\.history\.map/);
  const line = fn('function outcomeLine');
  assert.match(line, /h\.score\}\/5/);
  assert.match(line, /did not play/);
  assert.match(line, /did not finish/);
});

test('the screen never shows points it cannot change', () => {
  const fill = fn('async function fillSelection');
  assert.doesNotMatch(fill, /current_points|p\.points|p\.badge/);
});

test('the button waits for exactly the number of hats', () => {
  const fill = fn('async function fillSelection');
  assert.match(fill, /querySelectorAll\('input:checked'\)\.length !== hats/);
  assert.match(fill, /class="primary sel-go" type="button" disabled/);
});

test('the confirmation names who takes no hat, and going back is the easy answer', () => {
  const confirm = fn('function confirmSelection');
  assert.match(confirm, /does not take a hat this season/);
  assert.match(confirm, /cannot be undone from the app/);
  assert.match(confirm, /id="sel-back-to" class="primary"/);
  assert.match(confirm, /id="sel-record" class="ghost owner-danger"/);
});

test('recording asks for the Quiz Code when the server wants it', () => {
  assert.match(fn('function confirmSelection'), /apiSendOwner\('POST', `\/ranked\/owner\/selections\//);
});

test('an empty list explains how a tie arrives here', () => {
  assert.match(fn('async function fillSelection'), /A tie comes here only when the rules say so/);
});

test('names are escaped before they reach the page', () => {
  const fill = fn('async function fillSelection');
  assert.match(fill, /esc\(p\.username\)/);
  assert.match(fill, /esc\(p\.tag\)/);
});
