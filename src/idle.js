// The inactivity rule, on its own so it can be tested without a browser.
//
// A sorter puts the phone down mid-shift; the account should not stay open
// on it. Fifteen minutes of no touch and no key ends the session, with a
// minute's warning first so nobody is dropped mid-quiz without knowing why.
//
// The server enforces the same window (backend/auth/settings.py,
// session_idle_seconds). This is the visible half of the rule, never the
// whole of it: a page can be kept awake, a revoked session cannot.

export const IDLE_LIMIT_MS = 15 * 60 * 1000;
export const IDLE_WARNING_MS = 60 * 1000;

// Timers in a backgrounded tab are throttled, so the verdict is read off
// the wall clock: how long ago the last touch was, not how many ticks have
// gone by. A phone that was away for an hour is out the moment it is
// looked at again.
export function idleVerdict(
  now,
  lastSeen,
  limit = IDLE_LIMIT_MS,
  warning = IDLE_WARNING_MS,
) {
  const idleFor = now - lastSeen;
  if (idleFor >= limit) return 'out';
  if (idleFor >= limit - warning) return 'warn';
  return 'active';
}
