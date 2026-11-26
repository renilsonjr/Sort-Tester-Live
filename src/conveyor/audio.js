// Handler (internal name: conveyor) stage 3 -- rule 21, the sound.
//
// A faithful port of the prototype's synthesiser, which is the version the
// owner approved. Levels and note choices are HIS, not mine: an earlier pass
// of this file guessed them and came out two to three times too quiet, which
// is why the game sounded like it had no sound at all. Do not retune by ear
// without saying so -- #397 is where the owner tunes these after playing.
//
// Everything is synthesised: there is no audio file in the repository and
// this adds none. The audio context and the on/off preference are the app's
// own (src/sound.js), so the header switch that silences the quiz silences
// Handler too. Nothing is created until start() runs, and start() runs when
// the player starts a round -- never on page load.

// One master, then a bus per bed, exactly as the prototype has it. The cues
// go straight to master so they always cut through the belt.
export const MASTER_GAIN = 0.85;
export const MUSIC_GAIN = 0.15;
// The belt is the room, not an instrument. The owner asked three times for it
// to come down; this is where it stopped.
export const BELT_GAIN = 0.035;
export const HUM_GAIN = 0.012;
export const MELODY_MS = 150;

const MELODY = [0, 3, 7, 3, 5, 3, 0, -2, 0, 3, 7, 10, 7, 5, 3, 0];
const BASS = [0, 0, -5, -5, -7, -7, -5, -5];
const hz = semitone => 220 * (2 ** (semitone / 12));

export function createHandlerAudio({ getContext, isEnabled = () => true } = {}) {
  if (typeof getContext !== 'function') throw new Error('createHandlerAudio needs a getContext function');
  let context = null;
  let master = null;
  let musicBus = null;
  let beltBus = null;
  let beltFilter = null;
  let hum = null;
  let beltSource = null;
  let timer = null;
  let playing = false;
  let step = 0;

  // One voice. Every cue is built from this, so a cue can never outlive its
  // own envelope and leave an oscillator running.
  function blip(frequency, at, duration, type, gain, slideTo = null, bus = null) {
    if (!context || !isEnabled()) return;
    try {
      const osc = context.createOscillator();
      const envelope = context.createGain();
      osc.type = type;
      osc.frequency.setValueAtTime(frequency, at);
      if (slideTo) osc.frequency.exponentialRampToValueAtTime(slideTo, at + duration);
      envelope.gain.setValueAtTime(0, at);
      envelope.gain.linearRampToValueAtTime(gain, at + 0.012);
      envelope.gain.exponentialRampToValueAtTime(0.0008, at + duration);
      osc.connect(envelope).connect(bus || master);
      osc.start(at);
      osc.stop(at + duration + 0.03);
    } catch { /* A device that refuses a voice just stays quiet. */ }
  }

  function tick() {
    if (!context || !playing || !isEnabled()) return;
    const at = context.currentTime + 0.03;
    blip(hz(MELODY[step % MELODY.length] + 12), at, 0.15, 'square', 0.5, null, musicBus);
    if (step % 2 === 0) blip(hz(BASS[(step / 2) % BASS.length] - 12), at, 0.26, 'triangle', 0.75, null, musicBus);
    step += 1;
  }

  function build() {
    if (master) return true;
    const next = getContext();
    if (!next) return false;
    context = next;
    try {
      master = context.createGain();
      master.gain.value = MASTER_GAIN;
      master.connect(context.destination);

      musicBus = context.createGain();
      musicBus.gain.value = MUSIC_GAIN;
      musicBus.connect(master);

      // The belt comes up from silence when the round starts, rather than
      // banging on with the first frame.
      beltBus = context.createGain();
      beltBus.gain.value = 0;
      beltBus.connect(master);

      // Low-passed brown noise for the rubber, plus a sawtooth motor under it.
      const length = Math.floor(context.sampleRate * 2);
      const buffer = context.createBuffer(1, length, context.sampleRate);
      const data = buffer.getChannelData(0);
      let value = 0;
      for (let i = 0; i < length; i += 1) {
        value = value * 0.94 + (Math.random() * 2 - 1) * 0.06;
        data[i] = Math.max(-1, Math.min(1, value * 3));
      }
      beltSource = context.createBufferSource();
      beltSource.buffer = buffer;
      beltSource.loop = true;
      beltFilter = context.createBiquadFilter();
      beltFilter.type = 'lowpass';
      beltFilter.frequency.value = 420;
      beltSource.connect(beltFilter).connect(beltBus);

      hum = context.createOscillator();
      hum.type = 'sawtooth';
      hum.frequency.value = 58;
      const humFilter = context.createBiquadFilter();
      humFilter.type = 'lowpass';
      humFilter.frequency.value = 150;
      const humGain = context.createGain();
      humGain.gain.value = HUM_GAIN;
      hum.connect(humFilter).connect(humGain).connect(beltBus);

      beltSource.start();
      hum.start();
      return true;
    } catch {
      master = null;
      return false;
    }
  }

  function start() {
    if (!build()) return;
    playing = true;
    if (!timer) timer = setInterval(tick, MELODY_MS);
  }

  function stop() {
    playing = false;
    if (timer) { clearInterval(timer); timer = null; }
    try { beltBus?.gain.setTargetAtTime(0, context.currentTime, 0.07); } catch { /* already quiet */ }
  }

  // The belt's voice follows the live speed, which is most of why Expert
  // feels like Expert. Ramps rather than jumps, so an accelerating belt rises
  // instead of stepping.
  function belt(speed) {
    if (!context || !beltFilter || !playing || !isEnabled()) return;
    const amount = Math.min(1, Math.max(0, (speed - 42) / 90));
    const now = context.currentTime;
    try {
      beltBus.gain.setTargetAtTime(BELT_GAIN, now, 0.2);
      beltFilter.frequency.setTargetAtTime(330 + 520 * amount, now, 0.25);
      hum.frequency.setTargetAtTime(52 + 34 * amount, now, 0.25);
    } catch { /* an old context keeps one pitch */ }
  }

  const now = () => context.currentTime;
  const sorted = () => {
    if (!context) return;
    blip(880, now(), 0.07, 'square', 0.2);
    blip(1318, now() + 0.07, 0.12, 'square', 0.18);
  };
  const missort = () => { if (context) blip(300, now(), 0.26, 'sawtooth', 0.2, 90); };
  // A drop is a thud, not a wrong answer: they are different mistakes.
  const dropped = () => { if (context) blip(150, now(), 0.22, 'sine', 0.3, 52); };

  // Reaching a tier: a short rising arpeggio, longer and higher at each step,
  // timed to land inside the badge's 300ms bump so the sound and the movement
  // read as one event.
  function tier(multiplier) {
    if (!context) return;
    const at = now();
    const steps = multiplier >= 4 ? [12, 16, 19, 24, 28]
      : multiplier >= 3 ? [7, 12, 16, 19]
        : [0, 7, 12];
    steps.forEach((semitone, i) => blip(hz(semitone + 12), at + i * 0.055, 0.15, 'square', 0.14 + 0.02 * multiplier));
    if (multiplier >= 4) blip(hz(31), at + 0.3, 0.26, 'triangle', 0.1);
  }

  return { start, stop, belt, sorted, missort, dropped, tier, get running() { return playing; } };
}
