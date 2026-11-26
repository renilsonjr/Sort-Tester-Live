// Handler's best score, one per mode (#396).
//
// The only thing the first release stores. It is kept per account on the
// server, so it follows the player to another phone -- but a guest can play
// too, and a guest's score is kept in this page's memory and said to be
// unsaved rather than shown as a silent zero.
//
// The screen reads these synchronously while it is drawing, so the figures
// live in a local cache: load() fills it once, set() updates it at once and
// sends the raise afterwards. A failed send costs the player nothing on
// screen this round; the cache is still right for the rest of the session.
export const MODES = ['easy', 'medium', 'hard', 'expert'];

const blank = () => Object.fromEntries(MODES.map(mode => [mode, 0]));

export function createBestScores({ fetchFn = (...args) => fetch(...args), base = '/api/handler' } = {}) {
  let cache = blank();
  // null until load() has been answered: "not known yet" is not "guest".
  let signedIn = null;
  let lastError = null;

  async function send(method, body) {
    const options = { method, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
    if (body !== undefined) options.body = JSON.stringify(body);
    return fetchFn(`${base}/best`, options);
  }

  async function load() {
    try {
      const answer = await send('GET');
      if (answer.status === 401) { signedIn = false; return cache; }
      if (!answer.ok) { lastError = `HTTP ${answer.status}`; return cache; }
      const body = await answer.json();
      signedIn = true;
      cache = { ...blank(), ...(body?.best ?? {}) };
    } catch (error) {
      // Offline, or the server is down. The game still plays; the score
      // simply is not kept, and the end-of-round screen says so.
      lastError = String(error?.message ?? error);
      signedIn = false;
    }
    return cache;
  }

  function get(mode) {
    return cache[mode] ?? 0;
  }

  function set(mode, score) {
    if (!MODES.includes(mode) || !Number.isInteger(score) || score < 0) return;
    if (score <= get(mode)) return;
    cache[mode] = score;
    if (signedIn === false) return;
    // Nothing waits on this: the screen has already drawn the new best.
    send('PUT', { mode, score }).then(answer => {
      if (answer?.status === 401) signedIn = false;
    }).catch(error => { lastError = String(error?.message ?? error); });
  }

  return {
    load,
    get,
    set,
    // What the end-of-round screen needs to tell the truth about storage.
    get saved() { return signedIn === true; },
    get lastError() { return lastError; },
  };
}
