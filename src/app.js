import { BELT_STYLE } from './belts.js';
import { avatarEmoji } from './avatars.js';
import { formatDestinationLabel } from './destination.js?v=chart-destination-20261108-r2';
import { SERVICE_LABEL } from './questions.js?v=chart-destination-20261108-r2';
import { DECKS, deckById, deckLabel } from './decks.js?v=chart-destination-20261108-r2';
import { CARD_SECONDS, createRun, currentCard, answerCard, timeoutCard, summarize } from './quiz.js?v=chart-destination-20261108-r2';
import { createClock } from './clock.js';
import { createShiftLog } from './shiftLog.js';
import { saveWorkbook } from './exportFile.js';
import { CHART, searchChart } from './study.js?v=chart-destination-20261108-r2';
import { selectLevelCards } from './levels.js?v=sort-change-20261116-r1';
import { createLanguage } from './i18n.js?v=chart-destination-20261108-r2';
import { logout } from './auth.js';
import { createOwnerScreens } from './ownerScreens.js';
import { createProfileScreens } from './profileScreens.js';
import { escapeHtml as esc } from './common.js';
import { longDate, readSeasonNotice, seasonBubbleCopy, seasonBubbleMarkup, showSeasonBubble } from './seasonNotice.js';
import { idleVerdict } from './idle.js';
import { createAttemptClient } from './attemptClient.js';
import { playCorrectSfx, playIncorrectSfx, isSoundEnabled, toggleSound, setMusicWanted, getAudioContext } from './sound.js';
import * as conveyorEngine from './conveyor/engine.js';
import * as conveyorRoutes from './conveyor/routes.js';
import { createHandlerScreen } from './conveyor/view.js';
import { createHandlerAudio } from './conveyor/audio.js';
import { createBestScores } from './conveyor/bestScores.js';
import { createHandlerBoard } from './conveyor/board.js';
import { createVersusClient } from './versus/client.js';
import { createVersusScreens } from './versus/screens.js';
import { HANDLER_DUEL_MODE, seededRandom } from './versus/logic.js';

const app = document.getElementById('app');
const log = createShiftLog(typeof localStorage === 'undefined' ? null : localStorage);
const language = createLanguage(typeof localStorage === 'undefined' ? null : localStorage);
const t = (source, values) => language.text(source, values);
let studyService = 'Ground';
let studyQuery = '';

let run = null;
let clock = null;
let frame = null;
let activeDeck = null;
let feedbackTimer = null;
let resumeTick = null;
// True while the stop panel is up. The card's clock stays paused behind it, so
// a screen lock and unlock must not quietly start it running again.
let bailOpen = false;

// The Artifact sandbox blocks any download a page starts itself, so a saved
// file has to go through the platform's downloads capability. A normal web
// browser uses its own download API when this capability is absent.
let downloadsHandle;
function getDownloads() {
  if (downloadsHandle === undefined) {
    const use = typeof window !== 'undefined' && window.claude && window.claude.use;
    downloadsHandle = typeof use === 'function'
      ? Promise.resolve(window.claude.use('downloads')).catch(() => null)
      : Promise.resolve(null);
  }
  return downloadsHandle;
}

// How long a belt shows right or wrong before the feedback screen takes
// over, in Ranked and in Practice alike. Owner decision, 2026-11-25: 250 ms.
// It was 550 ms in Ranked and 450 ms in Practice, and in Ranked it comes on
// top of the wait for the server, so it was most of what a player felt
// between tapping a belt and seeing the result.
const FEEDBACK_PAUSE_MS = 250;

function canBuildWorkbook() {
  return typeof window !== 'undefined' && typeof window.XLSX !== 'undefined';
}

// SheetJS is ~900 KB and only needed when the player exports the shift log.
// It used to load from the CDN on every page view; instead it is fetched on
// demand the first time an export runs, keeping the first paint light.
const XLSX_SRC = 'https://cdn.sheetjs.com/xlsx-0.20.3/package/dist/xlsx.full.min.js';
const XLSX_INTEGRITY = 'sha384-EnyY0/GSHQGSxSgMwaIPzSESbqoOLSexfnSMN2AP+39Ckmn92stwABZynq1JyzdT';
let xlsxPromise = null;
function loadXLSX() {
  if (canBuildWorkbook()) return Promise.resolve(window.XLSX);
  if (xlsxPromise) return xlsxPromise;
  xlsxPromise = new Promise((resolve, reject) => {
    const script = document.createElement('script');
    script.src = XLSX_SRC;
    script.integrity = XLSX_INTEGRITY;
    script.crossOrigin = 'anonymous';
    script.onload = () => (canBuildWorkbook() ? resolve(window.XLSX) : reject(new Error('xlsx-missing')));
    script.onerror = () => { xlsxPromise = null; reject(new Error('xlsx-load-failed')); };
    document.head.appendChild(script);
  });
  return xlsxPromise;
}

function clockText(totalMs) {
  const minutes = Math.floor(totalMs / 60000);
  const seconds = Math.floor((totalMs % 60000) / 1000);
  return `${minutes}:${String(seconds).padStart(2, '0')}`;
}

function sheetFrom(rows, headers) {
  // json_to_sheet drops the header row when there are no rows, which would
  // hand over a sheet with no columns at all.
  return rows.length
    ? window.XLSX.utils.json_to_sheet(rows, { header: headers })
    : window.XLSX.utils.aoa_to_sheet([headers]);
}

function buildWorkbook(entries) {
  const XLSX = window.XLSX;
  const resultHeaders = ['Name', 'Test', 'Score', 'Correct', 'Missed', 'Total', 'Time', 'Taken'];
  const missortHeaders = ['Name', 'Test', 'Taken', 'Service', 'State', 'Routing code', 'Answered', 'Correct belt', 'Outcome'];

  const results = entries.map((s) => ({
    Name: s.name || 'Guest',
    Test: s.deck || '',
    Score: `${s.correct}/${s.total}`,
    Correct: s.correct,
    Missed: s.total - s.correct,
    Total: s.total,
    Time: clockText(s.totalMs),
    Taken: language.dateTime(s.takenAt),
  }));

  const missorts = [];
  for (const s of entries) {
    for (const r of s.missed || []) {
      missorts.push({
        Name: s.name || 'Guest',
        Test: s.deck || '',
        Taken: language.dateTime(s.takenAt),
        Service: serviceName(r.svc, r.destinationModifier),
        State: r.state,
        'Routing code': r.code,
        Answered: r.outcome === 'timeout' ? 'ran out of time' : r.answered,
        'Correct belt': r.correctBelt,
        Outcome: r.outcome,
      });
    }
  }

  const resultSheet = sheetFrom(results, resultHeaders);
  resultSheet['!cols'] = [18, 18, 8, 8, 8, 7, 8, 20].map((wch) => ({ wch }));
  const missortSheet = sheetFrom(missorts, missortHeaders);
  missortSheet['!cols'] = [18, 18, 20, 14, 8, 14, 16, 14, 10].map((wch) => ({ wch }));

  const book = XLSX.utils.book_new();
  XLSX.utils.book_append_sheet(book, resultSheet, 'Results');
  XLSX.utils.book_append_sheet(book, missortSheet, 'Missorts');
  return XLSX.write(book, { bookType: 'xlsx', type: 'array' });
}

function renderRoutingCode(value) {
  const code = String(value);
  const range = code.match(/^([\d ]+)[–-]([\d ]+)$/);
  if (!range) return esc(code);
  const [, start, end] = range;
  return `<span class="sr-only">${esc(start)} to ${esc(end)}</span><span class="range-display" aria-hidden="true"><span class="range-number">${esc(start)}</span><span class="range-dash"></span><span class="range-number">${esc(end)}</span></span>`;
}

function serviceName(svc, destinationModifier) {
  return formatDestinationLabel(language.service(SERVICE_LABEL[svc] || svc), destinationModifier);
}

function displayName(name) {
  return name || t('Guest');
}

