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
  let goneHandler = null;

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
    async start(path, body) {
      const result = await send('POST', path, body);
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

    // Ordinary Ranked and promotion hold feedback until the player presses
    // Next (settled Q8); this is that press. A tie-break has no Next --
    // it never calls this -- because its questions advance by themselves.
    advance() {
      return send('POST', `/ranked/attempts/${attemptId}/advance`);
    },

    quit() {
      return send('POST', `/ranked/attempts/${attemptId}/quit`);
    },

    // The settled result of an attempt that has already ended (Quit's own
    // response already carries it; this is for an attempt the page finds
    // ended on a later read, e.g. the final answer completed it).
    result() {
      return send('GET', `/ranked/attempts/${attemptId}/result`);
    },

    heartbeat() {
      return send('POST', `/ranked/attempts/${attemptId}/heartbeat`);
    },

    startHeartbeat(setIntervalFn = setInterval) {
      if (beat !== null) return;
      beat = setIntervalFn(async () => {
        const answer = await this.heartbeat();
        if (answer.status !== 410 || !goneHandler) return;
        const tell = goneHandler;
        goneHandler = null;  // told once; the next screen asks again if it cares
        tell();
      }, HEARTBEAT_MS);
    },

    // Who to tell when the server says the attempt is gone (410) while the
    // page is only watching a question: the season launched, or the server's
    // clock ended the attempt. The heartbeat is the one request still going
    // then, so without this the question stays on screen with nothing behind
    // it. One handler, called once; the screen showing sets it again.
    onGone(handler) {
      goneHandler = handler;
    },

    // Forget everything: the attempt cannot be resumed from this object.
    stop(clearIntervalFn = clearInterval) {
      if (beat !== null) clearIntervalFn(beat);
      beat = null;
      capability = null;
      goneHandler = null;
    },
  };
}
