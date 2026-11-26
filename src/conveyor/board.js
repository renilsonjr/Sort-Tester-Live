// The Handler leaderboard's read (#417): one board per mode, for the newest
// season. Read-only, and it asks for one mode at a time on purpose -- modes
// are never compared or combined (rule 16), so there is no "overall" to ask
// for.
//
// The answer is one of three plain states, so the screen never has to read
// an HTTP status: the board itself, a guest who must sign in to see it, or a
// failure that is said rather than drawn as an empty board.
export function createHandlerBoard({ fetchFn = (...args) => fetch(...args), base = '/api/handler' } = {}) {
  async function load(mode) {
    try {
      const answer = await fetchFn(`${base}/leaderboard?mode=${encodeURIComponent(mode)}`, {
        method: 'GET', credentials: 'same-origin',
      });
      if (answer.status === 401) return { state: 'guest' };
      if (!answer.ok) return { state: 'error' };
      const body = await answer.json();
      return {
        state: 'ok',
        mode,
        seasonLabel: body?.season_label ?? null,
        open: body?.open === true,
        rows: Array.isArray(body?.rows) ? body.rows : [],
        players: Number.isInteger(body?.players) ? body.players : 0,
        you: body?.you ?? null,
      };
    } catch {
      return { state: 'error' };
    }
  }
  return { load };
}