function el(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

// Handler's screen owns an animation frame, a round clock, audio and
// listeners on the document. Leaving it has to stop all of that, and the
// screen may be left in more ways than one -- a dock tab, the Home stripe,
// a sign-in, a language change that redraws the page. render() is where the
// app already decides the music and the heartbeat on every screen change,
// for the same reason, so it decides this too.
let handlerScreen = null;
function unmountHandler() {
  if (!handlerScreen) return;
  const leaving = handlerScreen;
  handlerScreen = null;
  leaving.unmount();
}

function render(node) {
  if (!node.querySelector?.('[data-handler-root]')) unmountHandler();
  document.documentElement.lang = language.code;
  // #427: the dock goes while a scored attempt is live, the way it already
  // does in Practice (#382) -- a dock under a timed run is a way to lose it,
  // and the Ranked one is the run that costs points. The marker that keeps
  // the heartbeat is the same marker that decides this: one fact about the
  // screen, read once.
  const attemptLive = Boolean(node.querySelector?.('[data-attempt-live]'));
  app.className = (node.classList.contains('lab-shell') ? 'lab-page' : 'quiz-page')
    + (attemptLive ? ' attempt-live' : '');
  app.replaceChildren(node);
  // Music belongs to the Ranked quiz screens only (#264). Deciding it here,
  // on every screen change, means no way out of a quiz can leave it playing.
  setMusicWanted(Boolean(node.querySelector?.('[data-ranked-music]')));
  // #426: the heartbeat belongs to the attempt's own screens, and the same
  // reasoning decides it here. A dock tab used to replace the quiz while the
  // beat went on once a second, so the server never saw the attempt go quiet
  // (it closes one 15s after its last beat) -- it never closed, every new
  // attempt came back 409, and "Preparing your next match" promised "a few
  // seconds" for as long as the page stayed open.
  if (!attemptLive) endLiveAttempt();
  window.scrollTo(0, 0);
}

// The attempt whose heartbeat is running, if any. It is held here, not in
// the screen that started it, because the screen that ENDS it may be any
// other -- a dock tab, a deep link, a session that expires.
let liveAttempt = null;
function holdLiveAttempt(attempt) { liveAttempt = attempt; }
function endLiveAttempt() {
  if (!liveAttempt) return;
  const going = liveAttempt;
  liveAttempt = null;  // cleared first: stop() must not re-enter this
  going.stop();
}

function languageButtons() {
  return `<div class="lab-language" role="group" aria-label="Language / Idioma">
    <button type="button" data-language="en" aria-label="English" aria-pressed="${language.code === 'en'}"><span>EN</span></button>
    <button type="button" data-language="es" aria-label="Español" aria-pressed="${language.code === 'es'}"><span>ES</span></button>
  </div>`;
}

function wireLanguageButtons(view, rerender) {
  view.querySelectorAll('[data-language]').forEach((button) => button.addEventListener('click', () => {
    if (language.code === button.dataset.language) return;
    language.set(button.dataset.language);
    rerender();
  }));
}

// Day / Night theme. Manual only (does not follow the system): the choice is
// kept per device and defaults to Night (the twilight look). The CSS reacts to
// `data-theme` on <html>, so a toggle needs no re-render.
function currentTheme() {
  try { return localStorage.getItem('sortlab-theme') === 'day' ? 'day' : 'night'; } catch { return 'night'; }
}
// The top edge of each theme's page background, which is what the phone's own
// bar sits against. `color-scheme` in the stylesheet handles the scrollbars and
// the field insides; this handles the strip above the page.
const THEME_BAR = { night: '#2b1b11', day: '#fef8ee' };
function applyTheme(theme) {
  const next = theme === 'day' ? 'day' : 'night';
  const root = (typeof document !== 'undefined') ? document.documentElement : null;
  if (root && typeof root.setAttribute === 'function') root.setAttribute('data-theme', next);
  const bar = (typeof document !== 'undefined' && typeof document.querySelector === 'function')
    ? document.querySelector('meta[name="theme-color"]')
    : null;
  if (bar && typeof bar.setAttribute === 'function') bar.setAttribute('content', THEME_BAR[next]);
  try { localStorage.setItem('sortlab-theme', next); } catch { /* private mode: live with the default */ }
}
// Drawn icons, not emoji: see ICONS below (#326). The button shows the theme
// it is IN, as it always did -- a moon at night, a sun by day.
function themeIcon(theme) { return theme === 'day' ? ICONS.day : ICONS.night; }
function themeButton() {
  const day = currentTheme() === 'day';
  return `<button type="button" class="lab-theme-btn" data-theme-toggle aria-label="${esc(t('Switch between day and night'))}" aria-pressed="${day}"><span class="lab-btn-ic" aria-hidden="true">${themeIcon(day ? 'day' : 'night')}</span></button>`;
}
function wireThemeButton(view) {
  const button = view.querySelector('[data-theme-toggle]');
  if (!button) return;
  button.addEventListener('click', () => {
    const next = currentTheme() === 'day' ? 'night' : 'day';
    applyTheme(next);
    // innerHTML, not textContent: the icon is drawn markup now, and
    // textContent would print the SVG source into the button.
    button.innerHTML = `<span class="lab-btn-ic" aria-hidden="true">${themeIcon(next)}</span>`;
    button.setAttribute('aria-pressed', String(next === 'day'));
  });
}
if (typeof document !== 'undefined') applyTheme(currentTheme());

// The three countdown bars (tie-break, Ranked, Practice). The fill is always
// the full width of its track and slides out to the left, so the browser
// composites it instead of laying the page out again on every tick; the
// track's `overflow: hidden` pill clips what leaves. `pct` is 0 to 100 and is
// clamped here rather than at each call site.
function setBarFill(fill, pct) {
  if (!fill?.style) return;
  const shown = Math.max(0, Math.min(100, Number(pct) || 0));
  fill.style.transform = `translateX(${shown - 100}%)`;
}

// One switch for all sound: answer effects everywhere and the Ranked music.
function soundIcon(on) { return on ? ICONS.soundOn : ICONS.soundOff; }
function soundButton() {
  const on = isSoundEnabled();
  return `<button type="button" class="lab-theme-btn" data-sound-toggle aria-label="${esc(t('Sound on or off'))}" aria-pressed="${on}"><span class="lab-btn-ic" aria-hidden="true">${soundIcon(on)}</span></button>`;
}
function wireSoundButton(view) {
  const button = view.querySelector('[data-sound-toggle]');
  if (!button) return;
  button.addEventListener('click', () => {
    const on = toggleSound();
    button.innerHTML = `<span class="lab-btn-ic" aria-hidden="true">${soundIcon(on)}</span>`;
    button.setAttribute('aria-pressed', String(on));
  });
}

// Who is using the app: null until the auth panel says. A guest gets Home
// and Practice; a signed-in player also gets Ranked and Profile (#10, from
// the navigation approved in #15).
let session = null;

function signedIn() {
  return session !== null;
}

// The bottom navigation, which changes shape with the session. Study and
// Quiz became one Practice tab in the approved navigation: both are ways of
// practising, and the separate Ranked tab is what costs points.

const ICONS = {
  home: '<svg viewBox="0 0 24 24"><path d="M3 10.5 12 3l9 7.5V20a1.5 1.5 0 0 1-1.5 1.5H15V15H9v6.5H4.5A1.5 1.5 0 0 1 3 20z"/></svg>',
  practice: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.2"/></svg>',
  ranked: '<svg viewBox="0 0 24 24"><path d="M7 4h10v5a5 5 0 0 1-10 0z"/><path d="M7 6H4.5a2.5 2.5 0 0 0 2.6 3.6M17 6h2.5a2.5 2.5 0 0 1-2.6 3.6"/><path d="M12 14v4M8.5 20.5h7"/></svg>',
  profile: '<svg viewBox="0 0 24 24"><circle cx="12" cy="8" r="4.2"/><path d="M4.5 20.5a7.5 7.5 0 0 1 15 0"/></svg>',
  // Versus: two marks facing each other across a gap. A pair of crossed
  // lines was the first idea and reads as "close" at 19px.
  versus: '<svg viewBox="0 0 24 24"><path d="M3.5 6.5 9 12l-5.5 5.5"/><path d="M20.5 6.5 15 12l5.5 5.5"/><path d="M12 9.5v5"/></svg>',
  // A box on a belt, drawn on the same 24x24 grid and stroke as the rest of
  // the set so the dock reads as one family.
  handler: '<svg viewBox="0 0 24 24"><rect x="7" y="4.5" width="10" height="8" rx="1.5"/><path d="M12 4.5v8"/><path d="M3 17h18"/><circle cx="6.5" cy="19.5" r="1.8"/><circle cx="12" cy="19.5" r="1.8"/><circle cx="17.5" cy="19.5" r="1.8"/></svg>',
  // The two mini-games, and only them, are drawn in volume: isometric art
  // with its own light, not a line glyph. The box IS the Handler's game --
  // the thing you grab and send down a route -- and the lifted card over a
  // thinner one IS the quiz: many questions, and you are on this one. They
  // are used on each game's own entry point and nowhere else (see the CSS
  // note in index.html); the dock keeps the line glyphs above.
  handlerSolid: '<svg viewBox="0 0 48 48"><defs><linearGradient id="g-hb-t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffd978"/><stop offset="1" stop-color="#f4bd38"/></linearGradient><linearGradient id="g-hb-l" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#b8801c"/><stop offset="1" stop-color="#8d5d12"/></linearGradient><linearGradient id="g-hb-r" x1="1" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e0a52c"/><stop offset="1" stop-color="#a8761a"/></linearGradient></defs><ellipse cx="24" cy="42.5" rx="14" ry="3.2" fill="#000" opacity=".28"/><path d="M24 6 42 16 24 26 6 16Z" fill="url(#g-hb-t)"/><path d="M6 16 24 26v14L6 30Z" fill="url(#g-hb-l)"/><path d="M42 16 24 26v14l18-10Z" fill="url(#g-hb-r)"/><path d="M24 6 33 11l-18 10-9-5Z" fill="#fff" opacity=".28"/><path d="M33 30.5 42 25.5V21l-9 5Z" fill="#fff" opacity=".16"/><path d="M24 6 42 16" stroke="#fff" stroke-opacity=".45" stroke-width="1.1" fill="none"/><path d="M24 6 6 16" stroke="#fff" stroke-opacity=".3" stroke-width="1.1" fill="none"/></svg>',
  quizSolid: '<svg viewBox="0 0 48 48"><defs><linearGradient id="g-qc-t" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#ffe59a"/><stop offset="1" stop-color="#f1b62c"/></linearGradient></defs><ellipse cx="24" cy="44" rx="12" ry="2.6" fill="#000" opacity=".28"/><path d="M24 28 38 36 24 44 10 36Z" fill="#8d6013"/><path d="M10 36v-2.6l14 8V44Z" fill="#6a460c"/><path d="M38 36v-2.6l-14 8V44Z" fill="#a3700f"/><path d="M24 6 44 17 24 28 4 17Z" fill="url(#g-qc-t)"/><path d="M4 17v3.4l20 11V28Z" fill="#c88f20"/><path d="M44 17v3.4l-20 11V28Z" fill="#e0a52c"/><path d="M24 6 44 17" stroke="#fff" stroke-opacity=".55" stroke-width="1.1" fill="none"/><path d="M15 17.5 22 21.5 34 14" stroke="#4a2f05" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill="none"/></svg>',
  chart: '<svg viewBox="0 0 24 24"><rect x="3.5" y="4" width="17" height="16" rx="2.5"/><path d="M3.5 9.5h17M9.5 9.5V20M15 9.5V20"/></svg>',
  quiz: '<svg viewBox="0 0 24 24"><circle cx="12" cy="13" r="8"/><path d="M12 9v4l2.5 2M9.5 2.5h5"/></svg>',
  board: '<svg viewBox="0 0 24 24"><path d="M5 20V11M12 20V5M19 20v-6"/></svg>',
  history: '<svg viewBox="0 0 24 24"><path d="M4 12a8 8 0 1 0 2.6-5.9L4 8.5"/><path d="M4 4v4.5h4.5M12 8v4.5l3 1.8"/></svg>',
  // The header used to show system emoji -- a speaker that renders grey and
  // muddy next to the gold, and a moon every platform draws differently
  // (#326). These are drawn on the same 24x24 grid, with the same stroke, so
  // the header and the dock read as one set.
  soundOn: '<svg viewBox="0 0 24 24"><path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z"/><path d="M16 9a4.5 4.5 0 0 1 0 6M18.8 6.5a8 8 0 0 1 0 11"/></svg>',
  soundOff: '<svg viewBox="0 0 24 24"><path d="M4 9.5h3.5L12 5.5v13L7.5 14.5H4z"/><path d="m16.5 10 5 4M21.5 10l-5 4"/></svg>',
  night: '<svg viewBox="0 0 24 24"><path d="M20 14.5A8.5 8.5 0 0 1 9.5 4 8.5 8.5 0 1 0 20 14.5z"/></svg>',
  day: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="4.2"/><path d="M12 3v2.2M12 18.8V21M3 12h2.2M18.8 12H21M5.6 5.6l1.6 1.6M16.8 16.8l1.6 1.6M18.4 5.6l-1.6 1.6M7.2 16.8l-1.6 1.6"/></svg>',
  // The Settings rows used plain text characters -- a star, a question mark,
  // an arrow, a circle, two squares and an exclamation mark (#381). Every
  // phone draws those with whatever font it falls back to, so that list
  // looked different on every device while sitting beside these. Same grid,
  // same stroke, so Settings reads as part of the app.
  owner: '<svg viewBox="0 0 24 24"><path d="M12 3 4.5 6.2v5.4c0 4.3 3 8.3 7.5 9.4 4.5-1.1 7.5-5.1 7.5-9.4V6.2z"/><path d="m9 12 2.2 2.2L15.5 10"/></svg>',
  support: '<svg viewBox="0 0 24 24"><path d="M20.5 15.5a2 2 0 0 1-2 2H9l-4.5 3.5v-3.5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/><path d="M9.6 8.6a2.6 2.6 0 1 1 3.3 3.1c-.6.2-1 .8-1 1.5"/><path d="M11.9 16.1h.01"/></svg>',
  logOut: '<svg viewBox="0 0 24 24"><path d="M14.5 3.5H18A2.5 2.5 0 0 1 20.5 6v12a2.5 2.5 0 0 1-2.5 2.5h-3.5"/><path d="M9 16.5 3.5 12 9 7.5M3.5 12H15"/></svg>',
  avatar: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M8.5 14.2a4.5 4.5 0 0 0 7 0"/><path d="M9 9.5h.01M15 9.5h.01"/></svg>',
  devices: '<svg viewBox="0 0 24 24"><rect x="2.5" y="4.5" width="13" height="10" rx="2"/><path d="M6 18.5h6"/><rect x="16.5" y="9.5" width="5" height="10" rx="1.6"/></svg>',
  deleteAccount: '<svg viewBox="0 0 24 24"><path d="M4.5 6.5h15M9.5 6.5V4.8a1.3 1.3 0 0 1 1.3-1.3h2.4a1.3 1.3 0 0 1 1.3 1.3v1.7"/><path d="M6.5 6.5 7.6 20a1.5 1.5 0 0 0 1.5 1.4h5.8a1.5 1.5 0 0 0 1.5-1.4l1.1-13.5"/><path d="M10.5 10.5v7M13.5 10.5v7"/></svg>',
  // The last eight tiles still drawn from a text character (#404): six on
  // the owner menu, one on Support and one on the prize tie-break. Measured
  // on the owner menu at 375x812, the six glyphs were 7.5px, 9.6px, 9.6px,
  // 9.6px, 12.2px and 12.2px of ink inside identical 44px tiles -- a 63%
  // spread in one column, because Nunito has none of them and each device
  // falls back to a different font. Every drawn icon here is 19x19.
  prizeEligibility: '<svg viewBox="0 0 24 24"><rect x="4.5" y="4.5" width="15" height="16" rx="2"/><rect x="9" y="2.5" width="6" height="3.5" rx="1"/><path d="m8.6 13.4 2.4 2.4 4.6-5"/></svg>',
  accessRecovery: '<svg viewBox="0 0 24 24"><circle cx="8" cy="16" r="4.2"/><path d="m11 13 9-9M17.4 6.6 20 9.2M14.8 9.2l2.6 2.6"/></svg>',
  recoveryMessages: '<svg viewBox="0 0 24 24"><rect x="2.5" y="5" width="19" height="14" rx="2"/><path d="m3.2 6.8 8.8 6.4 8.8-6.4"/></svg>',
  caseReview: '<svg viewBox="0 0 24 24"><circle cx="10.5" cy="10.5" r="6.5"/><path d="m15.3 15.3 5.2 5.2"/></svg>',
  accounts: '<svg viewBox="0 0 24 24"><circle cx="9" cy="8" r="4.2"/><path d="M2.5 20.5a6.5 6.5 0 0 1 13 0"/><path d="M16.5 13.5h5"/></svg>',
  createTicket: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="8.5"/><path d="M12 8v8M8 12h8"/></svg>',
  // One icon for both sides of the same thing. "Prize selection -- ties the
  // rules send to you" is the owner's end of the tie-break the player sees
  // on Ranked, so they share a mark rather than each getting one. A cap was
  // drawn for the owner row first and read as a blob at 19px, which is what
  // sent me back to asking what the row actually does.
  tiebreak: '<svg viewBox="0 0 24 24"><path d="M6 21.5V3"/><path d="M6 4.5h10.8l-2.1 3.6 2.1 3.6H6"/></svg>',
  // Not a tile, so outside the letter of #404, but the same defect and the
  // one the player sees most: the Settings chip's gear is a U+2699 that
  // Nunito does not have, 8.4px of ink in the sub-header of every screen.
  // Sliders rather than a gear, because a gear at this size is a ring with
  // short rays -- which is the day-theme icon sitting two chips away.
  settings: '<svg viewBox="0 0 24 24"><path d="M4 7h16M4 17h16"/><circle cx="9" cy="7" r="2.4"/><circle cx="15" cy="17" r="2.4"/></svg>',
  // #440: the two marks that are not tiles. These are badges, not list
  // icons: each replaces a font-weight 900 glyph, so they carry a 2.4
  // stroke where the tiles carry 2, and they size in `em` so the three
  // contexts that already declare a font-size keep deciding how big the
  // mark is.
  verdictGood: '<svg viewBox="0 0 24 24"><path d="m5 12.6 4.9 4.9L19 7"/></svg>',
  verdictBad: '<svg viewBox="0 0 24 24"><path d="M6.6 6.6 17.4 17.4M17.4 6.6 6.6 17.4"/></svg>',
  // A crown, although the prize is a hat and the app says so everywhere.
  // A cap was drawn seven ways across two rounds and tested at 26px and
  // 32px against the real podium: a cap in outline is a dome with a brim,
  // and at these sizes it reads as a bowl or a serving cloche every time.
  // The crown reads instantly, and it is what the glyph already meant.
  prizeHolder: '<svg viewBox="0 0 24 24"><path d="M3.5 18.5h17M4 8l4 3.5L12 5l4 6.5L20 8l-1.5 8h-13z"/></svg>',
};

function navTabs() {
  const tabs = [
    ['home', ICONS.home, t('Home')],
    ['practice', ICONS.practice, t('Practice')],
    // Handler sits with Practice because it is practice: a guest can play
    // it, and nothing about it is gated behind signing in. Only the stored
    // best score needs an account (#396).
    ['handler', ICONS.handler, t('Handler')],
  ];
  if (signedIn()) {
    tabs.push(['ranked', ICONS.ranked, t('Ranked')]);
    // Versus needs two named accounts, so it is a signed-in tab like Ranked.
    tabs.push(['versus', ICONS.versus, t('Versus')]);
    tabs.push(['profile', ICONS.profile, t('Profile')]);
  }
  return tabs;
}

function labPage(content, active = 'home', rerender = showStart) {
  // #427: while a scored attempt is live the dock is not drawn at all. Not
  // hidden: never built, so it is not in the tab order or the screen reader
  // either, and no CSS has to beat `.lab-nav { display: grid !important }`.
  // The marker is read from the content the screen asked for, so the fact
  // lives in one place -- the screen's own markup.
  const attemptLive = content.includes('data-attempt-live');
  const view = el(`
    <div class="lab-shell">
      <header class="lab-top">
        <div class="lab-top-row">
          <div class="lab-brand"><span class="lab-mark">RJ</span> <span class="lab-wordmark">Sort Quiz</span></div>
          <div class="lab-top-actions">${languageButtons()}${soundButton()}${themeButton()}</div>
        </div>
        ${active === 'profile' ? `
        <div class="lab-site-row">
          <div class="lab-site">UPS Saddle Brook <span aria-hidden="true">·</span> Twilight</div>
          <button type="button" class="lab-settings-btn" id="top-settings"><span class="lab-btn-ic" aria-hidden="true">${ICONS.settings}</span> ${esc(t('Settings'))}</button>
        </div>` : ''}
      </header>
      <main class="lab-main">${content}</main>
      ${attemptLive ? '' : `<nav class="lab-nav${navTabs().length > 4 ? ' lab-nav-tight' : ''}" style="grid-template-columns: repeat(${navTabs().length}, 1fr)" aria-label="${esc(t('Main navigation'))}">
        ${navTabs().map(([id, icon, label]) => `
        <button type="button" data-nav="${id}" ${active === id ? 'aria-current="page"' : ''}><i aria-hidden="true">${icon}</i>${esc(label)}</button>`).join('')}
      </nav>`}
    </div>
  `);
  render(view);
  wireLanguageButtons(view, rerender);
  wireThemeButton(view);
  wireSoundButton(view);
  view.querySelector('#top-settings')?.addEventListener('click', () => showProfile('settings'));
  view.querySelectorAll('[data-nav]').forEach((button) => button.addEventListener('click', () => {
    // The active tab is not skipped: a screen inside a tab (a tie-break
    // invite, the leaderboard) carries its tab's mark, and pressing the tab
    // is how a player expects to get back to its first screen.
    if (button.dataset.nav === 'practice') showPractice();
    else if (button.dataset.nav === 'handler') showHandler();
    else if (button.dataset.nav === 'ranked') showRanked();
    else if (button.dataset.nav === 'versus') showVersus();
    else if (button.dataset.nav === 'profile') showProfile();
    else showStart();
  }));
  return view;
}

function stopTick() {
  if (frame !== null) cancelAnimationFrame(frame);
  frame = null;
}

function beltChip(belt, className) {
  const style = BELT_STYLE[belt];
  return `<div class="${className}" data-belt="${esc(belt)}" style="background:${style.bg};color:${style.fg}">${belt}</div>`;
}

// Practice: the two ways of practising, together under one tab. Neither
// changes Ranked points, and the screen says so.
// Handler, the conveyor mini-game (#396). The page is a mount point and
// nothing else: the game's screens, input, canvas and sound all live in
// src/conveyor/, and this file only puts them on screen and takes them off.
// The dock, while a Handler round is running. It is put back on the same
// parent it came off, in the place it had: the shell's last child.
function holdHandlerDock(view, live) {
  const shell = view.querySelector('.lab-shell') ?? view;
  if (live) {
    handlerDock = shell.querySelector('.lab-nav') ?? handlerDock;
    handlerDock?.remove();
  } else if (handlerDock && !shell.querySelector('.lab-nav')) {
    shell.append(handlerDock);
  }
  view.classList?.toggle('hd-live', live);
  app.classList.toggle('hd-live', live);
}
let handlerDock = null;

function showHandler() {
  stopTick();
  clock = null;
  handlerDock = null;
  const best = createBestScores();
  const view = labPage(`
    <section class="lab-screen screen-handler">
      <div data-handler-root></div>
    </section>
  `, 'handler', showHandler);
  const root = view.querySelector('[data-handler-root]');
  unmountHandler();
  handlerScreen = createHandlerScreen({
    root,
    t: (source, values) => t(source, values),
    engine: conveyorEngine,
    routes: conveyorRoutes,
    audio: createHandlerAudio({ getContext: getAudioContext, isEnabled: isSoundEnabled }),
    soundPref: { isEnabled: isSoundEnabled, toggle: toggleSound },
    bestScores: best,
    board: createHandlerBoard(),
    avatarOf: avatarEmoji,
    // The dock goes while the minute runs, the way it does under a Ranked
    // attempt and a Versus duel: a dock under a timed round is a way to
    // lose it with a thumb. The Handler mounts after the page shell is
    // built, so it cannot carry the shell's own marker -- it says when a
    // round is live and the dock is taken out and put back here. Any way
    // OUT of the Handler redraws the whole page, which restores it anyway.
    onRound: (live) => holdHandlerDock(view, live),
  });
  // The stored bests arrive after the first paint, so the mode list is
  // redrawn once they do. A guest's load() answers 401 and the screen says
  // the score is not saved rather than showing a silent zero.
  best.load().then(() => {
    if (handlerScreen) handlerScreen.showModes();
  });
  return view;
}

// Versus, the 1 vs 1 frame over the two mini-games. Its screens live in
// src/versus/; this file hands them the page shell and the pieces the quiz
// and the Handler already own, and mounts the Handler for a handler duel.
let versusScreens = null;
function versus() {
  if (!versusScreens) {
    versusScreens = createVersusScreens({
      labPage, t, esc, ICONS, language, avatarEmoji,
      client: createVersusClient(),
      beltButton, destinationLine, rqChip, backLink,
      playCorrectSfx, playIncorrectSfx,
      mountHandlerDuel,
    });
  }
  return versusScreens;
}

function showVersus() {
  stopTick();
  clock = null;
  return versus().showVersus();
}

// A handler duel is the Handler's own screen, started straight into one
// round of the duel's mode and dealt from the match's seed, so both players
// sort the same packages. It is held in `handlerScreen` like any other
// Handler mount, which is what makes render() take it down on the way out.
function mountHandlerDuel(root, { seed, onScore, onEnd }) {
  unmountHandler();
  handlerScreen = createHandlerScreen({
    root,
    t: (source, values) => t(source, values),
    engine: conveyorEngine,
    routes: conveyorRoutes,
    audio: createHandlerAudio({ getContext: getAudioContext, isEnabled: isSoundEnabled }),
    soundPref: { isEnabled: isSoundEnabled, toggle: toggleSound },
    random: seededRandom(seed),
    duel: { mode: HANDLER_DUEL_MODE, onScore, onEnd },
  });
  return handlerScreen;
}

// The name a player gave for the Shift log, kept for as long as the page is
// open. It used to be asked for on a screen of its own before every list of
// tests; now it is offered from the list, and remembered between tests.
let practiceName = '';

// The Practice tab is the list of tests. It was a screen with two buttons,
// then a screen for an optional name, then the list: three taps to reach
// what the tab is for.
function showPractice() {
  showDeckPicker(practiceName);
}

// Ranked and Profile exist as tabs for signed-in players from this slice on;
// their screens are the next slices of #10. A placeholder that says so is
// better than a tab that does nothing when pressed.
function comingSoon(eyebrow, title, note, active, back = null) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(eyebrow)}</p>
      <h1 class="lab-title">${esc(title)}</h1>
      <p class="lab-intro">${esc(note)}</p>
      ${back ? `<button id="soon-back" class="ghost" type="button">${esc(t(back.label))}</button>` : ''}
    </section>
  `, active, () => comingSoon(eyebrow, title, note, active, back));
  if (back) view.querySelector('#soon-back').addEventListener('click', back.go);
}

// Profile (#10, slice 2). Everything here is the signed-in account's own:
// the server returns no other account's, and asks for none.
const BADGES = [
  ['Challenger', '4,001 and up, no cap'],
  ['Gold', '3,001\u20134,000'],
  ['Silver', '2,001\u20133,000'],
  ['Bronze', '1,001\u20132,000'],
  ['Iron', 'Through 1,000'],
];
const BADGE_CAP = { Iron: 1000, Bronze: 2000, Silver: 3000, Gold: 4000 };

// Lowest first, which is the order the climb row is drawn in and the order
// "earned / current / still ahead" is decided by. BADGES itself is highest
// first because it is printed as a table.
//
// Derived from BADGES rather than written out again: this list and the
// quiz screen's used to be two separate hand-written copies of the same
// five names, 1,600 lines apart, and only one of them could be kept right.
const BADGE_ORDER = [...BADGES].map(([name]) => name).reverse();

// The badge above this one, or null at the top.
function nextBadgeName(badge) {
  const at = BADGE_ORDER.indexOf(badge);
  return at === -1 ? null : (BADGE_ORDER[at + 1] ?? null);
}

// A screen that calls this shows its own "could not load" notice when the
// answer is null. An unreachable server (stopped, no network, a phone that
// lost signal mid-sort) throws instead of answering, so without this catch
// the promise rejected and the screen sat on "Loading..." for ever.
//
// The balance and the season are read by Home, Ranked and Profile alike, so
// moving between those screens asked the same question again each time and
// sat on "Loading..." for the answer. These two reads are kept for a few
// seconds and shared while in flight. Nothing here is trusted for play: the
// server decides every attempt, and anything that can change the answer
// (a write, an attempt request, a change of session) empties the cache.
const CACHED_READS = new Set(['/ranked/entry', '/ranked/season', '/ranked/profile/stats']);
const CACHED_READ_MS = 15000;
const readCache = new Map();

function clearReadCache() {
  readCache.clear();
}

async function api(path) {
  if (!CACHED_READS.has(path)) return apiRead(path);
  const kept = readCache.get(path);
  if (kept && Date.now() - kept.at < CACHED_READ_MS) return kept.answer;
  const record = { at: Date.now(), answer: apiRead(path) };
  readCache.set(path, record);
  const body = await record.answer;
  // A failure is never kept: the next screen should ask again.
  if (body === null && readCache.get(path) === record) readCache.delete(path);
  return body;
}

async function apiRead(path) {
  let response;
  try {
    response = await fetch(`/api${path}`, { credentials: 'same-origin' });
  } catch {
    return null;
  }
  // The server ended this session. Every screen would otherwise show
  // "could not load" as if the server were broken, so the player is sent to
  // the entry screen instead. No reason is named: a 401 can be the idle
  // window, the eight-hour limit, or the player ending this device from
  // another one (#270), and nothing here can tell which. The app's own idle
  // timer does know, and says so in checkIdle.
  if (response.status === 401 && signedIn()) {
    signOut(t('Your session ended. Log in to carry on.'));
    return null;
  }
  if (!response.ok) return null;
  try {
    return await response.json();
  } catch {
    return null;
  }
}

// The writing half of `api`. A refusal carries the server's reason, which
// is written for the person reading it; `ok` is false for a dead server
// too, so a caller never has to tell the two apart before showing
// something.
async function apiSend(method, path, body) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body !== undefined) options.body = JSON.stringify(body);
  let response;
  // Emptied before and after: a read that started while the write was on
  // its way may hold the old answer.
  clearReadCache();
  try {
    response = await fetch(`/api${path}`, options);
  } catch {
    return { ok: false, status: 0, data: null, reason: t('Could not reach the server. Nothing has been changed.') };
  } finally {
    clearReadCache();
  }
  if (response.status === 204) return { ok: true, status: 204, data: null };
  let data = null;
  try {
    data = await response.json();
  } catch {
    data = null;
  }
  return {
    ok: response.ok,
    status: response.status,
    data,
    reason: typeof data?.detail === 'string' ? data.detail : null,
  };
}

// Recent reauthentication (#11 box 5). The server answers 428 when an
// owner action needs the login ID re-entered on this device; the page asks
// for it, confirms it, and repeats the action once. One entry covers five
// minutes of work, so a run of approvals asks once, not once per click.
//
// The field is a password field on purpose: the owner does this standing
// in front of a sorter, and the login ID should not be readable over their
// shoulder. It also lets a password manager fill it in.
function askForLoginId(reason) {
  return new Promise((resolve) => {
    const dialog = document.createElement('div');
    dialog.className = 'reauth-dialog';
    dialog.setAttribute('role', 'dialog');
    dialog.setAttribute('aria-modal', 'true');
    dialog.setAttribute('aria-labelledby', 'reauth-title');
    dialog.innerHTML = `
      <form class="reauth-card">
        <h2 id="reauth-title">${esc(t('Confirm it is you'))}</h2>
        <p class="lab-study-meta">${esc(reason || t('Re-enter your Quiz Code to continue. It stays confirmed on this device for five minutes.'))}</p>
        <label class="field"><span>${esc(t('Your Quiz Code'))}</span>
          <input id="reauth-input" type="password" autocomplete="current-password" spellcheck="false" placeholder="banana-48"></label>
        <p class="notice" id="reauth-error" role="status" hidden></p>
        <button class="primary" type="submit">${esc(t('Confirm'))}</button>
        <button class="ghost" type="button" id="reauth-cancel">${esc(t('Cancel'))}</button>
      </form>`;
    const close = (value) => { dialog.remove(); resolve(value); };
    dialog.querySelector('#reauth-cancel').addEventListener('click', () => close(null));
    dialog.querySelector('form').addEventListener('submit', async (event) => {
      event.preventDefault();
      const input = dialog.querySelector('#reauth-input');
      const result = await apiSend('POST', '/auth/reauthenticate', { login_id: input.value });
      input.value = '';
      if (result.ok) { close(true); return; }
      const error = dialog.querySelector('#reauth-error');
      error.hidden = false;
      error.textContent = result.status === 429
        ? t('Too many attempts. Wait a moment and try again.')
        : (result.reason || t('That did not work. Nothing has been changed.'));
      input.focus();
    });
    document.body.append(dialog);
    dialog.querySelector('#reauth-input').focus();
  });
}

// apiSend for the owner's guarded actions: asks for the login ID when the
// server wants it, then tries the action exactly once more.
async function apiSendOwner(method, path, body) {
  const first = await apiSend(method, path, body);
  if (first.status !== 428) return first;
  const confirmed = await askForLoginId(first.reason);
  if (!confirmed) {
    return { ok: false, status: 428, data: null, reason: t('Cancelled. Nothing has been changed.') };
  }
  return apiSend(method, path, body);
}

function badgeArt(badge) {
  return `assets/badge-${badge.toLowerCase()}.png`;
}

// The five badges under "Your climb".
//
// The row used to mark the current badge by dimming the other four, and
// nothing else. That is a subtractive mark, and it fails exactly where it is
// needed: the Iron and Silver artwork is grey metal to begin with, so a
// full-colour Iron beside four greyed badges looks like five greyed badges.
// Measured on a new account: the current badge really was at opacity 1 with
// no filter -- the markup was right, it just could not be seen.
//
// So the current badge now carries a positive mark of its own, a gold ring,
// and the three states are told apart properly: badges already passed keep
// their colour (they were earned), the current one is ringed, and only the
// ones still ahead are dimmed.
function badgeTrail(current) {
  const at = BADGE_ORDER.indexOf(current);
  return BADGE_ORDER.map((name, i) => {
    const state = i === at ? 'now' : i < at ? 'done' : 'off';
    // The ring is the sighted mark; a screen reader gets the same fact in
    // the alt text, since an outline is not announced.
    const mark = i === at ? ` (${t('Your badge')})` : '';
    return `<img class="${state}" src="${badgeArt(name)}" alt="${esc(name + mark)}">`;
  }).join('');
}

function balanceLine(entry) {
  const cap = BADGE_CAP[entry.badge];
  if (cap === undefined) return `${entry.badge} \u00b7 ${t('no cap')}`;
  if (entry.points >= cap) return `${entry.badge} \u00b7 ${t('at the cap')} (${language.number(cap)})`;
  if (entry.points < 0) return `${entry.badge} \u00b7 ${t('a negative total stays in Iron')}`;
  // It used to read "Iron - 1,000 points to the cap (1,000)": the number said
  // twice, and nothing about where the climb goes. A player at zero could not
  // tell that from a player one point short. Progress over the target reads
  // at a glance, and the badge above is the thing the points are actually
  // for, so it is named: "Iron - 0 / 1,000 to Bronze".
  const next = nextBadgeName(entry.badge);
  const progress = `${language.number(entry.points)} / ${language.number(cap)}`;
  if (next === null) return `${entry.badge} \u00b7 ${progress}`;
  return `${entry.badge} \u00b7 ${progress} ${t('to')} ${next}`;
}

// The player's own screens -- profile, support, avatar, Quiz Code, deleting
// the account, Settings -- live in src/profileScreens.js. The signed-in
// account stays here; they read it and, on a deletion, drop it.
let profileScreens = null;
function showProfile(tab) {
  if (!profileScreens) {
    profileScreens = createProfileScreens({
      labPage, t, esc, ICONS, language, backLink, log,
      api, apiSend, apiSendOwner,
      account: () => session,
      forgetAccount: () => { session = null; clearReadCache(); },
      stopQuizClock: () => { stopTick(); clock = null; },
      logout, signOut, showOwnerTools,
      badgeArt, badgeProgress, badgeTrail, balanceLine, fillLaunchCallout,
    });
  }
  return profileScreens.showProfile(tab);
}

// The owner's screens live in src/ownerScreens.js; this file hands them the
// page shell and the ways to reach the server, and keeps the one way in.
let ownerScreens = null;
function showOwnerTools() {
  if (!ownerScreens) {
    ownerScreens = createOwnerScreens({
      labPage, t, esc, ICONS, language, backLink,
      api, apiSend, apiSendOwner, clearReadCache,
      stopQuizClock: () => { stopTick(); clock = null; },
      showSettings: () => showProfile('settings'),
    });
  }
  return ownerScreens.showOwnerTools();
}

// The tie-break invite: what the round is, before anything starts.
function showTiebreakInvite(tie) {
  stopTick();
  clock = null;
  const round = tie.round;
  const closes = language.dateTime(round.deadline_at);
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Prize tie-break'))} · ${esc(t('round'))} ${round.number}</p>
      <h1 class="lab-title">${esc(t('You are tied for a hat'))}</h1>
      <p class="lab-intro">${esc(t('You have the same points as another sorter. A separate quiz decides who takes the hat.'))}</p>
      ${tie.last_result ? `<p class="lab-intro" id="tb-last"><strong>${esc(lastRoundLine(tie.last_result, true))}</strong></p>` : ''}
      ${round.restarted ? `<div class="board-notice" id="tb-restarted"><h2>${esc(t('This round was restarted'))}</h2>
        <p>${esc(t('A server outage interrupted it, so the round starts again for everyone with new questions and a new deadline. Answers given before do not count, even a finished attempt. Play it again to stay in the tie-break.'))}</p></div>` : ''}
      <ol class="lab-rules">
        <li>${esc(t('Five Hard route questions, the same five for everyone in this round.'))}</li>
        <li>${esc(round.seconds)} ${esc(t('seconds each. Questions move on by themselves — there is no Next.'))}</li>
        <li>${esc(t('Play once, at any time before the round closes.'))}</li>
        <li>${esc(t('Nothing is shown until the round closes, for anyone.'))}</li>
      </ol>
      <div class="board-notice"><h2>${esc(t('This changes no points and no badge'))}</h2>
        <p>${esc(t('It decides the hat only. Your season points, your badge and your history stay exactly as they are, whatever happens here.'))}</p></div>
      <p class="lab-intro">${esc(t('Round closes'))}: ${esc(closes)}. ${esc(t('Nothing has started yet.'))}</p>
      <button id="tb-start" class="primary">${esc(t('Start round'))}</button>
      <button id="tb-not-yet" class="ghost">${esc(t('Not yet'))}</button>
    </section>
  `, 'ranked', () => showTiebreakInvite(tie));
  view.querySelector('#tb-not-yet').addEventListener('click', showRanked);
  view.querySelector('#tb-start').addEventListener('click', () => playTiebreak(round));
  return view;
}

