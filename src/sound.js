/**
 * Zero-latency procedural audio synthesizer using Web Audio API.
 * Provides interactive feedback SFX and optional background music (BGM).
 */

const STORAGE_KEY = 'sort_sound_enabled';

let audioCtx = null;
let soundEnabled = true;
let bgmPlaying = false;
let bgmTimer = null;
let bgmIndex = 0;

// Read initial state from localStorage if available
try {
  if (typeof localStorage !== 'undefined') {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved !== null) {
      soundEnabled = (saved === 'true');
    }
  }
} catch {
  // Ignore storage access errors
}

export function isSoundEnabled() {
  return soundEnabled;
}

export function setSoundEnabled(enabled) {
  soundEnabled = Boolean(enabled);
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, String(soundEnabled));
    }
  } catch {
    // Ignore storage write errors
  }
  if (!soundEnabled && bgmPlaying) {
    stopBgm();
  }
  return soundEnabled;
}

export function toggleSound() {
  return setSoundEnabled(!soundEnabled);
}

export function getAudioContext() {
  if (!audioCtx) {
    const AudioContextClass = (typeof window !== 'undefined')
      ? (window.AudioContext || window.webkitAudioContext)
      : null;
    if (AudioContextClass) {
      audioCtx = new AudioContextClass();
    }
  }
  // 'suspended' is how a context starts; iOS also parks it as 'interrupted'
  // after a call or an app switch. Anything but 'running' needs a resume.
  if (audioCtx && audioCtx.state !== 'running' && typeof audioCtx.resume === 'function') {
    try {
      audioCtx.resume()?.catch?.(() => {});
    } catch {
      // Nothing to do: the next tap tries again.
    }
  }
  return audioCtx;
}

// iOS Safari starts (and resumes) audio only inside a user gesture. The quiz
// plays its feedback sound after the tap is over — Ranked waits for the server
// to say whether the answer was right — so a context first touched there stays
// silent for ever. Every tap therefore opens the audio itself, synchronously:
// create/resume the context and start a one-sample silent buffer, which is
// what iOS takes as "this page plays sound". Once it is running a tap costs
// one comparison.
export function unlockAudio() {
  if (!soundEnabled) return;
  if (audioCtx && audioCtx.state === 'running') return;
  const ctx = getAudioContext();
  if (!ctx) return;
  try {
    const source = ctx.createBufferSource();
    source.buffer = ctx.createBuffer(1, 1, 22050);
    source.connect(ctx.destination);
    source.start(0);
  } catch {
    // Graceful degrade if audio is unavailable
  }
}

export function installAudioUnlock(target) {
  if (!target || typeof target.addEventListener !== 'function') return;
  for (const type of ['pointerdown', 'touchend', 'keydown']) {
    target.addEventListener(type, unlockAudio, { capture: true, passive: true });
  }
}

if (typeof document !== 'undefined') installAudioUnlock(document);

export function playTone(freq, type = 'sine', duration = 0.15, delay = 0, gainLevel = 0.15) {
  if (!soundEnabled) return;
  const ctx = getAudioContext();
  if (!ctx) return;

  try {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = type;
    osc.frequency.setValueAtTime(freq, ctx.currentTime + delay);

    gain.gain.setValueAtTime(gainLevel, ctx.currentTime + delay);
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + delay + duration);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start(ctx.currentTime + delay);
    osc.stop(ctx.currentTime + delay + duration);
  } catch {
    // Graceful degrade if audio device fails
  }
}

export function playCorrectSfx() {
  // Ascending arpeggio: C5 (523Hz), E5 (659Hz), G5 (784Hz), C6 (1046Hz)
  playTone(523.25, 'sine', 0.15, 0.00, 0.20);
  playTone(659.25, 'sine', 0.16, 0.08, 0.20);
  playTone(783.99, 'sine', 0.18, 0.16, 0.22);
  playTone(1046.50, 'sine', 0.35, 0.24, 0.25);
}

export function playIncorrectSfx() {
  // Soft double buzzer: A3 (220Hz), F3 (174Hz)
  playTone(220, 'triangle', 0.18, 0.00, 0.25);
  playTone(174.61, 'triangle', 0.28, 0.12, 0.25);
}

const BGM_NOTES = [
  { f: 261.63, d: 0.3 }, // C4
  { f: 329.63, d: 0.3 }, // E4
  { f: 392.00, d: 0.3 }, // G4
  { f: 523.25, d: 0.4 }, // C5
  { f: 440.00, d: 0.3 }, // A4
  { f: 392.00, d: 0.3 }, // G4
  { f: 349.23, d: 0.3 }, // F4
  { f: 329.63, d: 0.5 }, // E4
];

function tickBgm() {
  if (!bgmPlaying) return;
  const note = BGM_NOTES[bgmIndex % BGM_NOTES.length];
  playTone(note.f, 'sine', note.d, 0, 0.035);
  bgmIndex++;
  bgmTimer = setTimeout(tickBgm, 420);
}

export function startBgm() {
  if (bgmPlaying) return;
  getAudioContext();
  bgmPlaying = true;
  tickBgm();
}

export function stopBgm() {
  bgmPlaying = false;
  if (bgmTimer) {
    clearTimeout(bgmTimer);
    bgmTimer = null;
  }
}

export function isBgmPlaying() {
  return bgmPlaying;
}
