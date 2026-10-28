export function createClock({ durationMs, now = () => Date.now() }) {
  let startedAt = null;
  let pausedAt = null;
  let lostMs = 0;

  function elapsed() {
    if (startedAt === null) return 0;
    const upTo = pausedAt === null ? now() : pausedAt;
    return upTo - startedAt - lostMs;
  }

  return {
    start() {
      startedAt = now();
      pausedAt = null;
      lostMs = 0;
    },
    pause() {
      if (startedAt !== null && pausedAt === null) pausedAt = now();
    },
    resume() {
      if (pausedAt === null) return;
      lostMs += now() - pausedAt;
      pausedAt = null;
    },
    elapsed,
    remaining() {
      return Math.max(0, durationMs - elapsed());
    },
    expired() {
      return durationMs - elapsed() <= 0;
    },
  };
}