// Playing the round. The server owns the clock and which question is live;
// this drives the exchange and shows a countdown to the server's deadline.
async function playTiebreak(round) {
  stopTick();
  clock = null;
  const attempt = createAttemptClient({ fetchFn: attemptFetch });
  const started = await attempt.start(`/ranked/tiebreak/rounds/${round.id}/attempts`);
  if (!started.ok) {
    showRanked();
    return;
  }
  attempt.startHeartbeat();
  holdLiveAttempt(attempt);
  const view = labPage(`
    <section class="lab-screen" id="tb-play" data-attempt-live>
      <div class="tb-top">
        <span class="lab-eyebrow" id="tb-count"></span>
        <span class="lab-eyebrow" id="tb-time"></span>
      </div>
      <div class="tb-bar"><i id="tb-bar-fill"></i></div>
      <div id="tb-question"></div>
    </section>
  `, 'ranked', () => showRanked());
  let timer = null;
  const stopTimer = () => { if (timer) clearInterval(timer); timer = null; };

  async function render() {
    const current = await attempt.current();
    if (current.status === 410 || current.status === 204 || !current.data) {
      stopTimer();
      attempt.stop();
      // The attempt ending is not proof it was submitted: a confirmed
      // outage voids the round and opens it again. Ask before telling the
      // player nothing else is needed, because that would cost them the hat.
      const again = (await api('/ranked/tiebreak/mine'))?.tie;
      if (again?.round && !again.round.played) showTiebreakInvite(again);
      else showTiebreakSubmitted(round);
      return;
    }
    const q = current.data;
    view.querySelector('#tb-count').textContent =
      `${t('Question')} ${q.seq} ${t('of')} 5 · ${t('round')} ${round.number}`;
    const where = destinationLine(q, t('Hard'));
    view.querySelector('#tb-question').innerHTML = `
      ${/* #435: the same card the Ranked question has. These two prompts were
            built from one shape and only the Ranked one kept the surface, so
            the screen with five seconds a question, played once, with a hat
            on it, was the one where the route had nothing to sit on. No
            stake pill here: the Ranked card's pill says what the attempt is
            worth, and this screen says that in its eyebrow instead. */ ''}
      <div class="rq-prompt rq-route home-spot">
        <p class="rq-service">${esc(where.service)}</p>
        <p class="rq-code">${esc(where.code)}</p>
      </div>
      <p class="lab-eyebrow rq-cue">${esc(t('Where does this go?'))}</p>
      <div class="belts" role="group" aria-label="${esc(t('Choose a belt'))}">
        ${(q.options || []).map((belt) => beltButton(belt)).join('')}
      </div>
      ${/* #437: a sentence, so the app's prose style rather than the label
            style it wore -- 12 words in 11px uppercase, on a screen with
            five seconds to read anything. */ ''}
      <p class="lab-intro">${esc(t('No feedback: whether you were right stays hidden until the round closes.'))}</p>
    `;
    view.querySelectorAll('.belt').forEach((button) => button.addEventListener('click', async () => {
      view.querySelectorAll('.belt').forEach((b) => { b.disabled = true; });
      stopTimer();
      await attempt.answer(q.seq, button.dataset.belt);
      render();
    }));
    startCountdown(new Date(q.deadline_at).getTime());
  }

  function startCountdown(deadlineMs) {
    stopTimer();
    const total = round.seconds * 1000;
    const paint = () => {
      const left = deadlineMs - Date.now();
      const secondsLeft = Math.max(0, Math.ceil(left / 1000));
      view.querySelector('#tb-time').textContent =
        `${secondsLeft} ${t(secondsLeft === 1 ? 'second' : 'seconds')}`;
      const fill = view.querySelector('#tb-bar-fill');
      setBarFill(fill, (left / total) * 100);
      if (left <= 0) { stopTimer(); render(); }
    };
    paint();
    timer = setInterval(paint, 200);
  }

  render();
  return view;
}

function showTiebreakSubmitted(round) {
  stopTick();
  const view = labPage(`
    <section class="lab-screen">
      ${/* #400: an informational terminus you are sent to, like the
            leaderboard (#385) -- nothing on it is an action, so the way out
            is the compact Back, not a full-width button. The five other
            "Back to Ranked" buttons in the app are a different case: on a
            result screen that button IS the way forward. */ ''}
      ${backLink('tb-back')}
      <p class="lab-eyebrow">${esc(t('Prize tie-break'))} · ${esc(t('round'))} ${round.number}</p>
      <h1 class="lab-title">${esc(t('Attempt submitted'))}</h1>
      <p class="lab-intro">${esc(t('All five are in. Nothing else is needed from you.'))}</p>
      <div class="board-notice"><h2>${esc(t('Why you see nothing yet'))}</h2>
        <p>${esc(t('Everyone in this round answers the same five questions, at different times. Showing a score now would tell a later player what to expect. Scores stay hidden for everyone until the round closes.'))}</p></div>
    </section>
  `, 'ranked', () => showTiebreakSubmitted(round));
  view.querySelector('#tb-back').addEventListener('click', showRanked);
  return view;
}

// Shared by every question screen: tie-break (always Hard, so it passes
// a tag), ordinary Ranked and promotion (no tag, matching the approved
// mock, which never names the difficulty while a question is live).
function destinationLine(q, tag) {
  const service = [SERVICE_LABEL[q.service] || q.service, q.mode && q.mode !== 'base' ? q.mode : '', q.region_label]
    .filter(Boolean).join(' · ');
  const code = q.named_destination || q.routing_code || '';
  return { service: tag ? `${service} · ${tag}` : service, code };
}

function beltButton(belt) {
  const style = BELT_STYLE[belt] || { bg: '#333', fg: '#fff' };
  return `<button type="button" class="belt" data-belt="${esc(belt)}" style="background:${style.bg};color:${style.fg}">${esc(belt)}<span class="belt-key" aria-hidden="true"></span></button>`;
}

