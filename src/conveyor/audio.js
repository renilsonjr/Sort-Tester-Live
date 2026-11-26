// Handler (internal name: conveyor) stage 3 -- rule 21, the sound.
//
// Four cues and two beds, all synthesised: there is no audio file in the
// repository and this adds none. The audio context and the on/off preference
// are the app's own (src/sound.js), so the header switch that silences the
// quiz silences Handler too. Nothing here is created until start() runs, and
// start() runs when the player starts a round -- never on page load.
//
// The levels were set by ear on the prototype after the owner asked three
// times for the belt to be quieter. The belt is the room, not an instrument:
// the sort and missort cues have to cut through it.
export const BELT_GAIN = 0.035;
export const HUM_GAIN = 0.012;
export const MUSIC_GAIN = 0.03;
// The belt noise follows the live speed, which is most of why Expert feels
// like Expert. These two map the modes' speed range onto the filter.
export const BELT_SPEED_FLOOR = 42;
export const BELT_SPEED_CEILING = 132;

const MELODY = [0, 4, 7, 12, 7, 4, 2, 4];
const BASE_HZ = 196; // G3, under the belts rather than over them.

// A short noise buffer, looped, is the belt. A sawtooth under it is the motor.
function brownNoise(context, seconds = 2) {
  const buffer = context.createBuffer(1, Math.floor(context.sampleRate * seconds), context.sampleRate);
  const data = buffer.getChannelData(0);
  let last = 0;
  for (let i = 0; i < data.length; i += 1) {
    // A deterministic walk rather than Math.random, so two runs sound alike
    // and a test can assert the buffer without a seeded generator.
    const step = Math.sin(i * 0.000731) * 0.6 + Math.sin(i * 0.004297) * 0.4;
    last = (last + step * 0.02) / 1.02;
    data[i] = last * 3.2;
  }
  return buffer;
}

export function createHandlerAudio({ getContext, isEnabled = () => true } = {}) {
  if (typeof getContext !== 'function') throw new Error('createHandlerAudio needs a getContext function');
  let context = null;
  let bus = null;
  let beltBus = null;
  let beltSource = null;
  let beltFilter = null;
  let hum = null;
  let humGain = null;
  let musicTimer = null;
  let musicStep = 0;
  let running = false;

  const live = () => running && context && isEnabled();

  function now() {
    return context.currentTime;
  }

  // One voice. Every cue is built from this, so a cue can never outlive its
  // own envelope and leave an oscillator running.
  function voice({ type = 'square', hz, from = 0, length = 0.14, gain = 0.12, slideTo = null }) {
    if (!live()) return;
    try {
      const osc = context.createOscillator();
      const envelope = context.createGain();
      osc.type = type;
      const at = now() + from;
      osc.frequency.setValueAtTime(hz, at);
      if (slideTo !== null) osc.frequency.linearRampToValueAtTime(slideTo, at + length);
      envelope.gain.setValueAtTime(0.0001, at);
      envelope.gain.exponentialRampToValueAtTime(gain, at + 0.012);
      envelope.gain.exponentialRampToValueAtTime(0.0001, at + length);
      osc.connect(envelope);
      envelope.connect(bus);
      osc.start(at);
      osc.stop(at + length + 0.02);
    } catch { /* A device that refuses a voice just stays quiet. */ }
  }

  function tickMusic() {
    if (!live()) return;
    const semitone = MELODY[musicStep % MELODY.length];
    voice({ type: 'square', hz: BASE_HZ * (2 ** (semitone / 12)), length: 0.26, gain: MUSIC_GAIN });
    if (musicStep % 4 === 0) voice({ type: 'triangle', hz: BASE_HZ / 2, length: 0.38, gain: MUSIC_GAIN * 1.2 });
    musicStep += 1;
    musicTimer = setTimeout(tickMusic, 300);
  }

  function start() {
    if (running) return;
    const next = getContext();
    if (!next) return;
    context = next;
    running = true;
    try {
      bus = context.createGain();
      bus.gain.value = 1;
      bus.connect(context.destination);

      beltBus = context.createGain();
      beltBus.gain.value = BELT_GAIN;
      beltBus.connect(context.destination);

      beltFilter = context.createBiquadFilter();
      beltFilter.type = 'lowpass';
      beltFilter.frequency.value = 520;
      beltFilter.connect(beltBus);

      beltSource = context.createBufferSource();
      beltSource.buffer = brownNoise(context);
      beltSource.loop = true;
      beltSource.connect(beltFilter);
      beltSource.start(0);

      humGain = context.createGain();
      humGain.gain.value = HUM_GAIN;
      humGain.connect(beltBus);
      hum = context.createOscillator();
      hum.type = 'sawtooth';
      hum.frequency.value = 58;
      hum.connect(humGain);
      hum.start(0);

      musicStep = 0;
      tickMusic();
    } catch {
      running = false;
    }
  }

  function stop() {
    running = false;
    if (musicTimer) { clearTimeout(musicTimer); musicTimer = null; }
    for (const node of [beltSource, hum]) {
      try { node?.stop?.(0); } catch { /* Already stopped. */ }
    }
    for (const node of [bus, beltBus, beltFilter, humGain]) {
      try { node?.disconnect?.(); } catch { /* Already gone. */ }
    }
    beltSource = null; hum = null; beltFilter = null; beltBus = null; humGain = null; bus = null;
  }

  // The belt's voice follows the live speed. A ramp rather than a jump, so an
  // accelerating Expert belt rises instead of stepping.
  function belt(speed) {
    if (!live() || !beltFilter) return;
    const span = BELT_SPEED_CEILING - BELT_SPEED_FLOOR;
    const amount = Math.min(1, Math.max(0, (speed - BELT_SPEED_FLOOR) / span));
    try {
      beltFilter.frequency.setTargetAtTime(420 + 680 * amount, now(), 0.25);
      if (hum) hum.frequency.setTargetAtTime(52 + 26 * amount, now(), 0.25);
    } catch { /* An old context without setTargetAtTime keeps one pitch. */ }
  }

  // Rule 20's three outcomes, and rule 21's tier cue.
  const sorted = () => { voice({ type: 'square', hz: 740, length: 0.09, gain: 0.14 }); voice({ type: 'square', hz: 1110, from: 0.07, length: 0.12, gain: 0.13 }); };
  const missort = () => { voice({ type: 'sawtooth', hz: 260, length: 0.16, gain: 0.14, slideTo: 150 }); };
  // A drop is a thud, not a wrong answer: they are different mistakes.
  const dropped = () => { voice({ type: 'triangle', hz: 120, length: 0.2, gain: 0.18, slideTo: 62 }); };
  // The tier cue is a rising arpeggio, longer and higher at each step, played
  // inside the badge's bump so the sound and the movement are one event.
  function tier(multiplier) {
    const steps = Math.max(2, Math.min(4, Math.round(multiplier)));
    for (let i = 0; i < steps; i += 1) {
      voice({ type: 'square', hz: 520 * (2 ** ((steps * 2 + i * 4) / 12)), from: i * 0.055, length: 0.1 + i * 0.02, gain: 0.12 });
    }
  }

  return { start, stop, belt, sorted, missort, dropped, tier, get running() { return running; } };
}
