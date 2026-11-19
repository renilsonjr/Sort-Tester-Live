import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const source = readFileSync(new URL('../src/sound.js', import.meta.url), 'utf8');
const {
  isSoundEnabled,
  toggleSound,
  setSoundEnabled,
  playCorrectSfx,
  playIncorrectSfx,
  startBgm,
  stopBgm,
  isBgmPlaying,
  installAudioUnlock,
} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

// A stand-in for the browser's AudioContext that starts the way iOS Safari
// leaves it: not running until resume() is called inside a user gesture.
function fakeAudio(initialState = 'suspended') {
  const log = { created: 0, resumed: 0, buffersStarted: 0, tones: 0 };
  class FakeContext {
    constructor() { log.created += 1; log.instance = this; this.state = initialState; this.currentTime = 0; this.destination = {}; }
    resume() { log.resumed += 1; this.state = 'running'; return Promise.resolve(); }
    createBuffer() { return {}; }
    createBufferSource() { return { connect() {}, start() { log.buffersStarted += 1; } }; }
    createOscillator() {
      return { frequency: { setValueAtTime() {} }, connect() {}, start() { log.tones += 1; }, stop() {} };
    }
    createGain() { return { gain: { setValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {} }; }
  }
  return { FakeContext, log };
}

function fakeTarget() {
  const listeners = new Map();
  return {
    addEventListener: (type, handler) => listeners.set(type, handler),
    fire: (type) => listeners.get(type)?.(),
    types: () => [...listeners.keys()],
  };
}

test('sound module initializes with sound enabled by default', () => {
  setSoundEnabled(true);
  assert.equal(isSoundEnabled(), true);
  assert.equal(isBgmPlaying(), false);
});

test('toggleSound toggles sound state and returns new value', () => {
  setSoundEnabled(true);
  const newState = toggleSound();
  assert.equal(newState, false);
  assert.equal(isSoundEnabled(), false);

  const backState = toggleSound();
  assert.equal(backState, true);
  assert.equal(isSoundEnabled(), true);
});

test('startBgm and stopBgm control BGM playback state', () => {
  setSoundEnabled(true);
  startBgm();
  assert.equal(isBgmPlaying(), true);

  stopBgm();
  assert.equal(isBgmPlaying(), false);
});

test('playCorrectSfx and playIncorrectSfx execute without error when audio context is simulated', () => {
  setSoundEnabled(true);
  assert.doesNotThrow(() => {
    playCorrectSfx();
    playIncorrectSfx();
  });
});

// iOS Safari starts audio only inside a tap. Ranked plays its sound after the
// server answers, by which time the tap is over — so the tap itself has to
// open the audio, before anything is awaited.
// The module keeps one context for the page, so these tests share one fake.
const audio = fakeAudio('suspended');
const page = fakeTarget();

test('a tap opens the audio before any sound is asked for', () => {
  setSoundEnabled(true);
  globalThis.window = { AudioContext: audio.FakeContext };
  installAudioUnlock(page);
  assert.ok(page.types().includes('pointerdown'), 'listens for the tap');

  page.fire('pointerdown');
  assert.equal(audio.log.created, 1, 'the context is created inside the tap');
  assert.equal(audio.log.resumed, 1, 'and resumed inside the tap');
  assert.equal(audio.log.buffersStarted, 1, 'with the silent buffer iOS needs to open audio');

  // Later, outside any gesture (after the network round trip): it just plays.
  playCorrectSfx();
  assert.equal(audio.log.tones, 4);
  assert.equal(audio.log.created, 1, 'the same context is reused');
});

test('audio that iOS interrupted (a call, switching apps) comes back on the next tap', () => {
  setSoundEnabled(true);
  audio.log.instance.state = 'interrupted';
  const before = audio.log.resumed;
  page.fire('pointerdown');
  assert.equal(audio.log.resumed, before + 1);
  assert.equal(audio.log.instance.state, 'running');
});

test('a tap on running audio does nothing more', () => {
  setSoundEnabled(true);
  const { resumed, buffersStarted } = audio.log;
  page.fire('pointerdown');
  assert.equal(audio.log.resumed, resumed);
  assert.equal(audio.log.buffersStarted, buffersStarted);
});

test('a muted app does not touch audio on tap', () => {
  setSoundEnabled(false);
  audio.log.instance.state = 'suspended';
  const before = audio.log.resumed;
  page.fire('pointerdown');
  assert.equal(audio.log.resumed, before);
  setSoundEnabled(true);
});