// The leaderboard (#12, slice 2), built to the screen approved in #16.
//
// No timestamps anywhere: the first-reached-score rule was superseded by
// tie-break quizzes, and showing a time here would revive it. Tied players
// share a place number, because which of them is ahead is a question only a
// tie-break quiz answers.
function showLeaderboard() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      ${backLink('board-back')}
      <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
      <h1 class="lab-title tab-title">${esc(t('Leaderboard'))}</h1>
      <div id="board-panel"><p class="lab-intro" role="status">${esc(t('Loading the standings…'))}</p></div>
    </section>
  `, 'ranked', showLeaderboard);
  view.querySelector('#board-back').addEventListener('click', showRanked);
  fillLeaderboard(view.querySelector('#board-panel'));
  return view;
}

function boardNotice(title, text) {
  return `<div class="board-notice"><h2>${esc(title)}</h2><p>${esc(text)}</p></div>`;
}

async function fillLeaderboard(panel) {
  const board = await api('/ranked/leaderboard');
  if (!board) {
    panel.innerHTML = boardNotice(
      t('Could not load the standings'),
      t('Your points are safe. Try again in a moment.'),
    );
    return;
  }
  // Pre-Season has a board of its own (#247): everyone with one completed
  // Ranked quiz, no approval. It wins no prize and the launch resets it, and
  // the screen says so every time, even when the board is still empty.
  const preSeason = board.phase === 'pre_season';
  const preSeasonLine = preSeason
    ? `<p class="lab-intro"><strong>${esc(t('Pre-Season'))}.</strong> ${esc(t('These standings win no prize. Everyone goes back to 0 points and Iron when the official season starts.'))}</p>`
    : '';
  if (board.rows.length === 0) {
    panel.innerHTML = preSeasonLine + boardNotice(
      t('No standings yet'),
      board.season_label
        ? t('Nobody has completed a Ranked quiz in this season yet, so there is nothing to rank.')
        : (preSeason
          ? t('Nobody has completed a Ranked quiz in Pre-Season yet, so there is nothing to rank.')
          : t('The official season has not started, so there is nothing to rank yet.')),
    );
    return;
  }
  // Top three get a 3D-style podium (mock); the rest stay in the list below.
  // Each pedestal carries the player's real place: with equal points the
  // standings share a place, and a fixed 1-2-3 would rank a tie that the
  // rules have not ranked.
  // Once the hats are decided the podium is the three winners: a tie-break
  // or a backfill can give a hat to a player listed below one who took none.
  const ordered = board.prizes_final
    ? [...board.rows.filter((row) => row.hat), ...board.rows.filter((row) => !row.hat)]
    : board.rows;
  const hasPodium = ordered.length >= 3;
  const top = ordered.slice(0, 3);
  // #443: the hat winner used to be marked three times at once -- a crown
  // above the disc, the SAME crown inside it, and the gold ring the leader
  // already has. The two crowns sat 20px apart, identical, and read as a
  // fault rather than as emphasis.
  //
  // The one that cost something was the disc. It is the identity element:
  // everyone else shows their avatar at 36px or their initial at 20px, and
  // the winner -- the one person you look for -- showed a 10.8px crown
  // instead of a face. The crown now sits above the disc and nowhere else,
  // and the disc does its job for every player alike.
  const slot = (row, cls) => !row ? '' : `
    <div class="pslot ${cls}${row.you ? ' pslot-you' : ''}">
      ${row.hat ? `<div class="pcrown" aria-hidden="true">${ICONS.prizeHolder}</div>` : ''}
      <div class="pdisc${avatarEmoji(row.avatar) ? ' has-avatar' : ''}">${avatarEmoji(row.avatar) || esc(row.username.slice(0, 1).toUpperCase())}</div>
      <div class="pname">${esc(row.username)}</div>
      <div class="ppts">${language.number(row.points)}</div>
      <div class="ppillar">${row.place}</div>
    </div>`;
  const podium = hasPodium ? `<div class="podium">
    ${slot(top[1], 'p2')}${slot(top[0], 'p1')}${slot(top[2], 'p3')}
  </div>` : '';
  const listRows = hasPodium ? ordered.slice(3) : ordered;
  // #444: the podium's points used to carry a U+25C6 that Nunito does not
  // have -- 7.6px of ink from whatever font the device fell back to, beside
  // a digit of 6.3px from the real one. It was the last text glyph doing an
  // icon's job, after #404 and #440.
  //
  // Dropped rather than drawn, because the list two rows below already
  // shows the same quantity with no mark at all: one screen was showing
  // points two ways. Removing it settles that AND the glyph, where drawing
  // it would have settled the glyph and added a filled icon -- the only one
  // in a set that is otherwise all strokes -- to keep the inconsistency.
  //
  // The same swap happened below the podium, where the crown replaced the
  // player's PLACE -- the one number the column exists for -- on a row that
  // already says "Hat winner" in words and is drawn in gold. The words and
  // the gold stay; the place comes back.
  const rows = listRows.map((row) => `
    <li class="${row.you ? 'board-you' : ''}${row.hat ? ' board-hat' : (row.tied ? ' board-tied' : '')}">
      <span class="board-place">${row.place}</span>
      <span class="board-who">
        <b>${avatarEmoji(row.avatar) ? `<span class="board-avatar" aria-hidden="true">${avatarEmoji(row.avatar)}</span>` : ''}${esc(row.username)}</b>
        <small>#${esc(row.tag)} · ${esc(row.badge)}${row.you ? ` · ${esc(t('your place'))}` : ''}${
          /* The marker rides on the tag line. It was a line of its own under
             the row, in a brown that only the day theme could read. */
          row.hat ? ` <span class="board-marker board-marker-hat">${esc(t('Hat winner'))}</span>`
            : (row.tied ? ` <span class="board-marker">${esc(t(board.prizes_final ? 'Tied on points, no hat' : 'Tied on points'))}</span>` : '')}</small>
      </span>
      <b class="board-points">${language.number(row.points)}</b>
    </li>
  `).join('');
  const intro = board.prizes_final
    ? t('Final results. The three hats are decided.')
    : (board.points_final
      ? t('Points are final for this season. Prize places stay provisional until any tie-break quizzes are played.')
      : t('Standings update after each settled Ranked quiz, not once a day.'));
  // The server sends a bounded number of rows. A player ranked past that
  // cut is eligible and has a place, but no line of their own in the list,
  // so the place is said in words rather than left for them to look for.
  const youInList = board.rows.some((row) => row.you);
  const placeLine = (!youInList && board.your_place)
    ? `<p class="board-your-place">${esc(t('Your place'))}: <b>${board.your_place}</b>${
        esc(t(' — beyond the rows shown above.'))}</p>`
    : '';
  // In Pre-Season nobody needs approval, so a player who is missing has
  // simply not completed a quiz yet. The approval sentence would be wrong.
  const notInStandings = preSeason
    ? boardNotice(
      t('You are not in the standings yet'),
      t('Complete one Ranked quiz and you will appear here. Pre-Season needs no approval.'),
    )
    : boardNotice(
      t('You are not in the standings'),
      t('Your points and badge count as usual and are on your profile. The competition is for Primary Sort on the Twilight shift, approved by the owner. Ask the owner if that should be you.'),
    );
  // The podium and the list each get a stripe. The player's place rides on the
  // first stripe shown, so it is in view without looking for their own row.
  // The player's place leads the screen, in a card of its own: it was a
  // 10px chip beside an eyebrow. Their points and the gap to the next
  // player up are added when their own row is among the rows the server
  // sent; a player ranked past that cut gets the place alone.
  // Only a player with strictly more points counts as the next one up: two
  // players tied on points are not ranked against each other here either.
  const mine = board.rows.find((row) => row.you);
  const nextUp = mine ? board.rows.reduce((best, row) => (
    row.points > mine.points && (!best || row.points < best.points) ? row : best), null) : null;
  const behind = nextUp
    ? t('{n} behind #{place}', { n: language.number(nextUp.points - mine.points), place: nextUp.place })
    : '';
  const placeCard = board.your_place ? `
    <div class="board-mine" id="board-mine">
      <div>
        <p class="lab-study-meta">${esc(t('Your place'))}</p>
        <p class="board-mine-place">#${esc(board.your_place)}</p>
      </div>
      ${mine ? `<div class="board-mine-pts">
        <b>${language.number(mine.points)} ${esc(t('points'))}</b>
        ${behind ? `<small>${esc(behind)}</small>` : ''}
      </div>` : ''}
    </div>` : '';
  const podiumStripe = podium ? `
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Top 3'))}</p>
      <div class="podium-card">${podium}</div>
    </section>` : '';
  const listStripe = rows ? `
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Standings'))}</p>
      <ol class="board">${rows}</ol>
    </section>` : '';
  // The wrapper is `display: contents` until the desktop breakpoint, so on a
  // phone it changes nothing at all; above it the podium and the standings
  // sit side by side (#273).
  panel.innerHTML = `
    ${preSeasonLine}
    ${placeCard}
    <div class="board-split${rows ? ' board-split-two' : ''}">
      <div class="board-split-podium">${podiumStripe}</div>
      <div class="board-split-list">${listStripe}</div>
    </div>
    ${/* How the standings are kept is a footnote to them, so it follows them. */ ''}
    <p class="lab-intro tab-intro">${esc(intro)}</p>
    ${placeLine}
    ${board.eligible ? '' : notInStandings}
  `;
}

function showRankedPlaceholder() {
  comingSoon(
    t('Ranked'),
    t('Ranked is being built'),
    t('Playing for points is not available yet. Practice is, and it never changes Ranked points.'),
    'ranked',
  );
}

// Ranked (#10, slice 3). The season display: what phase the season is in,
// this account's balance, and the one entry the rules allow right now.
// Opening this screen starts no attempt and no timer.
const SEASON_LINE = {
  pre_season: {
    open: 'Pre-Season. The official season starts {date}.',
    finishing: 'Pre-Season is finishing.',
    closed: 'Pre-Season is closed.',
    frozen: 'Pre-Season is over.',
  },
  official: {
    open: 'The official season is open.',
    finishing: 'The season is closing. Attempts already started have five more minutes.',
    closed: 'The season is closed. Standings are provisional while settlement and any tie-breaks finish.',
    frozen: 'Points are final for this season.',
  },
};

function seasonLine(season) {
  const line = (SEASON_LINE[season.phase] ?? {})[season.status] ?? '';
  // #452: the owner announced the start; without it, say nothing invented
  if (line.includes('{date}')) {
    return season.announced_start
      ? t(line, { date: longDate(season.announced_start, language.locale) })
      : t('Pre-Season.');
  }
  return t(line);
}

function showRanked() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
      <h1 class="lab-title sr-only" id="ranked-title">\u2026</h1>
      <div id="ranked-panel"><p class="lab-intro">${esc(t('Loading\u2026'))}</p></div>
    </section>
  `, 'ranked', showRanked);
  fillRanked(view.querySelector('#ranked-panel'), view.querySelector('#ranked-title'));
  return view;
}

async function fillRanked(panel, title) {
  const [season, entry] = await Promise.all([api('/ranked/season'), api('/ranked/entry')]);
  if (!season || !entry) {
    title.textContent = t('Ranked');
    // The way to the leaderboard stays on the screen. The season and the
    // standings are separate requests, so one can fail while the other
    // answers; and when both are down, the board says so itself and
    // invites another try, rather than this screen being a dead end.
    panel.innerHTML = `
      <p class="notice">${esc(t('Could not load the season. Your points are safe.'))}</p>
      <button id="ranked-board" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.board}</span>
        <span><strong>${esc(t('Leaderboard'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
    `;
    panel.querySelector('#ranked-board').addEventListener('click', showLeaderboard);
    return;
  }
  const seasonName = season.phase === 'pre_season' ? t('Pre-Season') : season.label;
  title.textContent = seasonName;
  const closes = season.closes_at ? language.dateTime(season.closes_at) : null;
  // A new quiz is offered only while the season admits one. Closing and
  // frozen seasons keep the balance and the leaderboard on the screen.
  const open = season.status === 'open';
  const atCap = open && entry.mode === 'promotion';
  const progress = badgeProgress(entry);
  // One card carries the season, the balance, how far the badge has to go and
  // the way to play; the standings are the stripe under it.
  panel.innerHTML = `
    <div class="home-spot rk-spot">
      <span class="home-pill">${esc(seasonName)}</span>
      <div class="rk-bal">
        <div>
          <p class="lab-study-meta">${esc(t('Your balance'))}</p>
          <p class="profile-points">${language.number(entry.points)} <i>${esc(t('points'))}</i></p>
        </div>
        <div class="home-obj rk-obj"><span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt=""></div>
      </div>
      ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
      <p class="home-climb-note">${esc(balanceLine(entry))}</p>
      ${open ? `
      <button id="ranked-start" class="primary" type="button">${esc(atCap ? t('Start promotion') : t('Start quiz'))} <span aria-hidden="true">\u2192</span></button>
` : ''}
    </div>
    ${closes ? `<p class="lab-intro">${esc(t(open ? 'Closes' : 'Closed'))}: ${esc(closes)}</p>` : ''}
    ${atCap ? `
    <div class="profile-promo">
      <h2>${esc(t('Promotion unlocked'))}</h2>
      <p>${esc(t('You are at the cap, so promotion is the only Ranked quiz available. It needs a perfect 15 out of 15. Practice is available as usual and never changes these points.'))}</p>
    </div>` : ''}
    <div id="tiebreak-callout" hidden></div>
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Standings'))}</p>
      <button id="ranked-board" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.board}</span>
        <span><strong>${esc(t('Leaderboard'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
    </section>
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Season'))}</p>
      <p class="rk-note">${esc(seasonLine(season))}</p>
    </section>
  `;
  fillTiebreakCallout(panel.querySelector('#tiebreak-callout'));
  panel.querySelector('#ranked-board').addEventListener('click', showLeaderboard);
  panel.querySelector('#ranked-start')?.addEventListener('click', () => {
    if (atCap) showPromotionOffer(entry);
    else startRankedAttempt('normal');
  });
}

// Playing Ranked and promotion (built to the screens approved in #17).
// The prerequisite #95 (the promotion celebration) was waiting on: that
// issue triggers only after the server confirms a successful promotion,
// which needs a promotion attempt to actually be playable first.
//
// Ordinary Ranked and promotion share almost everything here -- the
// question, the belts, feedback held until Next, Cancel/Quit -- so one
// state machine drives both, parameterized by `mode`.
// BADGE_ORDER and nextBadgeName used to be declared here as a second,
// hand-written copy. They now live once, beside the BADGES table they are
// derived from.

// Every request an attempt makes may settle points, so each one empties the
// kept balance; the screen after the quiz then reads it fresh.
async function attemptFetch(...args) {
  clearReadCache();
  try {
    return await fetch(...args);
  } finally {
    clearReadCache();
  }
}

// How long to wait before trying again on our own, after the server says a
// previous match is still closing. The server ends a page that went quiet
// 15 seconds after its last heartbeat (engine.GRACE_SECONDS); one second
// more keeps us on the far side of it (#269).
const GRACE_RETRY_MS = 16000;

