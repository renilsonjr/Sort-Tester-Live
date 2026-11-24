// The season bubble (#452): one small notice at the top of Home, the login
// screen and the profile. Every screen reads the same public endpoint, so
// they cannot disagree about the date (#338).
//
// Three states, all from /api/ranked/season/notice:
//   upcoming  not launched yet: the owner's announced start (Dec 1, 2026,
//             midnight Eastern) and that Pre-Season points go back to 0
//   live      launched and still admitting: it is on, and when it ends
//   ended     its end has passed
// An X closes it. Closing remembers the state and its date on this device,
// so a closed "starts on" bubble comes back once the season is live.

const DISMISSED_BUBBLE_STORE = 'sortTest.seasonBubble.v1';
const ZONE = 'America/New_York';

export async function readSeasonNotice(fetchFn = fetch) {
  try {
    const response = await fetchFn('/api/ranked/season/notice', { credentials: 'same-origin' });
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;  // no backend, as on the static page: show nothing at all
  }
}

// The date in words ("December 1, 2026" / "1 de diciembre de 2026"),
// read in Eastern time, where the season's dates are set.
export function longDate(value, locale) {
  const when = new Date(value);
  if (Number.isNaN(when.getTime())) return '';
  return when.toLocaleDateString(locale, { year: 'numeric', month: 'long', day: 'numeric', timeZone: ZONE });
}

function clockTime(value, locale) {
  const when = new Date(value);
  if (Number.isNaN(when.getTime())) return '';
  return when.toLocaleTimeString(locale, { hour: 'numeric', minute: '2-digit', timeZone: ZONE, timeZoneName: 'short' });
}

// What the bubble says, or null when it should say nothing. `t` is the
// app's translator, `locale` its date locale.
export function seasonBubbleCopy(notice, { t, locale, signedIn, now = Date.now() }) {
  if (!notice) return null;
  if (notice.started && notice.started_at) {
    const started = longDate(notice.started_at, locale);
    const closes = notice.closes_at ? longDate(notice.closes_at, locale) : null;
    // Once the season's end has passed, "is live" is stale: nobody can
    // start a quiz for points any more. It does not say points are final:
    // attempts already started have five more minutes.
    if (notice.closes_at && new Date(notice.closes_at).getTime() <= now) {
      const ran = t('It ran from {start} to {end}.', { start: started, end: closes });
      return {
        state: `ended|${notice.closes_at}`,
        title: t('The official season has ended'),
        text: signedIn ? `${ran} ${t('The leaderboard has the results.')}` : ran,
      };
    }
    const ends = closes ? t('It ends {date}.', { date: closes }) : '';
    return {
      state: `live|${notice.started_at}`,
      title: t('The official season is live'),
      text: `${ends} ${t(signedIn ? 'Everyone began again at 0 points and Iron.' : 'Log in to play for points this season.')}`.trim(),
    };
  }
  if (!notice.announced_start) return null;
  return {
    state: `upcoming|${notice.announced_start}`,
    title: t('The official season starts {date}', { date: longDate(notice.announced_start, locale) }),
    text: `${t('It starts at {time}.', { time: clockTime(notice.announced_start, locale) })} ${t('Pre-Season points go back to 0 that day.')}`,
  };
}

function dismissed(storage) {
  try { return storage?.getItem(DISMISSED_BUBBLE_STORE) ?? ''; } catch { return ''; }
}

// Fill a bubble host: an element with [data-bubble-title], [data-bubble-text]
// and a [data-bubble-close] button inside, hidden until there is something
// to say.
export function showSeasonBubble(box, copy, { storage, closeLabel } = {}) {
  if (!box) return;
  if (!copy || dismissed(storage) === copy.state) {
    box.hidden = true;
    return;
  }
  box.querySelector('[data-bubble-title]').textContent = copy.title;
  box.querySelector('[data-bubble-text]').textContent = copy.text;
  const close = box.querySelector('[data-bubble-close]');
  if (closeLabel) close.setAttribute('aria-label', closeLabel);
  close.onclick = () => {
    try { storage?.setItem(DISMISSED_BUBBLE_STORE, copy.state); } catch { /* closes for this visit only */ }
    box.hidden = true;
  };
  box.hidden = false;
}

export function seasonBubbleMarkup(id = 'season-bubble') {
  return `
    <section class="season-bubble" id="${id}" hidden aria-live="polite">
      <i aria-hidden="true">!</i>
      <div class="season-bubble-body">
        <h2 data-bubble-title></h2>
        <p data-bubble-text></p>
      </div>
      <button type="button" class="season-bubble-close" data-bubble-close aria-label="Close">×</button>
    </section>`;
}
