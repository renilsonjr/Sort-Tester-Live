// Playing one server-authoritative attempt (issue #24, slice 7).
//
// The first client in the app that plays a Ranked-engine attempt, written
// on its own so ordinary Ranked play can reuse it rather than repeat it.
// The server owns everything that matters: the clock, which question is
// live, whether an answer counts. This module only carries requests and
// keeps the two things the server asks the page to keep:
//
// * the page capability, issued once when the attempt starts and sent on
//   every later request in a header. It lives in this object's memory
//   only -- never storage, never the URL -- so a refresh cannot resume the
//   attempt, which is the settled rule.
// * a heartbeat while the attempt runs, so the server can tell a page that
//   is still here from one that went away. Missing it is not a penalty by
//   itself: the server gives 15 seconds of grace before ending the attempt.

const CAPABILITY_HEADER = 'X-Attempt-Capability';
export const HEARTBEAT_MS = 1000;

export function createAttemptClient({ fetchFn = (...a) => fetch(...a), base = '/api' } = {}) {
  let attemptId = null;
  let capability = null;
  let beat = null;

  async function send(method, path, body) {
    const headers = { 'Content-Type': 'application/json' };
    if (capability) headers[CAPABILITY_HEADER] = capability;
    const options = { method, headers, credentials: 'same-origin' };
    if (body !== undefined) options.body = JSON.stringify(body);
    let response;
    try {
      response = await fetchFn(`${base}${path}`, options);
    } catch {
      return { ok: false, status: 0, data: null };
    }
    if (response.status === 204) return { ok: true, status: 204, data: null };
    let data = null;
    try {
      data = await response.json();
    } catch {
      data = null;
    }
    return { ok: response.ok, status: response.status, data };
  }

  return {
    get attemptId() { return attemptId; },

    // Start the attempt at a URL that returns {attempt_id, capability}.
    async start(path) {
      const result = await send('POST', path);
      if (result.ok) {
        attemptId = result.data.attempt_id;
        capability = result.data.capability;
      }
      return result;
    },

    current() {
      return send('GET', `/ranked/attempts/${attemptId}/current`);
    },

    answer(seq, choice) {
      return send('POST', `/ranked/attempts/${attemptId}/answer`, { seq, choice });
    },

    quit() {
      return send('POST', `/ranked/attempts/${attemptId}/quit`);
    },

    heartbeat() {
      return send('POST', `/ranked/attempts/${attemptId}/heartbeat`);
    },

    startHeartbeat(setIntervalFn = setInterval) {
      if (beat === null) beat = setIntervalFn(() => { this.heartbeat(); }, HEARTBEAT_MS);
    },

    // Forget everything: the attempt cannot be resumed from this object.
    stop(clearIntervalFn = clearInterval) {
      if (beat !== null) clearIntervalFn(beat);
      beat = null;
      capability = null;
    },
  };
}