// A player who left the tab mid-match comes back to a match the server has
// already closed, or is about to: for those seconds, starting a new one is
// refused. Saying so, and trying again, beats printing the server's own
// English phrase on a screen with nowhere to go (#269).
function showPreparingNextMatch(mode) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
      <h1 class="lab-title">${esc(t('Preparing your next match'))}</h1>
      <p class="lab-intro">${esc(t('Your last match is still closing. This takes a few seconds.'))}</p>
      <button id="rq-retry" class="primary" type="button">${esc(t('Try again'))}</button>
      <button id="rq-retry-back" class="ghost" type="button">${esc(t('Back'))}</button>
    </section>
  `, 'ranked', () => showPreparingNextMatch(mode));
  const again = () => { if (view.isConnected) startRankedAttempt(mode); };
  view.querySelector('#rq-retry').addEventListener('click', again);
  view.querySelector('#rq-retry-back').addEventListener('click', showRanked);
  // and on its own, once the closing window has passed, so a player who
  // simply waits is taken into the match without touching anything
  setTimeout(again, GRACE_RETRY_MS);
  return view;
}

async function startRankedAttempt(mode) {
  const attempt = createAttemptClient({ fetchFn: attemptFetch });
  const started = await attempt.start('/ranked/attempts', { mode });
  if (!started.ok) {
    // Every refusal the server can give here, said in the player's own
    // language. Its `detail` is an English phrase for the log, never a
    // sentence to show (#269).
    const detail = started.status === 409 ? started.data?.detail : null;
    if (detail === 'Active attempt exists') {
      showPreparingNextMatch(mode);
      return;
    }
    const reason = detail === 'No open season'
      ? t('The season is closed, so no new Ranked quiz can start.')
      : detail === 'Promotion required'
        ? t('You are at the cap, so the next Ranked quiz is a promotion.')
        : detail === 'Promotion not available'
          ? t('Promotion needs you at the cap. Play ordinary Ranked to get there.')
          : started.status === 409
            ? t('That did not work. Nothing has started.')
            : t('Could not reach the server. Nothing has started.');
    comingSoon(t('Ranked'), t('Could not start'), reason, 'ranked',
      { label: 'Back', go: showRanked });
    return;
  }
  attempt.startHeartbeat();
  holdLiveAttempt(attempt);
  playRankedAttempt(attempt, mode, { correctCount: 0 });
}

// Which ranked screen the page means to be showing. A read that was in
// flight when another screen took over belongs to a screen nobody is
// looking at any more, and drawing its answer would undo what replaced it.
let rankedScreen = 0;

async function playRankedAttempt(attempt, mode, tally) {
  stopTick();
  clock = null;
  const mine = ++rankedScreen;
  const current = await attempt.current();
  if (mine !== rankedScreen) return;
  // Anything that is not a question means the attempt is over: 410 and 204
  // say so plainly, and so does any refusal -- a 403 once rendered its own
  // error body as a question, and the screen read "Question undefined of
  // 15" with NaN on the clock and no belts, a dead end with only Cancel.
  // Seen on 2026-11-26 when the last question ran out of time: two paths
  // reached here at once, and the second asked after the first had already
  // put the capability away.
  if (!current.ok || !current.data || current.data.seq === undefined) {
    // The result is read while the capability still works; stopping first
    // takes away the very thing that request needs.
    const result = await attempt.result();
    attempt.stop();
    showRankedResult(mode, result.data, tally, { attemptId: attempt.attemptId });
    return;
  }
  const q = current.data;
  const view = labPage(`
    <section class="lab-screen" id="rq-play" data-ranked-music data-attempt-live>
      <div class="tb-top">
        <span class="lab-eyebrow" id="rq-count">${esc(t('Question'))} ${q.seq} ${esc(t('of'))} 15</span>
        ${/* Quit sits up here, beside the clock and away from the four
              answers. It used to be a full-width button directly under the
              bottom two belts, where a thumb racing a ten-second clock lands. */ ''}
        <div class="rq-top-end">
          <button id="rq-cancel" class="ghost rq-quit" type="button">${esc(t('Quit'))}</button>
          <div class="rq-ring" id="rq-clock" role="timer" aria-label="${esc(t('seconds'))}"><span id="rq-ring-num"></span></div>
        </div>
      </div>
      <div class="tb-bar"><i id="rq-bar-fill"></i></div>
      <div id="rq-question"></div>
    </section>
  `, 'ranked', () => playRankedAttempt(attempt, mode, tally));
  const where = destinationLine(q);
  // What this attempt is playing for rides on the route card as its label.
  const stake = mode === 'promotion'
    ? `${t('Promotion')} · ${tally.correctCount} ${t('of')} ${q.seq - 1} ${t('right so far')}`
    : `${t('Ranked')} · ${t('counts for points')}`;
  view.querySelector('#rq-question').innerHTML = `
    <div class="rq-prompt rq-route home-spot">
      <span class="home-pill">${esc(stake)}</span>
      <p class="rq-service">${esc(where.service)}</p>
      <p class="rq-code">${esc(where.code)}</p>
    </div>
    <p class="lab-eyebrow rq-cue">${esc(t('Where does this go?'))}</p>
    <div class="belts" role="group" aria-label="${esc(t('Choose a belt'))}">
      ${(q.options || []).map((belt) => beltButton(belt)).join('')}
    </div>
  `;
  view.querySelector('#rq-cancel').addEventListener('click', () => showQuitConfirm(attempt, mode, q.seq, tally));
  // A desktop means a keyboard (#273). 1-4 answer in the order the belts are
  // drawn, Escape asks to cancel. The number is drawn on each belt so nobody
  // has to discover it; CSS hides it below the desktop breakpoint.
  const belts = [...view.querySelectorAll('.belt')];
  belts.forEach((button, index) => {
    button.querySelector('.belt-key')?.setAttribute('data-key', String(index + 1));
  });
  const onKey = (event) => {
    // The screen is replaced, not unmounted, so this is where a listener from
    // a question that is gone takes itself off rather than piling up.
    if (!view.isConnected) { document.removeEventListener('keydown', onKey); return; }
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    if (event.key === 'Escape') {
      event.preventDefault();
      view.querySelector('#rq-cancel').click();
      return;
    }
    const index = Number(event.key) - 1;
    if (!Number.isInteger(index) || index < 0 || index >= belts.length) return;
    if (belts[index].disabled) return;
    event.preventDefault();
    belts[index].click();
  };
  document.addEventListener('keydown', onKey);
  // The attempt can end while this question is on screen (the season
  // launches, the server's clock ends it). Reading it again then leads to
  // the result. Only while this screen is the one showing: feedback for a
  // last answer is also seen after the attempt ended, and waits for Next.
  attempt.onGone(() => { if (view.isConnected) playRankedAttempt(attempt, mode, tally); });
  let timer = null;
  const stopTimer = () => { if (timer) clearInterval(timer); timer = null; };
  function startCountdown(deadlineMs, totalMs) {
    const paint = () => {
      const left = deadlineMs - Date.now();
      const pct = Math.max(0, Math.min(100, (left / totalMs) * 100));
      const ring = view.querySelector('#rq-clock');
      const num = view.querySelector('#rq-ring-num');
      if (num) num.textContent = Math.max(0, Math.ceil(left / 1000));
      if (ring) { ring.style.setProperty('--pct', pct); ring.classList.toggle('low', left <= 3000); }
      const fill = view.querySelector('#rq-bar-fill');
      setBarFill(fill, pct);
      if (left <= 0) { stopTimer(); runOut(); }
    };
    paint();
    timer = setInterval(paint, 200);
  }

  // #428: the clock reaching zero used to change nothing but the ring's
  // colour. The four belts stayed enabled and the card sat there until the
  // player pressed one, which is how they learned the question had already
  // timed out and cost them its points. The press was never going anywhere:
  // the server discards a choice sent past the deadline.
  //
  // So zero does what the press did, without the press. The belts go first,
  // then the cue says what happened, then the same submit runs with no
  // choice -- which is the truth, and which the server refuses outright if
  // ITS clock says the question is still open (this page's may be fast),
  // leaving the question on screen with its remaining seconds.
  let over = false;
  function runOut() {
    if (over) return;
    over = true;
    view.querySelectorAll('.belt').forEach((b) => { b.disabled = true; });
    const cue = view.querySelector('.rq-cue');
    if (cue) { cue.textContent = t('Time ran out'); cue.classList.add('over'); }
    submit(null, null);
  }

  async function submit(choice, button) {
    stopTimer();
    // Owner report, 2026-11-26: the review of the fifteenth question showed
    // and was gone again in an instant, replaced by the result.
    //
    // The last answer ends the attempt, so the heartbeat's very next beat is
    // refused with 410 -- and the handler armed above reads that as "the
    // attempt died under a question" and goes to fetch the result. It checks
    // that this screen is still up, and it is: the feedback is 250 ms away.
    // Then the feedback draws, the read finishes, and the result lands on
    // top of it. On this machine the read came back first and the feedback
    // won; over a real network it loses, which is why it was never seen here
    // and always there.
    //
    // Disarmed here, before the answer goes: from this moment the attempt
    // ending is this function's business, and the two paths cannot race.
    attempt.onGone(() => {});
    const result = await attempt.answer(q.seq, choice);
    if (!result.ok) { playRankedAttempt(attempt, mode, tally); return; }
    const isRight = Boolean(result.data.correct);
    if (button) {
      button.classList.add(isRight ? 'belt-correct' : 'belt-incorrect');
    }
    if (isRight) playCorrectSfx(); else playIncorrectSfx();
    const nextTally = { correctCount: tally.correctCount + (isRight ? 1 : 0) };
    setTimeout(() => {
      showRankedFeedback(attempt, mode, q, choice, result.data, nextTally);
    }, FEEDBACK_PAUSE_MS);
  }

  startCountdown(new Date(q.deadline_at).getTime(), 10000);
  view.querySelectorAll('.belt').forEach((button) => button.addEventListener('click', () => {
    if (over) return;
    over = true;
    view.querySelectorAll('.belt').forEach((b) => { b.disabled = true; b.classList.toggle('picked', b === button); });
    submit(button.dataset.belt, button);
  }));
  return view;
}

function showRankedFeedback(attempt, mode, q, chosen, response, tally) {
  stopTick();
  clock = null;
  rankedScreen += 1;  // this screen is the one showing now
  const right = response.outcome === 'correct';
  const where = destinationLine(q);
  const promoCorrect = mode === 'promotion' && right;
  // A wrong or late answer ends a promotion attempt on the spot (#268):
  // the engine completes it with that answer, nothing else is asked, and
  // the one miss deducts its ordinary points. `response.finished` is true.
  const promoLost = mode === 'promotion' && !right;
  const verdict = right
    ? (mode === 'promotion' ? t('Correct · still perfect') : t('Correct'))
    : (response.outcome === 'timeout' ? t('Time ran out') : t('Review this route'));
  const view = labPage(`
    <section class="lab-screen" data-ranked-music data-attempt-live>
      <div class="rq-head">
      <div class="rq-mark ${right ? 'good' : 'bad'}" aria-hidden="true">${right ? ICONS.verdictGood : ICONS.verdictBad}</div>
      <div class="rq-head-text">
      <h1 class="lab-title rq-verdict ${right ? 'good' : 'bad'}">${esc(verdict)}</h1>
      ${mode === 'promotion'
        ? (promoCorrect
          ? `<p class="rq-worth">${esc(tally.correctCount)} ${esc(t('of'))} ${esc(tally.correctCount)} ${esc(t('right.'))} ${q.seq < 15 ? `${esc(15 - q.seq)} ${esc(t(15 - q.seq === 1 ? 'question to go.' : 'questions to go.'))}` : esc(t('That was the last one.'))}</p>`
          : `<p class="rq-worth bad">${response.worth} ${esc(t('points'))} · ${esc(t(response.difficulty === 'easy' ? 'Easy question' : response.difficulty === 'hard' ? 'Hard question' : 'Medium question'))}</p>`)
        : `<p class="rq-worth ${right ? 'good' : 'bad'}">${response.worth > 0 ? '+' : ''}${response.worth} ${esc(t('points'))} · ${esc(t(response.difficulty === 'easy' ? 'Easy question' : response.difficulty === 'hard' ? 'Hard question' : 'Medium question'))}</p>`}
      </div>
      </div>
      <div class="rq-prompt rq-route rq-route-sm"><p class="rq-service">${esc(where.service)}</p><p class="rq-code">${esc(where.code)}</p></div>
      <p class="lab-eyebrow">${esc(t('Answer'))}</p>
      <div class="rq-cmp">
        ${response.outcome === 'timeout'
          ? `<div><span>${esc(t('Your choice'))}</span><small>${esc(t('none sent in time'))}</small></div>`
          : (!right ? `<div><span>${esc(t('Your choice'))}</span>${rqChip(chosen)}</div>` : '')}
        <div><span>${esc(t('Correct belt'))}</span>${rqChip(response.correct_belt)}</div>
      </div>
      ${promoCorrect ? boardNotice(
          t('A right answer in promotion adds no points'),
          t('It keeps the attempt alive. Only passing all fifteen changes your balance, and it sets you to the next cap.'),
        ) : `<p class="rq-why">${esc(language.code === 'es' ? response.explanation_es : response.explanation_en)}</p>`}
      ${promoLost ? boardNotice(
          t('This promotion ends here'),
          t('Promotion needs all fifteen right, so it stops at the first miss. This mistake takes its points off your balance. Reach the cap again to try next time.'),
        ) : ''}
      <button id="rq-next" class="primary" type="button">${esc(t(promoLost ? 'Result' : (response.finished ? 'Finish' : 'Next')))}</button>
    </section>
  `, 'ranked', () => showRankedFeedback(attempt, mode, q, chosen, response, tally));
  view.querySelector('#rq-next').addEventListener('click', async () => {
    view.querySelector('#rq-next').disabled = true;
    if (response.finished) {
      attempt.stop();
      showRankedResult(mode, response.result, tally, { attemptId: attempt.attemptId });
      return;
    }
    await attempt.advance();
    playRankedAttempt(attempt, mode, tally);
  });
  return view;
}

// The balance breakdown the approved result screens show, line by line,
// so nothing is lumped together: what the answers were worth, what
// quitting took off, and what the cap would not let in. The quit penalty
// is the same ten points the confirmation names before anything is sent.
const QUIT_PENALTY = 10;

function rankedSum(result, quit) {
  const expected = result.points_before + result.raw_score - (quit ? QUIT_PENALTY : 0);
  const overflow = result.points_after - expected;
  return `
    <div class="sum">
      <div><span>${esc(t('Before this attempt'))}</span><b>${language.number(result.points_before)}</b></div>
      <div class="${result.raw_score < 0 ? 'lost' : ''}"><span>${esc(t(quit ? 'Right before you quit' : 'This attempt'))}</span><b>${result.raw_score >= 0 ? '+' : ''}${language.number(result.raw_score)}</b></div>
      ${quit ? `<div class="lost"><span>${esc(t('Quitting costs'))}</span><b>−${QUIT_PENALTY}</b></div>` : ''}
      ${overflow < 0 ? `<div class="lost"><span>${esc(t('Did not fit in'))} ${esc(result.badge_before)}</span><b>${language.number(overflow)}</b></div>` : ''}
      <div class="total"><span>${esc(t('Your balance now'))}</span><b>${language.number(result.points_after)}</b></div>
    </div>`;
}

function rqChip(belt) {
  const style = BELT_STYLE[belt] || { bg: '#333', fg: '#fff' };
  return `<span class="chip" data-belt="${esc(belt)}" style="background:${style.bg};color:${style.fg}">${esc(belt)}</span>`;
}

// Quit (built to the screens approved in #17). Quitting costs the partial
// score plus 10, applied before the cap -- the same penalty whatever mode
// this attempt is, since promotion's own penalty math already includes it.
function showQuitConfirm(attempt, mode, seq, tally) {
  const view = labPage(`
    ${/* #426: the attempt is still running behind this question, and
          "Continue quiz" goes back to it, so this screen keeps the beat. */ ''}
    <section class="lab-screen" data-attempt-live>
      <h1 class="lab-title">${esc(t('Quit this ranked quiz?'))}</h1>
      <p class="lab-intro">${esc(t('Your current score will count, and 10 points are taken off it. You cannot resume this attempt.'))}</p>
      <button id="qc-stay" class="primary">${esc(t('Continue quiz'))}</button>
      <button id="qc-quit" class="ghost owner-danger">${esc(t('Quit quiz'))}</button>
    </section>
  `, 'ranked', () => showQuitConfirm(attempt, mode, seq, tally));
  view.querySelector('#qc-stay').addEventListener('click', () => playRankedAttempt(attempt, mode, tally));
  view.querySelector('#qc-quit').addEventListener('click', async () => {
    view.querySelector('#qc-quit').disabled = true;
    const quit = await attempt.quit();
    attempt.stop();
    showRankedResult(mode, quit.data?.result, tally, { quit: true, attemptId: attempt.attemptId });
  });
  return view;
}

// The canonical result (built to the screens approved in #17): raw and
// applied scores, the balance before/after, and -- only for promotion --
// passed or failed. Preserved in full; nothing here is cosmetic-only.
function showRankedResult(mode, result, tally, { quit = false, attemptId = null } = {}) {
  stopTick();
  clock = null;
  if (!result) {
    comingSoon(t('Ranked'), t('Could not load the result'), t('Your points are safe. Check your history from Profile.'), 'ranked');
    return;
  }
  if (result.final_outcome === 'launch_reset') {
    showEndedAtLaunch();
    return;
  }
  // Voided by a server outage or restart: no score, in any mode, and a
  // promotion is not lost. Said before the promotion branch for that reason.
  if (result.final_outcome === 'outage_void') {
    showVoidedByOutage();
    return;
  }
  if (mode === 'promotion') {
    showPromotionResult(result, tally, { quit, attemptId });
    return;
  }
  const droppedBadge = result.badge_after !== result.badge_before
    && result.points_after < result.points_before;
  // What the match did to the balance, after the quit penalty and the cap:
  // the same difference the breakdown below adds up to, said once, large.
  const gain = result.points_after - result.points_before;
  const gainSign = gain > 0 ? '+' : gain < 0 ? '−' : '';
  const gainTone = gain > 0 ? 'good' : gain < 0 ? 'lost' : 'flat';
  // Where the balance now stands on the way to the next badge. The card on
  // this screen used to measure only the hits out of fifteen.
  const now = { badge: result.badge_after, points: result.points_after };
  const climb = badgeProgress(now);
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))} · ${esc(t(quit ? 'attempt ended' : 'attempt finished'))}</p>
      <div class="home-spot rq-score">
        <div class="rq-score-top">
          <h1 class="lab-title rq-score-line"><b>${esc(tally.correctCount)}</b> ${esc(t('of'))} 15 ${esc(t('correct'))}</h1>
          <span class="rq-gain ${gainTone}" id="rq-gain">${gainSign}${language.number(Math.abs(gain))} ${esc(t('points'))}</span>
        </div>
        <div class="profile-bar home-meter"><i style="width:${Math.round((tally.correctCount / 15) * 100)}%"></i></div>
      </div>
      ${result.final_outcome === 'season_close' ? `<p class="lab-intro" id="rq-season-close">${esc(t('The season closed before you finished. What you had scored counts, with no penalty.'))}</p>` : ''}
      ${result.final_outcome === 'disconnect' ? `<p class="lab-intro" id="rq-disconnect">${esc(t('The app lost contact with the server, so the match was closed. Questions already answered counted; one left unanswered counted as a timeout.'))}</p>` : ''}
      <p class="lab-eyebrow">${esc(t('Points'))}</p>
      ${rankedSum(result, quit)}
      ${droppedBadge ? boardNotice(
          `${t('You are')} ${result.badge_after} ${t('again')}`,
          `${t('Getting')} ${result.badge_before} ${t('back takes reaching its cap, then passing a perfect promotion.')}`,
        ) : ''}
      <p class="lab-eyebrow">${esc(t('Your climb'))}</p>
      <div class="rq-climb" id="rq-climb">
        <img class="rq-climb-badge" src="${badgeArt(now.badge)}" alt="">
        <div class="rq-climb-body">
          <p class="rq-climb-line">${esc(balanceLine(now))}</p>
          ${climb === null ? '' : `<div class="profile-bar home-meter"><i style="width:${climb}%"></i></div>`}
        </div>
      </div>
      ${/* The room for "Play again" is kept from the first paint, so the two
            buttons under it never move under a thumb while the season is read. */ ''}
      <div class="rq-next" id="rq-next-step"></div>
      <div class="rq-pair">
        <button id="rq-board" class="ghost" type="button">${esc(t('Leaderboard'))}</button>
        <button id="rq-done" class="ghost">${esc(t('Back'))}</button>
      </div>
    </section>
  `, 'ranked', () => showRankedResult(mode, result, tally, { quit, attemptId }));
  view.querySelector('#rq-done').addEventListener('click', showRanked);
  view.querySelector('#rq-board').addEventListener('click', showLeaderboard);
  fillRankedNextStep(view);
  return view;
}

