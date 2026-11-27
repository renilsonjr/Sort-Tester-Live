// Versus -- the server's routes, one function each. Every call answers
// { ok, status, data } and never throws: a duel is polled once a second,
// and a dropped request is a missed beat, not an error screen.
export function createVersusClient({ fetchFn = (...args) => fetch(...args), base = '/api/versus' } = {}) {
  async function send(method, path, body) {
    const options = { method, headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin' };
    if (body !== undefined) options.body = JSON.stringify(body);
    let response;
    try {
      response = await fetchFn(`${base}${path}`, options);
    } catch {
      return { ok: false, status: 0, data: null };
    }
    let data = null;
    try { data = await response.json(); } catch { data = null; }
    return { ok: response.ok, status: response.status, data };
  }

  const id = value => encodeURIComponent(String(value));

  return {
    createRoom: game => send('POST', '/rooms', { game }),
    joinRoom: code => send('POST', '/rooms/join', { code }),
    readRoom: roomId => send('GET', `/rooms/${id(roomId)}`),
    leaveRoom: roomId => send('POST', `/rooms/${id(roomId)}/leave`),
    startMatch: roomId => send('POST', `/rooms/${id(roomId)}/start`),
    readMatch: matchId => send('GET', `/matches/${id(matchId)}`),
    question: matchId => send('GET', `/matches/${id(matchId)}/question`),
    answer: (matchId, seq, choice) => send('POST', `/matches/${id(matchId)}/answer`, { seq, choice: choice ?? '' }),
    progress: (matchId, score, final = false) => send('POST', `/matches/${id(matchId)}/progress`, { score, final }),
    forfeit: matchId => send('POST', `/matches/${id(matchId)}/forfeit`),
    leaderboard: () => send('GET', '/leaderboard'),
  };
}
