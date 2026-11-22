// Ranked background music (issue #264). The melody was written in sound.js
// but nothing ever started it, and the app had no sound switch on screen.
// Music now plays on the Ranked quiz screens only, and a button in the top
// bar turns all sound on or off.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const soundSource = readFileSync(new URL('../src/sound.js', import.meta.url), 'utf8');
const app = readFileSync(new URL('../src/app.js', import.meta.url), 'utf8');
const i18n = readFileSync(new URL('../src/i18n.js', import.meta.url), 'utf8');
const sound = await import(`data:text/javascript;base64,${Buffer.from(soundSource).toString('base64')}`);

function fn(name) {
  const start = app.indexOf(name);
  assert.notEqual(start, -1, `${name} is missing`);
  const body = app.slice(start);
  return body.slice(0, body.indexOf('\n}\n'));
}

function reset() {
  delete globalThis.document;
  sound.setSoundEnabled(true);
  sound.setMusicWanted(false);
}

test('asking for music starts it, and no longer asking stops it', () => {
  reset();
  sound.setMusicWanted(true);
  assert.equal(sound.isBgmPlaying(), true);
  sound.setMusicWanted(false);
  assert.equal(sound.isBgmPlaying(), false);
});

test('sound off silences the music; sound back on resumes it mid-quiz', () => {
  reset();
  sound.setMusicWanted(true);
  sound.setSoundEnabled(false);
  assert.equal(sound.isBgmPlaying(), false);
  sound.setSoundEnabled(true);
  assert.equal(sound.isBgmPlaying(), true);
  reset();
});

test('music asked for while sound is off stays silent', () => {
  reset();
  sound.setSoundEnabled(false);
  sound.setMusicWanted(true);
  assert.equal(sound.isBgmPlaying(), false);
  reset();
});

test('sound back on outside a quiz does not start music', () => {
  reset();
  sound.setSoundEnabled(false);
  sound.setSoundEnabled(true);
  assert.equal(sound.isBgmPlaying(), false);
});

test('a hidden tab pauses the music and coming back resumes it', () => {
  reset();
  sound.setMusicWanted(true);
  globalThis.document = { hidden: true };
  sound.syncMusic();
  assert.equal(sound.isBgmPlaying(), false);
  globalThis.document = { hidden: false };
  sound.syncMusic();
  assert.equal(sound.isBgmPlaying(), true);
  reset();
});

test('only the Ranked question and feedback screens ask for music', () => {
  const marked = [...app.matchAll(/<section class="lab-screen"[^>]*data-ranked-music[^>]*>/g)];
  assert.equal(marked.length, 2);
  assert.match(fn('async function playRankedAttempt'), /data-ranked-music/);
  assert.match(fn('function showRankedFeedback'), /data-ranked-music/);
  assert.doesNotMatch(fn('function showRankedResult'), /data-ranked-music/);
  assert.doesNotMatch(fn('function showCard'), /data-ranked-music/);
});

test('every screen change decides the music in one place', () => {
  const render = fn('function render(node)');
  assert.match(render, /setMusicWanted\(Boolean\(node\.querySelector\?\.\('\[data-ranked-music\]'\)\)\)/);
});

test('the top bar carries a sound switch that says its state', () => {
  assert.match(fn('function labPage'), /\$\{soundButton\(\)\}/);
  const button = fn('function soundButton');
  assert.match(button, /data-sound-toggle/);
  assert.match(button, /aria-pressed="\$\{on\}"/);
  assert.match(button, /t\('Sound on or off'\)/);
  const wire = fn('function wireSoundButton');
  assert.match(wire, /toggleSound\(\)/);
  assert.match(fn('function labPage'), /wireSoundButton\(view\)/);
});

test('the switch label has Spanish', () => {
  assert.match(i18n, /'Sound on or off': '[^']+'/);
});