// "Play again" is offered only when the server would start one: the season
// is open and the player is not at the cap, where the next Ranked quiz is a
// promotion with its own offer screen. The result does not say either, so
// they are read the way the Ranked tab reads them. When another quiz cannot
// start -- or the reads fail -- the kept room closes and Back becomes the
// screen's main button, as it was before.
async function fillRankedNextStep(view) {
  const slot = view.querySelector('#rq-next-step');
  const [season, entry] = await Promise.all([api('/ranked/season'), api('/ranked/entry')]);
  if (!view.isConnected) return;
  const again = Boolean(season && entry) && season.status === 'open' && entry.mode !== 'promotion';
  if (!again) {
    slot.remove();
    view.querySelector('#rq-done').className = 'primary';
    return;
  }
  slot.innerHTML = `<button id="rq-again" class="primary" type="button">${esc(t('Play again'))} <span aria-hidden="true">→</span></button>`;
  slot.querySelector('#rq-again').addEventListener('click', (event) => {
    event.currentTarget.disabled = true;
    startRankedAttempt('normal');
  });
}

// An attempt that was in progress when the official season launched. It
// was ended with no score, and the launch then reset every balance, so the
// usual breakdown would show a balance that no longer exists.
function showEndedAtLaunch() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))} · ${esc(t('attempt ended'))}</p>
      <h1 class="lab-title">${esc(t('The official season has started'))}</h1>
      <p class="lab-intro">${esc(t('This attempt ended when the season started. No score was applied.'))}</p>
      <p class="lab-intro">${esc(t('Everyone began again at 0 points and Iron.'))}</p>
      <button id="rq-done" class="ghost">${esc(t('Back'))}</button>
    </section>
  `, 'ranked', showEndedAtLaunch);
  view.querySelector('#rq-done').addEventListener('click', showRanked);
  return view;
}

function showVoidedByOutage() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))} · ${esc(t('attempt ended'))}</p>
      <h1 class="lab-title">${esc(t('This attempt does not count'))}</h1>
      <p class="lab-intro">${esc(t('The server stopped while you were playing, so the attempt was cancelled. No score was applied and your points are exactly as they were.'))}</p>
      <p class="lab-intro">${esc(t('You can start again when you are ready.'))}</p>
      <button id="rq-done" class="ghost">${esc(t('Back'))}</button>
    </section>
  `, 'ranked', showVoidedByOutage);
  view.querySelector('#rq-done').addEventListener('click', showRanked);
  return view;
}

// The promotion celebration (#95). It plays once per attempt, and only on
// a promotion the server has already settled: nothing here decides that a
// player was promoted, it only shows the badge the result already carries.
const CELEBRATED_KEY = 'sortLab.promotionCelebrated';
const celebrated = new Set();

function celebrationSeen(attemptId) {
  if (celebrated.has(attemptId)) return true;  // a re-render, not a new pass
  try {
    return localStorage.getItem(CELEBRATED_KEY) === attemptId;
  } catch {
    return false;  // a phone that saves nothing still gets its celebration
  }
}

function markCelebrated(attemptId) {
  celebrated.add(attemptId);
  try {
    localStorage.setItem(CELEBRATED_KEY, attemptId);
  } catch {
    // nothing to do: the in-memory mark still stops a replay in this view,
    // and a result must never fail to show because storage is full
  }
}

// Every piece starts invisible or small and ends where it belongs, so with
// animations switched off -- reduced motion, or Skip -- what is left on the
// screen is exactly the finished state: the badge and the new rank.
const CHEER_SPARKS = 10;

function sparkMarkup() {
  return Array.from({ length: CHEER_SPARKS }, (_, i) => {
    const angle = (360 / CHEER_SPARKS) * i;
    const distance = 78 + (i % 3) * 16;
    return `<span class="cheer-spark" aria-hidden="true" style="--a:${angle}deg;--d:${distance}px;--delay:${(i % 5) * 40}ms"></span>`;
  }).join('');
}

function showPromotionCelebration(result, tally, attemptId) {
  markCelebrated(attemptId);
  const badge = result.badge_after;
  const view = labPage(`
    <section class="lab-screen promo-cheer" id="promo-cheer">
      <p class="lab-eyebrow">${esc(t('Promotion'))} · ${esc(t('passed'))}</p>
      <div class="cheer-stage">
        <i class="cheer-glow" aria-hidden="true"></i>
        ${sparkMarkup()}
        <img class="cheer-badge" src="${badgeArt(badge)}" alt="">
      </div>
      <h1 class="lab-title cheer-name">${esc(t('You are'))} ${esc(badge)}.</h1>
      <p class="lab-intro">${esc(t('Fifteen out of fifteen. The new badge is yours.'))}</p>
      <p class="sr-only" role="status">${esc(t('Promoted to'))} ${esc(badge)}.</p>
      <button id="cheer-continue" class="primary" type="button">${esc(t('Continue'))}</button>
      <button id="cheer-skip" class="ghost" type="button">${esc(t('Skip'))}</button>
    </section>
  `, 'ranked', () => showPromotionCelebration(result, tally, attemptId));
  const skip = view.querySelector('#cheer-skip');
  skip.addEventListener('click', () => {
    view.querySelector('#promo-cheer').classList.add('skipped');
    skip.hidden = true;
    view.querySelector('#cheer-continue').focus();
  });
  view.querySelector('#cheer-continue').addEventListener('click', () => {
    showPromotionResult(result, tally, { attemptId });
  });
  return view;
}

function showPromotionResult(result, tally, { quit = false, attemptId = null } = {}) {
  const passed = !quit && result.badge_after !== result.badge_before
    && result.points_after > result.points_before;
  if (passed && !celebrationSeen(attemptId)) {
    return showPromotionCelebration(result, tally, attemptId);
  }
  if (passed) {
    const view = labPage(`
      <section class="lab-screen screen-promo">
        <p class="lab-eyebrow">${esc(t('Promotion'))} · ${esc(t('passed'))}</p>
        <h1 class="lab-title">15 ${esc(t('of'))} 15. ${esc(t('You are'))} ${esc(result.badge_after)}.</h1>
        <div class="profile-balance">
          <img class="profile-badge" src="${badgeArt(result.badge_after)}" alt="">
          <div>
            <p class="lab-study-meta">${esc(t('Your balance'))}</p>
            <p class="profile-points">${language.number(result.points_after)} ${esc(t('points'))}</p>
            <p class="lab-study-meta">${esc(balanceLine({ badge: result.badge_after, points: result.points_after }))}</p>
          </div>
        </div>
        <p class="lab-intro">${esc(t('Passing sets the new badge’s first point total. Ordinary Ranked quizzes are available again until you reach the next cap.'))}</p>
        <button id="rq-done" class="ghost">${esc(t('Back'))}</button>
      </section>
    `, 'ranked', () => showPromotionResult(result, tally, { quit, attemptId }));
    view.querySelector('#rq-done').addEventListener('click', showRanked);
    return view;
  }
  // the quit penalty is its own line: lumping it in with what the wrong
  // answers cost would hide where the points went
  const mistakes = result.adjustment + (quit ? QUIT_PENALTY : 0);
  const view = labPage(`
    <section class="lab-screen screen-promo">
      <p class="lab-eyebrow">${esc(t('Promotion'))} · ${esc(t(quit ? 'quit' : 'ended'))}</p>
      <h1 class="lab-title">${esc(tally.correctCount)} ${esc(t('of'))} 15 — ${esc(t('promotion needs all 15'))}</h1>
      <div class="sum">
        <div><span>${esc(t('Before this attempt'))}</span><b>${language.number(result.points_before)}</b></div>
        ${mistakes < 0
          ? `<div class="lost"><span>${esc(t('Wrong answers and timeouts'))}</span><b>${language.number(mistakes)}</b></div>`
          : ''}
        ${quit ? `<div class="lost"><span>${esc(t('Quitting costs'))}</span><b>−${QUIT_PENALTY}</b></div>` : ''}
        <div class="total"><span>${esc(t('Your balance now'))}</span><b>${language.number(result.points_after)}</b></div>
      </div>
      ${boardNotice(
          `${(BADGE_CAP[result.badge_before] ?? 0) - result.points_after} ${t('points to the cap again')}`,
          t('Earn them in ordinary Ranked quizzes. Promotion comes back when you reach the cap.'),
        )}
      <button id="rq-done" class="ghost">${esc(t('Back'))}</button>
    </section>
  `, 'ranked', () => showPromotionResult(result, tally, { quit, attemptId }));
  view.querySelector('#rq-done').addEventListener('click', showRanked);
  return view;
}

// Promotion (built to the screen approved in #17). At a cap, promotion is
// the only Ranked option. Opening this screen starts nothing -- no
// question has been sent and no clock is running -- the stakes (losing
// points on a miss) earn it a confirmation step ordinary Ranked skips.
function showPromotionOffer(entry) {
  stopTick();
  clock = null;
  const next = nextBadgeName(entry.badge);
  const view = labPage(`
    <section class="lab-screen screen-promo">
      <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
      <h1 class="lab-title">${esc(t('Promotion to'))} ${esc(next || entry.badge)}</h1>
      <div class="profile-balance">
        <img class="profile-badge" src="${badgeArt(entry.badge)}" alt="">
        <div>
          <p class="lab-study-meta">${esc(t('Your balance'))}</p>
          <p class="profile-points">${language.number(entry.points)} ${esc(t('points'))}</p>
          <p class="lab-study-meta">${esc(balanceLine(entry))}</p>
        </div>
      </div>
      <ol class="lab-rules">
        <li>${esc(t('15 questions. You need every one of them right.'))}</li>
        <li>${esc(t('One wrong answer or timeout ends the promotion right there, and that mistake deducts its points.'))}</li>
        <li>${esc(t('Losing points drops you below the cap, so promotion is not available again until you earn them back.'))}</li>
        <li>${esc(t('Passing sets you to'))} ${language.number((BADGE_CAP[entry.badge] ?? entry.points) + 1)} ${esc(t('points and'))} ${esc(next || entry.badge)}.</li>
      </ol>
      <p class="lab-intro">${esc(t('Opening this screen has not started anything. No question has been sent and no clock is running.'))}</p>
      <button id="pr-start" class="primary">${esc(t('Start promotion'))}</button>
      <button id="pr-not-now" class="ghost">${esc(t('Not now'))}</button>
      <p class="lab-study-meta">${esc(t('Ordinary Ranked quizzes are not available at the cap. Practice is, and never changes these points.'))}</p>
    </section>
  `, 'ranked', () => showPromotionOffer(entry));
  view.querySelector('#pr-not-now').addEventListener('click', showRanked);
  view.querySelector('#pr-start').addEventListener('click', () => startRankedAttempt('promotion'));
  return view;
}

// Prize tie-break, the player's side (#24, slice 7). A tie-break only
// exists for the handful of players tied for a hat, so it is not a tab of
// its own: it shows up as a callout on the Ranked screen when there is a
// round to play or a result to read, and is silent for everyone else.
async function fillTiebreakCallout(box, { onlyToPlay = false } = {}) {
  if (!box) return;
  const body = await api('/ranked/tiebreak/mine');
  const tie = body?.tie;
  if (!tie) return;
  const round = tie.round;
  if (round && !round.played) {
    // #436: the row used to sit loose between Standings and Season, the two
    // blocks on that screen that CAN wait, both of them labelled. The one
    // with a deadline was the only one with nothing naming it. Same stripe
    // and eyebrow as its neighbours now. The other two states below are
    // .board-notice cards, which carry their own heading already.
    box.innerHTML = `
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Prize tie-break'))}</p>
        <button id="tiebreak-go" class="lab-choice lab-choice-quiz" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.tiebreak}</span>
          <span><strong>${esc(t('You are in a prize tie-break'))}</strong><small>${esc(t(round.restarted
            ? 'The round was restarted after a server outage. Play it again before it closes.'
            : 'A quiz decides the hat. Play once before the round closes.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
      </section>`;
    box.querySelector('#tiebreak-go').addEventListener('click', () => showTiebreakInvite(tie));
    box.hidden = false;
    return;
  }
  // Home carries only the round still to be played: it has a deadline.
  // Everything else is read on the Ranked screen.
  if (onlyToPlay) return;
  if (round && round.played) {
    box.innerHTML = `<div class="board-notice"><h2>${esc(t('Your tie-break answers are in'))}</h2><p>${esc(t('Scores are hidden for everyone until the round closes. Come back then for the result.'))}</p></div>`;
    box.hidden = false;
    return;
  }
  // no open round: a result to read, or a place already settled
  const standing = tiebreakStanding(tie);
  if (standing) {
    const last = tie.last_result ? ` ${lastRoundLine(tie.last_result, false)}` : '';
    box.innerHTML = `<div class="board-notice"><h2>${esc(standing.title)}</h2><p>${esc(standing.text + last)}</p></div>`;
    box.hidden = false;
  }
}

// A player's own score in the last closed round. The server sends it only
// once the round has closed, and only their own. ``stillTied`` is for the
// invite to the next round, which exists because that round settled nothing.
function lastRoundLine(last, stillTied) {
  const mine = last.outcome === 'completed'
    ? t('You scored {score} of 5 in round {round}.', { score: last.score, round: last.round })
    : t(last.outcome === 'no_show'
      ? 'You did not play round {round}.'
      : 'You did not finish round {round}.', { round: last.round });
  return stillTied ? `${mine} ${t('The tie is still not settled.')}` : mine;
}

function tiebreakStanding(tie) {
  if (tie.placement === 'hat') {
    // Says nothing about how: a quiz or the owner's selection both end here.
    return { title: t('You won a hat'), text: t('The tie for the hat is settled in your favour. The leaderboard shows it once every prize place is settled.') };
  }
  if (tie.placement === 'excluded') {
    return { title: t('The tie-break is settled'), text: t('You did not complete the round, so you take no hat this season. Your points, badge and history are unchanged.') };
  }
  if (tie.placement === 'no_hat') {
    return { title: t('The tie-break is settled'), text: t('You did not take a hat this season. Your points, badge and history are unchanged.') };
  }
  if (tie.placement === 'owner_selection') {
    return { title: t('Waiting on the owner'), text: t('This tie could not be settled by a quiz, so the owner decides who takes the hat.') };
  }
  return null;
}

function showProfilePlaceholder() {
  comingSoon(
    t('Profile'),
    t('Your profile is being built'),
    t('Your points, badge and history will appear here.'),
    'profile',
  );
}

function showStart() {
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  resumeTick = null;
  stopTick();
  clock = null;
  const entries = log.all();

  // Home in stripes: Ranked first, then the player's climb, then the two ways
  // to practise. It opens straight on the Ranked card (the poster is gone);
  // the prize it announced is said in the card and shown beside the badge.
  const view = labPage(`
    <section class="lab-screen home-screen">
      <h1 class="sr-only">${esc(t('Home'))}</h1>
      ${seasonBubbleMarkup('launch-callout')}
      ${seasonBubbleMarkup('home-hat-notice')}
      <div id="home-tiebreak" hidden></div>
      <div class="home-split">
      <!-- One card says where the player stands and how to play: the balance
           as the big number, the badge beside it, how far the badge has to
           go, and the button. The climb used to be a block of its own two
           stripes down, repeating the badge at twice the height. -->
      <section class="home-stripe home-split-hero">
        <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
        <div class="home-spot home-hero">
          <span class="home-pill" id="home-season" hidden></span>
          ${signedIn() ? `
          <div class="home-hero-bal">
            <div class="home-standing" id="home-ident"><small>${esc(t('Your balance'))}</small><b class="home-hero-num">…</b></div>
            <div class="home-obj home-hero-obj" id="home-badge" aria-hidden="true"></div>
          </div>
          <div id="home-progress" hidden></div>
          <button id="home-ranked" class="primary" type="button">${esc(t('Play Ranked'))} <span aria-hidden="true">→</span></button>
          ` : `
          <div class="home-standing"><small>${esc(t('Playing as guest'))}</small><b class="home-standing-note">${esc(t('Sign in to compete'))}</b></div>
          <button id="home-signin" class="primary" type="button">${esc(t('Sign in'))} <span aria-hidden="true">→</span></button>
          `}
        </div>
        <div class="home-prize">
          <img class="home-prize-hat" src="assets/prize-hat.svg" alt="">
          <div><strong>${esc(t('UPS hat'))}</strong><small>${esc(t('Top 3 prize'))}</small></div>
        </div>
      </section>
      <!-- Handler leads the row and stays outside the Ranked stripe: the
           mini-game is deliberately kept out of Ranked, and sharing that
           stripe would say the opposite. It is practice, so it sits with the
           other two ways to practise instead of alone beside an empty half. -->
      <section class="home-stripe home-split-actions">
        <p class="lab-eyebrow">${esc(t('Practice'))}</p>
        <div class="home-shortcuts home-trio">
          <button id="home-handler" class="home-short" type="button">
            <span class="home-short-ic is-solid" aria-hidden="true">${ICONS.handlerSolid}</span>
            <strong>${esc(t('Handler'))}</strong>
          </button>
          <button id="home-practice" class="home-short" type="button">
            <span class="home-short-ic" aria-hidden="true">${ICONS.practice}</span>
            <strong>${esc(t('Practice'))}</strong>
          </button>
          <button id="home-study" class="home-short" type="button">
            <span class="home-short-ic" aria-hidden="true">${ICONS.chart}</span>
            <strong>${esc(t('Chart'))}</strong>
          </button>
        </div>
      </section>
      </div>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Your sessions'))}</p>
        <button id="viewlog" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.history}</span>
          <span><strong>${esc(t('Shift log'))}${entries.length ? ` (${entries.length})` : ''}</strong></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
      </section>
      ${log.available ? '' : `<p class="warn">${esc(t('This phone is not saving results. Each score is shown once and then gone.'))}</p>`}
      <aside class="lab-disclaimer" aria-label="${esc(t('Independent practice'))}">
        <strong>${esc(t('Made by RJ.'))}</strong> ${esc(t('Not affiliated with or endorsed by UPS. This practice does not replace any required UPS test or training. Follow your current worksite chart and instructions.'))}
      </aside>
    </section>
  `, 'home');
  view.querySelector('#home-study').addEventListener('click', showStudy);
  view.querySelector('#home-handler').addEventListener('click', showHandler);
  view.querySelector('#home-practice').addEventListener('click', showPractice);
  if (signedIn()) {
    view.querySelector('#home-ranked').addEventListener('click', showRanked);
    fillHomeIdentity(view);
  } else {
    view.querySelector('#home-signin').addEventListener('click', () => {
      if (typeof window !== 'undefined' && typeof window.showSortLabEntry === 'function') {
        window.showSortLabEntry('');
      }
    });
  }
  view.querySelector('#viewlog').addEventListener('click', showLog);
  fillLaunchCallout(view);
  if (signedIn()) fillHatNotice(view.querySelector('#home-hat-notice'));
  if (signedIn()) fillTiebreakCallout(view.querySelector('#home-tiebreak'), { onlyToPlay: true });
}

