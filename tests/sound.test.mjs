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
  isBgmPlaying
} = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

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