// How far through the current badge the balance is, as a percentage for the
// Home meter. Each badge below Challenger spans a thousand points up to its
// cap; Challenger has no cap, so it has no meter.
function badgeProgress(entry) {
  const cap = BADGE_CAP[entry.badge];
  if (cap === undefined) return null;
  const floor = cap - 1000;
  return Math.max(0, Math.min(100, Math.round(((entry.points - floor) / 1000) * 100)));
}

// The signed-in parts of Home, read from the endpoints Ranked and Profile
// already use: the season name, the balance, and the place in the standings
// when the player has one. A guest never reaches here. Each read may fail on
// its own; what it feeds then stays as it was rendered.
async function fillHomeIdentity(view) {
  const [season, entry, stats] = await Promise.all([
    api('/ranked/season'), api('/ranked/entry'), api('/ranked/profile/stats'),
  ]);
  const pill = view.querySelector('#home-season');
  if (pill && season) {
    pill.textContent = season.phase === 'pre_season' ? t('Pre-Season') : season.label;
    pill.hidden = false;
  }
  const box = view.querySelector('#home-ident');
  if (!box || !entry) return;
  const placed = stats && stats.place != null;
  const label = placed ? `${t('Your standing')} · #${stats.place}` : t('Your balance');
  box.innerHTML = `<small>${esc(label)}</small><b class="home-hero-num">${esc(language.number(entry.points))} <i>${esc(t('points'))}</i></b>`;

  const badge = view.querySelector('#home-badge');
  if (badge) badge.innerHTML = `<span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt="">`;

  const climb = view.querySelector('#home-progress');
  if (!climb) return;
  const progress = badgeProgress(entry);
  climb.innerHTML = `
    ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
    <p class="home-climb-note">${esc(balanceLine(entry))}</p>`;
  climb.hidden = false;
}

// The season bubble (#452; Decision 15 placement widened 2026-11-24 to Home,
// login and profile). It reads the public notice, so guests see it too. The
// wording for every state lives in seasonNotice.js, shared with the login
// screen.
// The login screen's bubble (#452). auth.js does not import the app, so it draws an
// empty #auth-season and announces itself; this fills it.
function fillAuthSeasonBubble() {
  const box = document.getElementById('auth-season');
  if (!box) return;
  readSeasonNotice().then((notice) => {
    const copy = seasonBubbleCopy(notice, { t, locale: language.locale, signedIn: false });
    showSeasonBubble(box, copy, { storage: globalThis.localStorage, closeLabel: t('Close') });
  });
}
if (typeof document !== 'undefined') {
  document.addEventListener('sortquiz:auth-shown', fillAuthSeasonBubble);
  fillAuthSeasonBubble();
}

// The one-time hat approval notice (#517): Home only, once per approval.
// The server keeps "seen", so closing it on the phone closes it on the
// laptop too. Same bubble as the season's. It names the official season,
// so a Pre-Season reader is not told that today's points count.
async function fillHatNotice(box) {
  if (!box) return;
  const body = await apiRead('/auth/hat-notice');
  if (!body?.show) return;
  box.querySelector('[data-bubble-title]').textContent = t("You're approved for the UPS hat!");
  box.querySelector('[data-bubble-text]').textContent =
    t('Play Ranked in the official season (Dec 1-31, 2026) and finish in the top 3.');
  const close = box.querySelector('[data-bubble-close]');
  close.setAttribute('aria-label', t('Close'));
  close.onclick = () => {
    box.hidden = true;
    apiSend('POST', '/auth/hat-notice/seen');
  };
  box.hidden = false;
}

async function fillLaunchCallout(view) {
  const box = view.querySelector('#launch-callout');
  if (!box) return;
  const notice = await readSeasonNotice();
  const copy = seasonBubbleCopy(notice, { t, locale: language.locale, signedIn: signedIn() });
  showSeasonBubble(box, copy, { storage: globalThis.localStorage, closeLabel: t('Close') });
}

// The auth panel calls this when the visitor enters the app, with the
// account for a signed-in player or null for a guest. Re-rendering is what
// makes the navigation change shape.
function setSession(account) {
  session = account;
  clearReadCache();
  if (signedIn()) startIdleWatch();
  else stopIdleWatch();
  showStart();
}

if (typeof window !== 'undefined') window.setSortLabSession = setSession;

// Leaving the app, by the Log out button or because the phone sat untouched
// through a sort. The server call revokes the session; even if it cannot be
// reached, this device is cleared and sent back to the entry screen, which
// is the half the player can see.
async function signOut(notice = '') {
  stopIdleWatch();
  stopTick();
  clock = null;
  session = null;
  clearReadCache();
  try {
    await logout();
  } catch {
    // Nothing to tell the player: the cookie is gone from this device either
    // way, and a session the server still holds expires on its own.
  }
  if (typeof window !== 'undefined' && typeof window.showSortLabEntry === 'function') {
    window.showSortLabEntry(notice);
    return;
  }
  showStart();
}

// Inactivity logout (#10). The rule itself lives in src/idle.js; what
// follows is the part that needs a page: when to ask, and what to show.
let idleLastSeen = 0;
let idleTimer = null;
let idleBar = null;

function removeIdleBar() {
  idleBar?.remove();
  idleBar = null;
}

function showIdleWarning() {
  if (idleBar) return;
  idleBar = document.createElement('div');
  idleBar.className = 'idle-warning';
  idleBar.setAttribute('role', 'alertdialog');
  idleBar.setAttribute('aria-live', 'assertive');
  idleBar.innerHTML = `
    <p>${esc(t('Still there? You will be logged out in a minute.'))}</p>
    <button type="button" class="primary">${esc(t('Keep me signed in'))}</button>
  `;
  idleBar.querySelector('button').addEventListener('click', () => {
    noteActivity();
    removeIdleBar();
  });
  document.body.append(idleBar);
  idleBar.querySelector('button').focus();
}

function checkIdle() {
  if (!signedIn()) return;
  const verdict = idleVerdict(Date.now(), idleLastSeen);
  if (verdict === 'out') {
    removeIdleBar();
    signOut(t('You were logged out because the app sat untouched for 15 minutes.'));
    return;
  }
  if (verdict === 'warn') showIdleWarning();
  else removeIdleBar();
}

function noteActivity() {
  idleLastSeen = Date.now();
}

const IDLE_EVENTS = ['pointerdown', 'keydown', 'touchstart', 'visibilitychange'];

function startIdleWatch() {
  if (typeof document === 'undefined') return;
  noteActivity();
  if (idleTimer !== null) return;
  IDLE_EVENTS.forEach((name) => document.addEventListener(name, onIdleEvent, { passive: true }));
  idleTimer = setInterval(checkIdle, 10 * 1000);
}

// Coming back to a tab is not activity: the check runs so a phone that was
// away past the limit is signed out the moment it is looked at again.
function onIdleEvent(event) {
  if (event.type === 'visibilitychange') {
    if (!document.hidden) checkIdle();
    return;
  }
  // A press on the warning's own button is handled there, so that the
  // warning cannot be dismissed by a stray tap elsewhere on the screen.
  if (idleBar && idleBar.contains(event.target)) return;
  if (idleBar) return;
  noteActivity();
}

function stopIdleWatch() {
  if (typeof document === 'undefined') return;
  removeIdleBar();
  if (idleTimer !== null) {
    clearInterval(idleTimer);
    idleTimer = null;
  }
  IDLE_EVENTS.forEach((name) => document.removeEventListener(name, onIdleEvent));
}

function showNameEntry(previousName = '') {
  const view = labPage(`
    <section class="lab-screen">
      ${backLink('name-back')}
      <p class="lab-eyebrow">${esc(t('Practice'))}</p>
      <h1 class="lab-title">${esc(t('Quiz yourself'))}</h1>
      <!-- The field and its button were the only ones in the app standing
           straight on the background, with no card and no eyebrow (#332).
           This is the card the sign-in screen uses, which is where a player
           last saw a field and a button together. The way out stays outside
           it, before the title like every other sub-screen: Back is not part
           of the task the card holds. -->
      <div class="auth-card">
        <label class="field">
          <span>${esc(t('Name or ID (optional)'))}</span>
          <input id="name" type="text" autocomplete="off" autocapitalize="words" placeholder="${esc(t('e.g. J. Rivera'))}" value="${esc(previousName)}">
        </label>
        <button id="begin" class="primary">${esc(t('Pick a test'))}</button>
      </div>
    </section>
  `, 'practice', () => showNameEntry(view.querySelector('#name').value));

  const nameInput = view.querySelector('#name');
  nameInput.focus();

  function begin() {
    practiceName = nameInput.value.trim();
    showDeckPicker(practiceName);
  }

  view.querySelector('#begin').addEventListener('click', begin);
  nameInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') begin();
  });
  // Back leaves the name as it was.
  view.querySelector('#name-back').addEventListener('click', showPractice);
}

function chartRow([state, code, belt, detail]) {
  return `<div class="lab-chart-row">
    <div><span class="lab-chart-state">${esc(language.state(state))}</span>
      <strong>${renderRoutingCode(code)}</strong>${detail ? `<small>${esc(language.detail(detail))}</small>` : ''}</div>
    ${beltChip(belt, 'lab-belt-chip')}
  </div>`;
}

function showStudy() {
  const view = labPage(`
    <section class="lab-screen screen-chart">
      <p class="lab-eyebrow">${esc(t('Twilight study guide'))}</p>
      <h1 class="lab-title">${esc(t('Know the chart.'))}</h1>
      <p class="lab-intro">${esc(t('Choose a service, then read its states, ZIP ranges, belts, and exceptions.'))}</p>
      <div class="chart-aside">
        <div class="lab-service-tabs" role="group" aria-label="${esc(t('Choose service'))}">
          ${Object.keys(CHART).map((service) => `<button type="button" data-service="${esc(service)}" aria-pressed="${service === studyService}">${esc(language.service(service))}</button>`).join('')}
        </div>
        ${/* The heading said the service that the pressed chip above already
              names, and "Twilight chart" what the eyebrow already says. The
              label stays for a screen reader; the placeholder shows the
              sighted reader what the field takes. */ ''}
        <label class="lab-search-label" for="chart-search">${esc(t('Find a state or number'))}</label>
        <input id="chart-search" class="lab-chart-search" type="search" placeholder="${esc(t('New Jersey, 079-9, California, 155'))}" value="${esc(studyQuery)}" autocomplete="off">
        <p id="chart-count" class="lab-chart-count" role="status"></p>
      </div>
      <div id="chart-rows"></div>
      <aside class="lab-disclaimer"><strong>${esc(t('Made by RJ.'))}</strong> ${esc(t('This study guide does not replace your current worksite chart or UPS training.'))}</aside>
    </section>
  `, 'practice', showStudy);

  const search = view.querySelector('#chart-search');
  const renderRows = () => {
    const section = searchChart(studyService, search.value);
    view.querySelector('#chart-count').textContent = t('{shown} of {total} routes shown', { shown: section.main.length + section.exceptions.length, total: section.total });
    view.querySelector('#chart-rows').innerHTML =
      // #390: the app's own section label, gold in both themes. Still an h2:
      // these are real headings, and the eyebrow is only how they look.
      (section.main.length ? `<h2 class="lab-eyebrow lab-chart-block">${esc(t('Main chart'))}</h2>${section.main.map(chartRow).join('')}` : '') +
      (section.exceptions.length ? `<h2 class="lab-eyebrow lab-chart-block">${esc(t('Exceptions and special rules'))}</h2>${section.exceptions.map(chartRow).join('')}` : '') ||
      `<p class="lab-intro">${esc(t('No matching routes in this service.'))}</p>`;
  };
  view.querySelectorAll('[data-service]').forEach((button) => button.addEventListener('click', () => {
    studyService = button.dataset.service;
    view.querySelectorAll('[data-service]').forEach((option) => option.setAttribute('aria-pressed', String(option === button)));
    renderRows();
  }));
  search.addEventListener('input', () => { studyQuery = search.value; renderRows(); });
  renderRows();
}

// One test in the picker.
//
// The picker used to have a component of its own -- .deckbtn, with .dname,
// .dblurb, .dmeta and a .dsort chip -- restyled independently in each of the
// four skin layers in index.html. It was the one list in the app that did
// not look like the Practice tab's rows: no icon, no arrow, so nothing said
// it was tappable, while the identical-looking Practice cards had both.
//
// It is the same row now: the icon tile carries the level number (or the
// quiz mark for a service deck), and the arrow is the one every other
// tappable row in the app has. The "TWILIGHT" chip that repeated on all ten
// cards is gone -- the section eyebrow above the list already says it once.
function deckRow(deck, { index = null, meta, count = null, locked = false }) {
  const icon = index === null ? ICONS.quiz : `0${index + 1}`;
  // The row shows how many questions as a figure at its end. The full
  // sentence ("15 questions, 15s each") stays for a screen reader; sighted,
  // the seconds are said once above the lists instead of on all ten rows.
  // A deck that cannot be played has no figure, so its reason is shown.
  const body = `<span class="lab-choice-icon" aria-hidden="true">${icon}</span>
      <span><strong>${esc(language.deckName(deck))}</strong><small>${esc(language.deckBlurb(deck))}</small><small class="lab-choice-meta${count === null ? '' : ' sr-only'}">${esc(meta)}</small></span>${
        count === null ? '' : `<span class="deck-count" aria-hidden="true">${esc(count)}</span>`}`;
  // A deck not yet checked against the chart is not playable, so it must not
  // be a button and must not show the arrow that promises it opens.
  if (locked) return `<div class="lab-choice locked">${body}</div>`;
  return `<button class="lab-choice lab-choice-quiz" type="button" data-deck="${deck.id}">
      ${body}<span class="lab-arrow" aria-hidden="true">→</span>
    </button>`;
}

// The way back from a sub-screen.
//
// Both places that had one used a full-width .ghost button, which is the
// shape of a primary action -- on the picker it was the heaviest thing on
// screen, above the list it was meant to be subordinate to. This is the
// same control at the weight it should have been, and it is shared so the
// app has one Back rather than a copy per screen.
function backLink(id) {
  return `<button id="${id}" class="lab-back" type="button"><span aria-hidden="true">←</span> ${esc(t('Back'))}</button>`;
}

function showDeckPicker(name) {
  stopTick();
  clock = null;
  practiceName = name ?? '';
  const entries = log.all();

  const view = labPage(`
    <section class="lab-screen screen-practice">
      <p class="lab-eyebrow">${esc(t('Practice'))}</p>
      <h1 class="lab-title tab-title">${esc(t('Pick a test'))}</h1>
      <p class="lab-intro tab-intro">${esc(t('{seconds} seconds for each card.', { seconds: CARD_SECONDS }))}</p>
      <section class="home-stripe practice-learn">
        <p class="lab-eyebrow">${esc(t('Learn'))}</p>
        <button id="study" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.chart}</span>
          <span><strong>${esc(t('Know the chart'))}</strong></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
      </section>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Levels · Twilight'))}</p>
        <div class="decks decks-card">
          ${DECKS.filter((deck) => deck.questionCount).map((deck, index) => deckRow(deck, {
            index,
            count: deck.questionCount,
            meta: t('{count} questions · {seconds}s each', { count: deck.questionCount, seconds: CARD_SECONDS }),
          })).join('')}
        </div>
      </section>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Current quizzes · Twilight'))}</p>
        <div class="decks decks-card">
          ${DECKS.filter((deck) => !deck.questionCount).map((deck) => deckRow(deck, {
            locked: !deck.verified,
            count: deck.verified ? (deck.practiceRunSize ?? deck.cards.length) : null,
            meta: deck.verified
              ? t('{count} cards · {seconds}s each', { count: deck.practiceRunSize ?? deck.cards.length, seconds: CARD_SECONDS })
              : t('Not checked against the chart yet'),
          })).join('')}
        </div>
      </section>
      ${/* Who the Shift log will name, and the two things that were ghost
            buttons under the list. "Main page" is gone: the dock is on this
            screen now, and Home is its first tab. */ ''}
      <p class="practice-who">
        <span>${esc(t('Playing as'))} <b>${esc(displayName(practiceName))}</b></span>
        <button id="practice-name" class="practice-link" type="button">${esc(t(practiceName ? 'Change name' : 'Add a name'))}</button>
        ${entries.length ? `<button id="viewlog" class="practice-link" type="button">${esc(t('Shift log'))} (${entries.length})</button>` : ''}
      </p>
    </section>
  `, 'practice', () => showDeckPicker(practiceName));

  view.querySelectorAll('.lab-choice[data-deck]').forEach((button) => {
    button.addEventListener('click', () => {
      const deck = deckById(button.dataset.deck);
      if (!deck) return;
      activeDeck = deck;
      run = createRun({ name: practiceName, cards: selectLevelCards(deck) });
      showCard();
    });
  });
  view.querySelector('#study').addEventListener('click', showStudy);
  view.querySelector('#practice-name').addEventListener('click', () => showNameEntry(practiceName));
  view.querySelector('#viewlog')?.addEventListener('click', showLog);
}

// Drops everything about the run in progress. Nothing has been recorded yet —
// results only save in showResults, once every card is answered — so leaving
// mid-test is a clean no-trace reset.
function leaveRun() {
  bailOpen = false;
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  resumeTick = null;
  stopTick();
  clock = null;
  run = null;
  activeDeck = null;
}

function quizHeader(cardNumber, total, withTimer = false) {
  return `<div class="quiz-top">
    <div class="quiz-topline"><span class="progress">${activeDeck ? esc(activeDeck.sort) : 'Twilight'}</span>${languageButtons()}</div>
    <div class="quiz-actions">
      <span id="quiz-count" class="quiz-step" tabindex="-1">${esc(t('Question {current} of {total}', { current: cardNumber, total }))}</span>
      ${withTimer ? `<div id="ring" class="quiz-timer" role="timer" aria-label="${esc(t('Time to choose'))}: ${run.seconds}" aria-live="off"><span id="ringNum">${run.seconds}</span></div>` : '<span aria-hidden="true"></span>'}
      <button id="cancel" type="button" class="stopbtn">${esc(t('Cancel'))}</button>
    </div>
    ${withTimer ? '<div class="tb-bar quiz-bar"><i id="quiz-bar-fill"></i></div>' : ''}
  </div>`;
}

function stopPanelHtml() {
  return `<div class="bail" id="bail" role="dialog" aria-modal="true" aria-labelledby="stop-title" hidden>
    <h1 id="stop-title">${esc(t('Test stopped'))}</h1>
    <p class="sub">${esc(t('Nothing is saved until a test is finished, so leaving now records nothing.'))}</p>
    <button id="bail-stay" class="primary">${esc(t('Keep going'))}</button>
    <button id="bail-picker" class="ghost">${esc(t('Pick another test'))}</button>
    <button id="bail-main" class="ghost">${esc(t('Main page'))}</button>
  </div>`;
}

function wireStopPanel(view, { canStop = () => true, pause = () => {}, resume = () => {} } = {}) {
  const bail = view.querySelector('#bail');
  const sorterName = run.name;
  bail.addEventListener('keydown', (event) => {
    if (event.key === 'Escape') {
      event.preventDefault();
      view.querySelector('#bail-stay').click();
    } else if (event.key === 'Tab') {
      const buttons = [...bail.querySelectorAll('button')];
      const first = buttons[0];
      const last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  });
  view.querySelector('#cancel').addEventListener('click', () => {
    if (!view.isConnected || bailOpen || !canStop()) return;
    bailOpen = true;
    pause();
    bail.hidden = false;
    view.querySelector('#bail-stay').focus();
  });
  view.querySelector('#bail-stay').addEventListener('click', () => {
    if (!view.isConnected || !bailOpen) return;
    bailOpen = false;
    bail.hidden = true;
    resume();
    view.querySelector('#cancel').focus();
  });
  view.querySelector('#bail-picker').addEventListener('click', () => {
    if (!view.isConnected) return;
    leaveRun();
    showDeckPicker(sorterName);
  });
  view.querySelector('#bail-main').addEventListener('click', () => {
    if (!view.isConnected) return;
    leaveRun();
    showStart();
  });
}

function showCard() {
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  const entry = currentCard(run);
  if (!entry) {
    showResults();
    return;
  }

  const { card, options } = entry;
  // Which card this render belongs to. Every handler below checks it before
  // acting, so a tap that was already queued when the card resolved cannot
  // land on the NEXT card — that silently ate a card and scored it against
  // the sorter without ever showing it.
  const cardIndex = run.index;

  const view = el(`
    <section class="screen quiz-card">
      ${quizHeader(cardIndex + 1, run.cards.length, true)}
      <div class="quiz-route">
        <div class="p-line">${esc(serviceName(card.svc, card.destinationModifier))} &middot; ${esc(card.state)}</div>
        <div class="p-code">${renderRoutingCode(card.code)}</div>
      </div>
      <p class="quiz-cue">${esc(t('Where does this go?'))}</p>
      <div class="options">
        ${options.map((belt) => {
          const style = BELT_STYLE[belt];
          return `<button class="belt" data-belt="${belt}" style="background:${style.bg};color:${style.fg}">${belt}</button>`;
        }).join('')}
      </div>
      ${stopPanelHtml()}
    </section>
  `);
  render(view);
  view.querySelector('#quiz-count').focus();
  view.querySelectorAll('[data-language]').forEach((button) => button.addEventListener('click', () => {
    if (language.code === button.dataset.language) return;
    language.set(button.dataset.language);
    document.documentElement.lang = language.code;
    view.querySelectorAll('[data-language]').forEach((option) => option.setAttribute('aria-pressed', String(option.dataset.language === language.code)));
    view.querySelector('#quiz-count').textContent = t('Question {current} of {total}', { current: cardIndex + 1, total: run.cards.length });
    view.querySelector('#cancel').textContent = t('Cancel');
    view.querySelector('.p-line').textContent = `${serviceName(card.svc, card.destinationModifier)} · ${card.state}`;
    view.querySelector('.quiz-cue').textContent = t('Where does this go?');
    view.querySelector('#ring').setAttribute('aria-label', `${t('Time to choose')}: ${Math.ceil(clock.remaining() / 1000)}`);
    view.querySelector('#bail h1').textContent = t('Test stopped');
    view.querySelector('#bail .sub').textContent = t('Nothing is saved until a test is finished, so leaving now records nothing.');
    view.querySelector('#bail-stay').textContent = t('Keep going');
    view.querySelector('#bail-picker').textContent = t('Pick another test');
    view.querySelector('#bail-main').textContent = t('Main page');
  }));

  bailOpen = false;
  const durationMs = run.seconds * 1000;
  clock = createClock({ durationMs });
  clock.start();
  if (document.hidden) clock.pause();

  const ring = view.querySelector('#ring');
  const ringNum = view.querySelector('#ringNum');
  const barFill = view.querySelector('#quiz-bar-fill');
  wireStopPanel(view, {
    canStop: () => !run.finished && run.index === cardIndex,
    pause: () => { clock.pause(); stopTick(); },
    resume: () => { clock.resume(); resumeTick?.(); },
  });

  view.querySelectorAll('.belt').forEach((button) => {
    button.addEventListener('click', () => {
      if (!view.isConnected || bailOpen || run.finished || run.index !== cardIndex) return;
      stopTick();
      const current = currentCard(run);
      // currentCard() returns { card, options }; the belt lives on the card.
      // Reading it off the wrapper made every answer look wrong (#263).
      const isRight = Boolean(current) && button.dataset.belt === current.card.belt;
      if (isRight) {
        button.classList.add('belt-correct');
        playCorrectSfx();
      } else {
        button.classList.add('belt-incorrect');
        playIncorrectSfx();
      }
      setTimeout(() => {
        showFeedback(clock.expired() ? timeoutCard(run) : answerCard(run, button.dataset.belt, clock.elapsed()));
      }, FEEDBACK_PAUSE_MS);
    });
  });

  function tick() {
    if (run.finished || run.index !== cardIndex) {
      stopTick();
      return;
    }

    const remaining = clock.remaining();
    ring.classList.toggle('urgent', remaining <= 5000);
    ringNum.textContent = Math.ceil(remaining / 1000);
    ring.setAttribute('aria-label', `${t('Time to choose')}: ${ringNum.textContent}`);
    setBarFill(barFill, (remaining / (run.seconds * 1000)) * 100);

    if (clock.expired()) {
      stopTick();
      showFeedback(timeoutCard(run));
      return;
    }
    frame = requestAnimationFrame(tick);
  }
  resumeTick = () => {
    if (frame === null) frame = requestAnimationFrame(tick);
  };
  frame = requestAnimationFrame(tick);
}

function showFeedback(response) {
  // The card is resolved: retire its clock so a background/foreground switch
  // during the feedback pause cannot pause or resume a dead card's timer.
  stopTick();
  clock = null;
  resumeTick = null;

  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  bailOpen = false;
  const right = response.outcome === 'correct';
  const verdict = right ? 'Correct!' : response.outcome === 'timeout' ? 'Out of time' : 'Review this route';
  const view = el(`
    <section class="screen quiz-feedback ${right ? 'good' : 'bad'}">
      ${quizHeader(run.index, run.cards.length)}
      <div class="quiz-verdict">
        <span class="rq-mark ${right ? 'good' : 'bad'}" aria-hidden="true">${right ? ICONS.verdictGood : ICONS.verdictBad}</span>
        <div>
          <h1 class="verdict" id="verdict" tabindex="-1">${esc(t(verdict))}</h1>
          ${right ? `<p class="quiz-auto">${esc(t('Next question starts automatically'))}…</p>` : ''}
        </div>
      </div>
      <div class="quiz-route">
        <div class="p-line">${esc(serviceName(response.svc, response.destinationModifier))} &middot; ${esc(response.state)}</div>
        <div class="p-code">${renderRoutingCode(response.code)}</div>
      </div>
      <p class="lab-eyebrow">${esc(t('Answer'))}</p>
      <div class="answer-compare">
        <div class="answer-row"><span>${esc(t('Your choice'))}</span>${response.answered ? beltChip(response.answered, 'answer') : `<strong>${esc(t('No choice'))}</strong>`}</div>
        <div class="answer-row"><span>${esc(t('Correct belt'))}</span>${beltChip(response.correctBelt, 'answer')}</div>
      </div>
      <p class="lab-eyebrow">${esc(t('Why'))}</p>
      <p class="why">${esc(language.explanation(response))}</p>
      ${right ? '' : `<button id="continue" class="primary" type="button">${esc(t('Continue'))}</button>`}
      ${stopPanelHtml()}
    </section>
  `);
  render(view);
  view.querySelector('#verdict').focus();

  const advance = () => {
    if (!view.isConnected || bailOpen || !run) return;
    feedbackTimer = null;
    if (run.finished) showResults();
    else showCard();
  };
  if (right) feedbackTimer = setTimeout(advance, 2100);
  view.querySelector('#continue')?.addEventListener('click', advance);
  wireLanguageButtons(view, () => showFeedback(response));
  wireStopPanel(view, {
    pause: () => { clearTimeout(feedbackTimer); feedbackTimer = null; },
    resume: () => { if (right) feedbackTimer = setTimeout(advance, 2100); },
  });
}

function showResults() {
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  resumeTick = null;
  stopTick();
  clock = null;

  const summary = { ...summarize(run, Date.now()), deck: activeDeck ? deckLabel(activeDeck) : null };
  const saved = log.append(summary);
  renderResults(summary, saved);
}

function renderResults(summary, saved) {
  const elapsed = clockText(summary.totalMs);

  // #382: the practice results carry the app frame -- header and dock -- like
  // every other untimed screen. Only the quiz itself drops it, on purpose: a
  // dock during a timed run is a way to lose it. The EN/ES pair that used to
  // float here loose comes from the header now, inside its bar.
  const view = labPage(`
    <section class="lab-screen screen-results">
      <div class="score-line">
        <div class="who">${esc(displayName(summary.name))}</div>
        <div class="stat"><div class="big">${summary.correct}/${summary.total}</div><div class="label">${esc(t('Score'))}</div></div>
        <div class="stat"><div class="big">${elapsed}</div><div class="label">${esc(t('Time'))}</div></div>
      </div>
      ${summary.deck ? `<div class="deckname">${esc(language.deckLabel(summary.deck))}</div>` : ''}
      ${saved ? '' : `<p class="warn">${esc(t('This result was not saved. This phone is not saving results.'))}</p>`}
      ${summary.missed.length === 0 ? `<p class="clean">${esc(t('No missorts.'))}</p>` : `
        <h2>${esc(t('Missed'))}</h2>
        <p class="lab-intro">${esc(t('Check the service and the range before choosing a belt.'))}</p>
        <ul class="missed">
          ${summary.missed.map((r) => `
            <li>
              <div class="mcard">${esc(serviceName(r.svc, r.destinationModifier))} &middot; ${esc(r.state)} &middot; ${renderRoutingCode(r.code)}</div>
              <div class="mans${r.outcome === 'timeout' ? ' timeout' : ''}">${esc(r.outcome === 'timeout' ? t('ran out of time') : t('said {answer}', { answer: r.answered }))} &rarr; <strong>${esc(r.correctBelt)}</strong></div>
              <div class="why">${esc(language.explanation(r))}</div>
            </li>
          `).join('')}
        </ul>
      `}
      <button id="again" class="primary">${esc(t('Back to main page'))}</button>
      <button id="viewlog" class="ghost">${esc(t('Shift log'))}</button>
    </section>
  `, 'practice', () => renderResults(summary, saved));

  view.querySelector('#again').addEventListener('click', () => showStart());
  view.querySelector('#viewlog')?.addEventListener('click', showLog);
}

function showLog() {
  const entries = log.all();

  // #382: same as the results screen -- the Shift log is not timed and has
  // nothing to protect, so it keeps the header and the dock.
  const view = labPage(`
    <section class="lab-screen screen-log">
      <h1>${esc(t('Shift log'))}</h1>
      ${entries.length === 0 ? `<p class="sub">${esc(t('Nothing recorded yet.'))}</p>` : `
        <ul class="logl">
          ${entries.map((s) => `
            <li>
              <span class="who">${esc(displayName(s.name))}</span>
              <span class="sc">${esc(s.correct)}/${esc(s.total)}</span>
              <span class="when">${s.deck ? esc(language.deckLabel(s.deck)) + ' &middot; ' : ''}${esc(language.dateTime(s.takenAt))}</span>
              ${s.missed.length ? `
                <ul class="logmiss">
                  ${s.missed.map((r) => `
                    <li>
                      <div class="mcard">${esc(serviceName(r.svc, r.destinationModifier))} &middot; ${esc(r.state)} &middot; ${renderRoutingCode(r.code)}</div>
                      <div class="mans${r.outcome === 'timeout' ? ' timeout' : ''}">${esc(r.outcome === 'timeout' ? t('ran out of time') : t('said {answer}', { answer: r.answered }))} &rarr; <strong>${esc(r.correctBelt)}</strong></div>
                    </li>
                  `).join('')}
                </ul>
              ` : `<div class="logclean">${esc(t('No missorts.'))}</div>`}
            </li>
          `).join('')}
        </ul>
      `}
      <button id="back" class="primary">${esc(t('Main page'))}</button>
      ${entries.length ? `<button id="export" class="ghost" hidden>${esc(t('Export to Excel'))}</button>` : ''}
      <p id="exportnote" class="exportnote" hidden></p>
      ${entries.length ? `<button id="clear" class="ghost danger">${esc(t('Clear log'))}</button>` : ''}
    </section>
  `, 'practice', showLog);

  const exportButton = view.querySelector('#export');
  const exportNote = view.querySelector('#exportnote');

  function note(message, bad = false) {
    exportNote.textContent = message;
    exportNote.classList.toggle('bad', bad);
    exportNote.hidden = !message;
  }

  if (exportButton && typeof document !== 'undefined') {
    getDownloads().then((downloads) => {
      exportButton.hidden = false;

      exportButton.addEventListener('click', async () => {
        exportButton.disabled = true;
        note(t('Preparing the sheet…'));
        try {
          await loadXLSX();
          const workbook = buildWorkbook(log.all());
          const stamp = new Date().toISOString().slice(0, 10);
          const result = await saveWorkbook(workbook, `sort-test-log-${stamp}.xlsx`, downloads);
          note(t(result.status === 'saved' ? 'Saved.' : 'Sent.'));
        } catch (error) {
          const code = error && error.code;
          if (code === 'declined') note('');
          else if (code === 'rate_limited') note(t('Already asking. Try again in a moment.'), true);
          else if (code === 'too_large') note(t('The log is too big to send. Clear it and start a fresh shift.'), true);
          else note(t('This phone could not save the file.'), true);
        } finally {
          exportButton.disabled = false;
        }
      });
    });
  }

  view.querySelector('#back').addEventListener('click', () => showStart());

  // Same sandbox problem as Cancel: window.confirm never shows here, so the
  // second tap IS the confirmation. It reverts on its own if left alone.
  const clearButton = view.querySelector('#clear');
  let armed = false;
  let armedTimer = null;
  clearButton?.addEventListener('click', () => {
    if (!armed) {
      armed = true;
      clearButton.textContent = t('Tap again to erase every result');
      armedTimer = setTimeout(() => {
        armed = false;
        clearButton.textContent = t('Clear log');
      }, 5000);
      return;
    }
    clearTimeout(armedTimer);
    log.clear();
    showStart();
  });
}

document.addEventListener('visibilitychange', () => {
  if (!clock) return;
  if (document.hidden) {
    clock.pause();
    stopTick();
  } else if (!bailOpen) {
    clock.resume();
    resumeTick?.();
  }
});

window.showStart = showStart;
showStart();
