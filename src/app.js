import { BELT_STYLE } from './belts.js';
import { AVATARS, avatarEmoji } from './avatars.js';
import { formatDestinationLabel } from './destination.js?v=chart-destination-20261108-r2';
import { SERVICE_LABEL } from './questions.js?v=chart-destination-20261108-r2';
import { DECKS, deckById, deckLabel } from './decks.js?v=chart-destination-20261108-r2';
import { CARD_SECONDS, createRun, currentCard, answerCard, timeoutCard, summarize } from './quiz.js?v=chart-destination-20261108-r2';
import { createClock } from './clock.js';
import { createShiftLog, practiceCountLabel } from './shiftLog.js';
import { saveWorkbook } from './exportFile.js';
import { CHART, searchChart } from './study.js?v=chart-destination-20261108-r2';
import { selectLevelCards } from './levels.js?v=chart-destination-20261108-r2';
import { createLanguage } from './i18n.js?v=chart-destination-20261108-r2';
import * as support from './support.js';
import { logout } from './auth.js';
import { idleVerdict } from './idle.js';
import { createAttemptClient } from './attemptClient.js';
import { playCorrectSfx, playIncorrectSfx, isSoundEnabled, toggleSound, setMusicWanted } from './sound.js';

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
    Taken: new Date(s.takenAt).toLocaleString(),
  }));

  const missorts = [];
  for (const s of entries) {
    for (const r of s.missed || []) {
      missorts.push({
        Name: s.name || 'Guest',
        Test: s.deck || '',
        Taken: new Date(s.takenAt).toLocaleString(),
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

function esc(value) {
  return String(value).replace(/[&<>"']/g, (c) => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
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

function render(node) {
  document.documentElement.lang = language.code;
  app.className = node.classList.contains('lab-shell') ? 'lab-page' : 'quiz-page';
  app.replaceChildren(node);
  // Music belongs to the Ranked quiz screens only (#264). Deciding it here,
  // on every screen change, means no way out of a quiz can leave it playing.
  setMusicWanted(Boolean(node.querySelector?.('[data-ranked-music]')));
  window.scrollTo(0, 0);
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
function applyTheme(theme) {
  const next = theme === 'day' ? 'day' : 'night';
  const root = (typeof document !== 'undefined') ? document.documentElement : null;
  if (root && typeof root.setAttribute === 'function') root.setAttribute('data-theme', next);
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
};

function navTabs() {
  const tabs = [
    ['home', ICONS.home, t('Home')],
    ['practice', ICONS.practice, t('Practice')],
  ];
  if (signedIn()) {
    tabs.push(['ranked', ICONS.ranked, t('Ranked')]);
    tabs.push(['profile', ICONS.profile, t('Profile')]);
  }
  return tabs;
}

function labPage(content, active = 'home', rerender = showStart) {
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
          <button type="button" class="lab-settings-btn" id="top-settings"><span aria-hidden="true">\u2699</span> ${esc(t('Settings'))}</button>
        </div>` : ''}
      </header>
      <main class="lab-main">${content}</main>
      <nav class="lab-nav" style="grid-template-columns: repeat(${navTabs().length}, 1fr)" aria-label="${esc(t('Main navigation'))}">
        ${navTabs().map(([id, icon, label]) => `
        <button type="button" data-nav="${id}" ${active === id ? 'aria-current="page"' : ''}><i aria-hidden="true">${icon}</i>${esc(label)}</button>`).join('')}
      </nav>
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
    else if (button.dataset.nav === 'ranked') showRanked();
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
function showPractice() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen screen-practice">
      <p class="lab-eyebrow">${esc(t('Practice'))}</p>
      <h1 class="lab-title tab-title">${esc(t('Study and practice'))}</h1>
      <p class="lab-intro tab-intro">${esc(t('Practice never changes Ranked points.'))}</p>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Learn'))}</p>
        <button id="study" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.chart}</span>
          <span><strong>${esc(t('Know the chart'))}</strong><small>${esc(t('Browse every service by state and ZIP range.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
      </section>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Test yourself'))}</p>
        <button id="quiz" class="lab-choice lab-choice-quiz" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.quiz}</span>
          <span><strong>${esc(t('Take a quiz'))}</strong><small>${esc(t('Start with Ground, then build up to the full chart.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
      </section>
    </section>
  `, 'practice', showPractice);
  view.querySelector('#study').addEventListener('click', showStudy);
  view.querySelector('#quiz').addEventListener('click', () => showNameEntry());
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
          <input id="reauth-input" type="password" autocomplete="current-password" spellcheck="false" placeholder="ABCD-EFGH-JKLM-NPQR"></label>
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
  if (entry.points >= cap) return `${entry.badge} \u00b7 ${t('at the cap')} (${cap.toLocaleString()})`;
  if (entry.points < 0) return `${entry.badge} \u00b7 ${t('a negative total stays in Iron')}`;
  // It used to read "Iron - 1,000 points to the cap (1,000)": the number said
  // twice, and nothing about where the climb goes. A player at zero could not
  // tell that from a player one point short. Progress over the target reads
  // at a glance, and the badge above is the thing the points are actually
  // for, so it is named: "Iron - 0 / 1,000 to Bronze".
  const next = nextBadgeName(entry.badge);
  const progress = `${entry.points.toLocaleString()} / ${cap.toLocaleString()}`;
  if (next === null) return `${entry.badge} \u00b7 ${progress}`;
  return `${entry.badge} \u00b7 ${progress} ${t('to')} ${next}`;
}

function showProfile(tab = 'overview') {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen screen-profile">
      <p class="lab-eyebrow">${esc(t('Profile'))}</p>
      <div class="pf-ident">
        <div class="home-obj pf-ident-obj" id="profile-badge"></div>
        <div class="pf-ident-text">
          <span id="profile-avatar-mark" class="pf-avatar" aria-hidden="true"></span>
          <h1 class="lab-title" id="profile-name">${esc(session?.username ?? '\u2026')}</h1>
          <p class="lab-intro" id="profile-tag">${session?.tag ? esc(`${t('Tag')} #${session.tag}`) : ''}</p>
        </div>
      </div>
      <div id="profile-panel"><p class="lab-intro">${esc(t('Loading\u2026'))}</p></div>
    </section>
  `, 'profile', () => showProfile(tab));

  const panel = view.querySelector('#profile-panel');
  fillProfile(view, panel, tab);
  return view;
}

// The name and tag come from the session the page already holds, so the
// panel's own request starts at once instead of waiting behind /auth/me.
// Only a session without them (which no entry path produces) asks the server.
async function fillProfile(view, panel, tab) {
  // The player's own icon, beside their name, on every tab. It comes off
  // the session like the name does, so no request is made for it; empty
  // until they choose one, which leaves the header as it was before #272.
  paintProfileAvatar(view, session?.avatar);
  if (!session?.username || !session?.tag) {
    api('/auth/me').then((me) => {
      if (!me) return;
      view.querySelector('#profile-name').textContent = me.username;
      view.querySelector('#profile-tag').textContent = `${t('Tag')} #${me.tag}`;
      // the icon rides on the session like the name does, so this only
      // runs on the path that was already asking the server anyway (#272)
      if (session) session.avatar = me.avatar;
      paintProfileAvatar(view, me.avatar);
    });
  }
  if (tab === 'overview') return fillOverview(panel);
  if (tab === 'history') await fillHistory(panel);
  else await fillSettings(panel);
  // History and Settings are sub-screens now (the mock profile has no tabs),
  // so give them a way back to the profile overview.
  // The same compact Back the picker uses (#331). It was a full-width ghost
  // button here too, which reads as a primary action above the content it is
  // supposed to be subordinate to.
  const back = document.createElement('div');
  back.innerHTML = backLink('profile-back');
  back.firstElementChild.addEventListener('click', () => showProfile('overview'));
  panel.prepend(back.firstElementChild);
  return undefined;
}

async function fillOverview(panel) {
  const entry = await api('/ranked/entry');
  if (!entry) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load your balance. Your points are safe.'))}</p>`;
    return;
  }
  // Profile laid out like the mock: badge, a stats grid, the climb, and a way
  // into history. Points come from the ledger; Best Ranked and Place come from
  // the account-private stats endpoint (#218). Practice leaves nothing on the
  // server, so Practices is the count of finished sessions in this device's
  // shift log, and the line under the grid says so (owner decision
  // 2026-11-22). A failed stats read leaves the two it feeds as a dash rather
  // than failing the whole screen.
  const DASH = '\u2014';
  // A player who has never played Ranked saw a dash under Best Ranked and
  // Place, which reads as something broken rather than "not yet". The two
  // cases are different and now look different: a read that FAILED still
  // shows the dash (the number exists, we could not fetch it), while a read
  // that succeeded and has nothing to show says so in words.
  const stats = await api('/ranked/profile/stats');
  const bestRanked = !stats ? DASH
    : stats.best_ranked ? `${stats.best_ranked.correct}/${stats.best_ranked.total}`
      : t('Not yet');
  const place = !stats ? DASH : stats.place != null ? `#${stats.place}` : t('Not yet');
  // "Not yet" / "Todavia no" at the 26px, weight-900 size the numbers use
  // overflows a quarter-width tile, so a worded value gets its own size.
  // The dash is not a word: it keeps the number size, as a placeholder.
  const statCell = (value, label) => `<div class="pf-stat"><b${value === t('Not yet') ? ' class="words"' : ''}>${esc(value)}</b><small>${esc(label)}</small></div>`;
  const tagEl = panel.closest('.lab-screen')?.querySelector('#profile-tag');
  if (tagEl) tagEl.textContent = `${tagEl.textContent} \u00b7 ${entry.badge}`;
    // The badge sits beside the name in the identity card above the panel.
  const badgeSlot = panel.closest('.lab-screen')?.querySelector('#profile-badge');
  if (badgeSlot) {
    badgeSlot.innerHTML = `<span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt="${esc(entry.badge)}">`;
  }
  const progress = badgeProgress(entry);
  panel.innerHTML = `
    <section class="home-stripe">
    <p class="lab-eyebrow">${esc(t('Your numbers'))}</p>
    <div class="pf-stats">
      ${statCell(entry.points.toLocaleString(), t('Points'))}
      ${statCell(bestRanked, t('Best Ranked'))}
      ${statCell(log.available ? practiceCountLabel(log.all()) : DASH, t('Practices'))}
      ${statCell(place, t('Place'))}
    </div>
    <p class="pf-stats-note">${esc(t('Practices counts the sessions in the Shift log on this device.'))}</p>
    </section>
    ${entry.mode === 'promotion' ? `
    <div class="profile-promo">
      <h2>${esc(t('Promotion available'))}</h2>
      <p>${esc(t('A perfect 15 out of 15 quiz moves you up. Start promotion is on the Ranked screen; nothing starts from here.'))}</p>
    </div>` : ''}
    <section class="home-stripe">
    <p class="lab-eyebrow">${esc(t('Your climb'))}</p>
    <div class="pf-climb">
      <div class="pf-badges">
        ${badgeTrail(entry.badge)}
      </div>
      ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
      <p class="home-climb-note">${esc(balanceLine(entry))}</p>
    </div>
    </section>
    <button id="pf-history" class="lab-choice" type="button">
      <span class="lab-choice-icon" aria-hidden="true">${ICONS.history}</span>
      <span><strong>${esc(t('See history'))}</strong><small>${esc(t('Your Ranked quizzes, one by one.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">→</span>
    </button>
  `;
  panel.querySelector('#pf-history').addEventListener('click', () => showProfile('history'));
}

async function fillHistory(panel) {
  const rows = await api('/ranked/history?phase=pre_season');
  if (rows === null) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load your history. Your attempts are safe.'))}</p>`;
    return;
  }
  if (rows.length === 0) {
    panel.innerHTML = `<p class="lab-intro">${esc(t('Only you can see this. Pre-Season results never count toward the official season.'))}</p>
      <p class="lab-intro">${esc(t('You played no Ranked quizzes during Pre-Season, so there is nothing here.'))}</p>`;
    return;
  }
  panel.innerHTML = `
    <p class="lab-intro">${esc(t('Only you can see this. Pre-Season results never count toward the official season.'))}</p>
    <ul class="profile-history">
      ${rows.map((row) => {
        const ended = row.final_outcome === 'launch_reset';
        return `<li class="${ended ? 'ended' : ''}">
          <b>${esc(t('Ranked quiz'))}</b>
          <span class="score">${ended ? '\u2014' : (row.adjustment > 0 ? '+' : '') + row.adjustment}</span>
          <small>${esc(new Date(row.settled_at).toLocaleDateString())}</small>
          <span class="status ${ended ? 'ended' : ''}">${esc(ended ? t('Ended at launch \u00b7 no score applied') : t('Completed'))}</span>
        </li>`;
      }).join('')}
    </ul>`;
}

// Support (#10, slice 5; the screen half of #26). Support holds Tickets and
// nothing else, and a ticket exists only because the player asked for one.
function showSupport() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Support'))}</p>
      <h1 class="lab-title">${esc(t('Tickets'))}</h1>
      <div id="support-panel"><p class="lab-intro">${esc(t('Loading\u2026'))}</p></div>
    </section>
  `, 'profile', showSupport);
  fillSupport(view.querySelector('#support-panel'));
  return view;
}

async function fillSupport(panel) {
  const result = await support.listTickets();
  if (!result || !result.ok) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load your tickets. Your tickets and your points are safe.'))}</p>`;
    return;
  }
  const tickets = result.data ?? [];
  panel.innerHTML = `
    <p class="lab-intro">${esc(t('Only you can see your tickets. When a ticket is closed, its description and connection details are deleted 15 days later. Evidence shared with another case that is still open is kept until that case closes.'))}</p>
    ${tickets.length === 0 ? `
      <p class="lab-intro">${esc(t('You have no tickets. Support only opens one when you ask for it: nothing here is created automatically, and a connection problem does not open a ticket by itself.'))}</p>
    ` : `<ul class="support-list">
      ${tickets.map((ticket) => `
      <li>
        <span class="support-pill ${ticket.closed_at ? 'closed' : 'open'}">${esc(support.outcomeLabel(ticket))}</span>
        <b>${esc(t('Ranked quiz'))}</b>
        <small>${esc(new Date(ticket.opened_at).toLocaleDateString())}</small>
        <span class="support-keep">${esc(support.retentionLine(ticket, (iso) => new Date(iso).toLocaleDateString()))}</span>
      </li>`).join('')}
    </ul>`}
    <p class="lab-intro">${esc(t('Opening a ticket never changes your points or your access.'))}</p>
    <button id="support-create" class="lab-choice lab-choice-quiz" type="button">
      <span class="lab-choice-icon">+</span>
      <span><strong>${esc(t('Create ticket'))}</strong><small>${esc(t('About one of your own Ranked attempts.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
  `;
  panel.querySelector('#support-create').addEventListener('click', showCreateTicket);
}

async function showCreateTicket() {
  const history = await api('/ranked/history');
  const attempts = history ?? [];
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Support'))}</p>
      <h1 class="lab-title">${esc(t('Create ticket'))}</h1>
      ${attempts.length === 0 ? `
        <p class="lab-intro">${esc(t('A ticket is about a Ranked attempt, and you have none yet.'))}</p>
      ` : `
      <label class="field">
        <span>${esc(t('Which attempt'))}</span>
        <select id="ticket-attempt">
          ${attempts.map((a) => `<option value="${a.attempt_id}">${esc(t('Ranked quiz'))} \u00b7 ${esc(new Date(a.settled_at).toLocaleDateString())} \u00b7 ${esc(a.final_outcome)}</option>`).join('')}
        </select>
      </label>
      <label class="field">
        <span>${esc(t('What happened (optional)'))}</span>
        <textarea id="ticket-note" rows="4" placeholder="${esc(t('Anything that helps. You can leave this empty.'))}"></textarea>
      </label>
      <aside class="lab-disclaimer">
        <strong>${esc(t('Sent with your ticket'))}</strong> ${esc(t('The attempt you picked and the connection events recorded for it. Only you and the people reviewing your ticket can see them. Your tickets never appear on your profile or the leaderboard.'))}
      </aside>
      <p class="notice" id="ticket-error" hidden></p>
      <button id="ticket-send" class="primary" type="button">${esc(t('Send ticket'))}</button>
      `}
      <button id="ticket-cancel" class="ghost" type="button">${esc(t('Cancel'))}</button>
    </section>
  `, 'profile', showCreateTicket);

  view.querySelector('#ticket-cancel').addEventListener('click', showSupport);
  const send = view.querySelector('#ticket-send');
  if (!send) return view;
  send.addEventListener('click', async () => {
    const error = view.querySelector('#ticket-error');
    error.hidden = true;
    send.disabled = true;
    const result = await support.createTicket(
      view.querySelector('#ticket-attempt').value,
      view.querySelector('#ticket-note').value,
    );
    if (result?.ok) return showTicketSent();
    error.textContent = result?.status === 409
      ? t('A ticket about this attempt is already open.')
      : t('Could not send the ticket. Nothing was sent.');
    error.hidden = false;
    send.disabled = false;
  });
  return view;
}

function showTicketSent() {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Support'))}</p>
      <h1 class="lab-title">${esc(t('Ticket sent'))}</h1>
      <p class="lab-intro">${esc(t('Someone will look at it. You can close the app; nothing is waiting on you.'))}</p>
      <aside class="lab-disclaimer">${esc(t('This does not change your points or your access, whatever the outcome is.'))}</aside>
      <button id="ticket-back" class="ghost" type="button">${esc(t('Back to your tickets'))}</button>
    </section>
  `, 'profile', showTicketSent);
  view.querySelector('#ticket-back').addEventListener('click', showSupport);
  return view;
}

// Account deletion (#10, slice 4). The wording is fixed by Decision 14 and
// is reproduced exactly, minus the word "email": the app collects none, and
// promising to delete one would imply it had been held.
const DELETE_QUESTION = 'Are you sure you want to proceed with deleting this account?';
const DELETE_ACK = 'I agree to delete my account. I understand that deleting it before prizes are finalized removes this account from this season\u2019s competition.';
const DELETE_CONSEQUENCE = 'After deletion is completed, your profile, quiz history and points are removed. A new account starts at 0 points / Iron.';
const DELETE_DISCLOSURE = 'Your profile, quiz history and points are deleted. We keep only a private season-ineligibility record until prizes are finalized.';

// An account may be signed in on five devices at once, on purpose
// (auth.sessions.MAX_ACTIVE_SESSIONS). This is the player's own remedy when
// they think somebody else has their Quiz Code: end the others, keep this
// one. The server asks for the Quiz Code first, so a stolen session alone
// cannot sign the real player out (#270).
// Choosing the icon shown on the profile and the leaderboard (#272). The
// account stores a key from a fixed set of fifteen; nothing a player types
// reaches a screen this way.
function paintProfileAvatar(root, key) {
  const mark = root?.querySelector('#profile-avatar-mark');
  if (mark) mark.textContent = avatarEmoji(key);
}

function showAvatarPicker(chosen = undefined, message = null) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Profile'))}</p>
      <h1 class="lab-title">${esc(t('Choose a profile icon'))}</h1>
      <p class="lab-intro">${esc(t('Shown on your profile and the leaderboard.'))}</p>
      <div class="avatar-grid" id="av-grid" role="group" aria-label="${esc(t('Choose a profile icon'))}">
        ${AVATARS.map(([key, glyph]) => `
          <button type="button" class="avatar-pick" data-avatar="${esc(key)}" aria-pressed="false" aria-label="${esc(key)}">${glyph}</button>`).join('')}
      </div>
      <p class="notice" id="av-said" role="status" hidden></p>
      <button id="av-none" class="ghost" type="button">${esc(t('No icon'))}</button>
      <button id="av-back" class="ghost" type="button">${esc(t('Back'))}</button>
    </section>
  `, 'profile', () => showAvatarPicker(chosen, message));

  const said = view.querySelector('#av-said');
  const mark = (key) => {
    view.querySelectorAll('.avatar-pick').forEach((button) => {
      button.setAttribute('aria-pressed', String(button.dataset.avatar === key));
    });
  };
  const tell = (text, done = false) => {
    said.hidden = false;
    said.classList.toggle('done', done);
    said.textContent = text;
  };
  if (message) tell(message, true);

  // what the account already has, so the row in use shows as pressed
  mark(chosen === undefined ? (session?.avatar ?? null) : chosen);

  const save = async (key) => {
    const result = await apiSend('PUT', '/auth/avatar', { avatar: key });
    if (!result.ok) { tell(result.reason || t('That did not work.')); return; }
    if (session) session.avatar = key;
    mark(key);
    tell(key === null ? t('Icon removed.') : t('Icon saved.'), true);
  };
  view.querySelectorAll('.avatar-pick').forEach((button) => {
    button.addEventListener('click', () => save(button.dataset.avatar));
  });
  view.querySelector('#av-none').addEventListener('click', () => save(null));
  view.querySelector('#av-back').addEventListener('click', () => showProfile('settings'));
  return view;
}

function showSignOutOthers() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Settings'))}</p>
      <h1 class="lab-title">${esc(t('Sign out my other devices'))}</h1>
      <p class="lab-intro">${esc(t('Ends every other phone or computer signed in to your account. This one stays.'))}</p>
      <p class="lab-intro">${esc(t('Your Quiz Code keeps working. Anyone using it elsewhere has to enter it again.'))}</p>
      <p class="lab-intro">${esc(t('If someone else knows your Quiz Code, ask the owner in person for a new one.'))}</p>
      <p class="notice" id="signout-others-said" role="status" hidden></p>
      <button id="signout-others-go" class="primary" type="button">${esc(t('Sign out my other devices'))}</button>
      <button id="signout-others-cancel" class="ghost" type="button">${esc(t('Cancel'))}</button>
    </section>
  `, 'profile', showSignOutOthers);

  const said = view.querySelector('#signout-others-said');
  const go = view.querySelector('#signout-others-go');
  view.querySelector('#signout-others-cancel').addEventListener('click', () => showProfile('settings'));
  go.addEventListener('click', async () => {
    go.disabled = true;
    const result = await apiSendOwner('POST', '/auth/sessions/revoke-others');
    said.hidden = false;
    if (!result.ok) {
      said.classList.remove('done');
      said.textContent = `${result.reason || t('That did not work.')} ${t('Nothing was changed.')}`;
      go.disabled = false;
      return;
    }
    said.classList.add('done');
    const ended = result.data?.ended ?? 0;
    said.textContent = ended === 0
      ? t('No other device was signed in.')
      : t(ended === 1 ? '{count} other device was signed out.' : '{count} other devices were signed out.', { count: ended });
  });
  return view;
}

function showDeleteAccount() {
  stopTick();
  clock = null;
  // Reopening always starts clean: the box unchecked, the field empty, the
  // final action disabled. Decision 14 requires the reset.
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Settings'))}</p>
      <h1 class="lab-title">${esc(t(DELETE_QUESTION))}</h1>
      <p class="lab-intro">${esc(t(DELETE_CONSEQUENCE))}</p>
      <label class="delete-ack">
        <input type="checkbox" id="delete-ack">
        <span>${esc(t(DELETE_ACK))}</span>
      </label>
      <p class="lab-intro" id="delete-hint">${esc(t('Tick the box above to continue.'))}</p>
      <div id="delete-step2" hidden>
        <div class="delete-warn">
          <h2>${esc(t('This cannot be undone'))}</h2>
          <p>${esc(t('Once this is accepted there is no undo and no restore.'))}</p>
        </div>
        <label class="field">
          <span>${esc(t('Quiz Code'))}</span>
          <input id="delete-login-id" type="text" autocomplete="off" placeholder="ABCD-EFGH-JKLM-NPQR">
        </label>
        <p class="notice" id="delete-error" hidden></p>
      </div>
      <button id="delete-go" class="primary delete-danger" type="button" disabled>${esc(t('Delete account'))}</button>
      <button id="delete-cancel" class="ghost" type="button">${esc(t('Cancel'))}</button>
      <p class="lab-disclaimer">${esc(t(DELETE_DISCLOSURE))}</p>
    </section>
  `, 'profile', showDeleteAccount);

  const ack = view.querySelector('#delete-ack');
  const step2 = view.querySelector('#delete-step2');
  const go = view.querySelector('#delete-go');
  const hint = view.querySelector('#delete-hint');
  const error = view.querySelector('#delete-error');

  ack.addEventListener('change', () => {
    step2.hidden = !ack.checked;
    hint.hidden = ack.checked;
    go.disabled = !ack.checked;
  });
  view.querySelector('#delete-cancel').addEventListener('click', () => showProfile('settings'));
  go.addEventListener('click', async () => {
    error.hidden = true;
    go.disabled = true;
    const result = await deleteAccount(view.querySelector('#delete-login-id').value);
    if (result === 'accepted') return showDeletionAccepted();
    error.textContent = result;
    error.hidden = false;
    go.disabled = false;
  });
  return view;
}

async function deleteAccount(loginId) {
  let response;
  try {
    response = await fetch('/api/auth/account/delete', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'same-origin',
      body: JSON.stringify({ login_id: loginId, acknowledge: true }),
    });
  } catch {
    return t('Could not reach the server. Nothing has been deleted.');
  }
  if (response.status === 202) return 'accepted';
  // One message for every refusal, so nobody learns which part was wrong.
  if (response.status === 409) return t('The owner account cannot be deleted.');
  if (response.status === 429) return t('Too many attempts. Wait a moment and try again.');
  return t('That did not work. Nothing has been deleted.');
}

function showDeletionAccepted() {
  session = null;
  clearReadCache();
  labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Account'))}</p>
      <h1 class="lab-title">${esc(t('Deletion accepted'))}</h1>
      <p class="lab-intro">${esc(t('You have been signed out and this account can no longer be used. Removing your data is under way.'))}</p>
      <aside class="lab-disclaimer">${esc(t('There is no undo and nothing to restore. A new account would start at 0 points and Iron, and cannot get this season\u2019s prizes back.'))}</aside>
    </section>
  `, 'home', showDeletionAccepted);
}

async function fillSettings(panel) {
  panel.innerHTML = `
    <button id="profile-owner" class="lab-choice" type="button" hidden>
      <span class="lab-choice-icon">★</span>
      <span><strong>${esc(t('Owner tools'))}</strong><small>${esc(t('Prize eligibility, access recovery, case review.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">→</span>
    </button>` + `
    <button id="profile-support" class="lab-choice" type="button">
      <span class="lab-choice-icon">?</span>
      <span><strong>${esc(t('Support'))}</strong><small>${esc(t('Your tickets.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
    <button id="profile-logout" class="lab-choice" type="button">
      <span class="lab-choice-icon">\u21aa</span>
      <span><strong>${esc(t('Log out'))}</strong><small>${esc(t('Ends this session on this device. Your points and history stay.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
    <button id="profile-avatar" class="lab-choice" type="button">
      <span class="lab-choice-icon" id="profile-avatar-now">\u25cb</span>
      <span><strong>${esc(t('Profile icon'))}</strong><small>${esc(t('Shown on your profile and the leaderboard.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
    <button id="profile-signout-others" class="lab-choice" type="button">
      <span class="lab-choice-icon">\u29c9</span>
      <span><strong>${esc(t('Sign out my other devices'))}</strong><small>${esc(t('Ends every other phone or computer signed in to your account. This one stays.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
    <button id="profile-delete" class="lab-choice lab-choice-quiz" type="button">
      <span class="lab-choice-icon">!</span>
      <span><strong>${esc(t('Delete account'))}</strong><small>${esc(t('Removes your profile, history and points.'))}</small></span>
      <span class="lab-arrow" aria-hidden="true">\u2192</span>
    </button>
    <p class="profile-version" id="profile-version"></p>
  `;
  panel.querySelector('#profile-support').addEventListener('click', showSupport);
  panel.querySelector('#profile-logout').addEventListener('click', () => signOut());
  panel.querySelector('#profile-avatar').addEventListener('click', () => showAvatarPicker());
  panel.querySelector('#profile-signout-others').addEventListener('click', showSignOutOthers);
  panel.querySelector('#profile-delete').addEventListener('click', showDeleteAccount);
  // One account in the whole app is the owner's. For everybody else the
  // row stays absent rather than disabled: a locked door still says there
  // is a room. The server refuses the calls regardless of this.
  // The version of the app actually serving this page (#274). Asked for
  // rather than written in, so it cannot drift from what is running; the
  // line stays empty if the server does not answer.
  // Fetched directly: /health sits outside /api, which is the prefix api()
  // adds, so api('/health') would ask for /api/health and get a 404.
  fetch('/health', { credentials: 'same-origin' })
    .then((answer) => (answer.ok ? answer.json() : null))
    .then((health) => {
      const line = panel.querySelector('#profile-version');
      if (line && health?.version) line.textContent = `${t('Version')} ${health.version}`;
    })
    .catch(() => {});
  const owner = panel.querySelector('#profile-owner');
  owner.addEventListener('click', showOwnerTools);
  const me = await api('/auth/me');
  if (me?.is_owner) owner.hidden = false;
}

// Owner tools (#11), built to the screens approved on 2026-11-15.
//
// Scoped on purpose: approving prize eligibility, approving access
// recovery in person, reviewing cases, and removing an account that should
// not exist (#271). The account list carries a name, a tag and a date and
// nothing of a player's record: there is still no points screen and no
// history browser, because the owner was never granted those. What is
// missing here is missing on purpose.
function showOwnerTools() {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen screen-owner">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Owner tools'))}</h1>
      <aside class="lab-disclaimer">${esc(t('These are the only administrator powers this app has. Approving does not change anybody’s points, badge or history, and gives you no access to a player’s record.'))}</aside>
      <button id="owner-eligibility" class="lab-choice" type="button">
        <span class="lab-choice-icon">✓</span>
        <span><strong>${esc(t('Prize eligibility'))}</strong><small>${esc(t('Who may win a hat this season.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="owner-recovery" class="lab-choice" type="button">
        <span class="lab-choice-icon">↺</span>
        <span><strong>${esc(t('Access recovery'))}</strong><small>${esc(t('In person, for a sorter who lost their Quiz Code.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="owner-messages" class="lab-choice" type="button">
        <span class="lab-choice-icon">✉</span>
        <span><strong>${esc(t('Recovery messages'))}</strong><small id="owner-messages-count">${esc(t('Left on the sign-in screen by people who are locked out.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="owner-select" class="lab-choice" type="button">
        <span class="lab-choice-icon">\u265b</span>
        <span><strong>${esc(t('Prize selection'))}</strong><small id="owner-select-count">${esc(t('Ties the rules send to you.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="owner-cases" class="lab-choice" type="button">
        <span class="lab-choice-icon">?</span>
        <span><strong>${esc(t('Case review'))}</strong><small>${esc(t('Tickets players opened, and connection flags.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="owner-accounts" class="lab-choice" type="button">
        <span class="lab-choice-icon">\u2715</span>
        <span><strong>${esc(t('Accounts'))}</strong><small>${esc(t('Remove an account that should not exist.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="owner-back" class="ghost">${esc(t('Back to Profile'))}</button>
    </section>
  `, 'profile', showOwnerTools);
  view.querySelector('#owner-accounts').addEventListener('click', () => showOwnerAccounts());
  view.querySelector('#owner-eligibility').addEventListener('click', () => showOwnerEligibility());
  view.querySelector('#owner-recovery').addEventListener('click', () => showRecovery());
  view.querySelector('#owner-messages').addEventListener('click', () => showRecoveryMessages());
  api('/ranked/owner/recovery-messages').then((body) => {
    const n = body?.open ?? 0;
    if (n > 0) {
      view.querySelector('#owner-messages-count').textContent =
        n === 1 ? t('1 message waiting.') : `${n} ${t('messages waiting.')}`;
    }
  });
  view.querySelector('#owner-cases').addEventListener('click', () => showCases());
  view.querySelector('#owner-select').addEventListener('click', () => showSelection());
  // the row says when something is waiting, so the owner does not have to
  // open the screen to find out
  api('/ranked/owner/selections').then((body) => {
    const n = body?.cases?.length ?? 0;
    if (n > 0) {
      view.querySelector('#owner-select-count').textContent =
        n === 1 ? t('1 tie waiting for you.') : `${n} ${t('ties waiting for you.')}`;
    }
  });
  view.querySelector('#owner-back').addEventListener('click', () => showProfile('settings'));
  return view;
}

// Prize eligibility. One sorter, one account, recorded while the season is
// open; withdrawal stays available afterwards, because leaving a wrong
// approval in place would hand a hat to somebody not entitled to it.
function showOwnerEligibility(message = null, bad = false) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Prize eligibility'))}</h1>
      ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
      <div id="elig-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="elig-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showOwnerEligibility(message, bad));
  view.querySelector('#elig-back').addEventListener('click', showOwnerTools);
  fillEligibility(view.querySelector('#elig-panel'));
  return view;
}

async function fillEligibility(panel) {
  const body = await api('/ranked/owner/approvals');
  if (!body) {
    panel.innerHTML = `<div class="board-notice board-notice-bad"><h2>${esc(t('Could not load the approvals'))}</h2><p>${esc(t('Nothing has been changed. Try again in a moment.'))}</p></div>`;
    return;
  }
  const approvals = body.approvals ?? [];
  panel.innerHTML = `
    <p class="lab-intro">${esc(t('Approved sorters may win one of the three hats. Each sorter holds one approved account. New approvals close when the season ends; you can still withdraw one afterwards.'))}</p>
    ${body.approvals_open ? `
      <div class="owner-form">
        <h2>${esc(t('Approve a sorter'))}</h2>
        <label class="field"><span>${esc(t('Player tag'))}</span>
          <input id="elig-tag" type="text" autocomplete="off" autocapitalize="characters" placeholder="#K7Q2MX"></label>
        <label class="field"><span>${esc(t('Roster reference'))}</span>
          <input id="elig-ref" type="text" autocomplete="off" placeholder="${esc(t('Primary Sort · Twilight · badge 4471'))}"></label>
        <p class="lab-study-meta">${esc(t('The roster reference is how you identify this person on your own roster. It is never shown to players.'))}</p>
        <button id="elig-approve" class="primary">${esc(t('Approve'))}</button>
      </div>
    ` : `<div class="board-notice"><h2>${esc(t('The season is closed to new approvals'))}</h2><p>${esc(t('Approvals close when the season ends, including the five-minute finishing window. You can still withdraw an approval that should not stand.'))}</p></div>`}
    <h2 class="owner-count">${approvals.length
      ? `${esc(t('Approved this season'))} (${approvals.length})`
      : esc(t('Approved this season'))}</h2>
    ${approvals.length === 0
      ? `<p class="lab-intro">${esc(t('Nobody is approved yet. Until you approve a sorter, the leaderboard has nobody to rank.'))}</p>`
      : `<ul class="approved">${approvals.map((row) => `
        <li>
          <span class="approved-who">
            <b>${esc(row.username)}</b>
            <small>#${esc(row.tag)} · ${esc(row.roster_reference)}</small>
          </span>
          <button class="ghost owner-withdraw" type="button" data-account="${esc(row.account_id)}" data-name="${esc(row.username)}">${esc(t('Withdraw'))}</button>
        </li>`).join('')}</ul>`}
  `;
  panel.querySelector('#elig-approve')?.addEventListener('click', () => approveSorter(panel));
  panel.querySelectorAll('.owner-withdraw').forEach((button) => {
    button.addEventListener('click', () => confirmWithdraw(button.dataset.account, button.dataset.name));
  });
}

async function approveSorter(panel) {
  const button = panel.querySelector('#elig-approve');
  button.disabled = true;
  const result = await apiSendOwner('POST', '/ranked/owner/approvals', {
    tag: panel.querySelector('#elig-tag').value,
    roster_reference: panel.querySelector('#elig-ref').value,
  });
  if (result.ok) {
    showOwnerEligibility(`${t('Approved')} ${result.data.username}.`);
    return;
  }
  button.disabled = false;
  // The server's refusal already says which rule stopped it, in words.
  const note = panel.querySelector('.owner-note') ?? document.createElement('p');
  note.className = 'owner-note notice';
  note.setAttribute('role', 'status');
  note.textContent = result.reason || t('That did not work. Nothing has been changed.');
  button.after(note);
}

// Withdrawing is the one thing here that takes something away, so it asks
// first, and keeping the approval is the easy answer.
function confirmWithdraw(accountId, username) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Withdraw'))} ${esc(username)}?</h1>
      <p class="lab-intro">${esc(t('They leave the standings and cannot win a hat this season. Their points, badge and history do not change, and they can go on playing. You can approve this sorter again while the season is open.'))}</p>
      <button id="withdraw-keep" class="primary">${esc(t('Keep it'))}</button>
      <button id="withdraw-go" class="ghost owner-danger">${esc(t('Withdraw approval'))}</button>
    </section>
  `, 'profile', () => confirmWithdraw(accountId, username));
  view.querySelector('#withdraw-keep').addEventListener('click', () => showOwnerEligibility());
  view.querySelector('#withdraw-go').addEventListener('click', async () => {
    view.querySelector('#withdraw-go').disabled = true;
    const result = await apiSendOwner('DELETE', `/ranked/owner/approvals/${accountId}`);
    showOwnerEligibility(
      result.ok ? `${t('Withdrawn')}: ${username}.` : (result.reason || t('That did not work. Nothing has been changed.')),
      !result.ok,
    );
  });
  return view;
}

// Accounts (#271). The owner removes an account that should not exist: a
// test, a duplicate, somebody who left. It is the player's own deletion
// with a different person asking, so it ends the same way and cannot be
// undone; the tag typed by hand is what stops a slip on a long list.
function showOwnerAccounts(message = null, bad = false) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Accounts'))}</h1>
      ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
      <div id="acct-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="acct-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showOwnerAccounts(message, bad));
  view.querySelector('#acct-back').addEventListener('click', showOwnerTools);
  fillOwnerAccounts(view.querySelector('#acct-panel'));
  return view;
}

function accountRowLine(row) {
  const parts = [`#${row.tag}`, `${t('created')} ${new Date(row.created_at).toLocaleDateString()}`];
  if (row.approved) parts.push(t('Approved for prizes'));
  if (row.has_played) parts.push(t('Has played'));
  return parts.join(' \u00b7 ');
}

async function fillOwnerAccounts(panel) {
  const body = await api('/ranked/owner/accounts');
  if (!body) {
    panel.innerHTML = `<div class="board-notice board-notice-bad"><h2>${esc(t('Could not load the accounts'))}</h2><p>${esc(t('Nothing has been changed. Try again in a moment.'))}</p></div>`;
    return;
  }
  const accounts = body.accounts ?? [];
  panel.innerHTML = `
    <p class="lab-intro">${esc(t('Every account, newest first. This list shows a name, a tag and a date, and nothing of anybody’s points or history.'))}</p>
    <label class="field"><span>${esc(t('Find by name or tag'))}</span>
      <input id="acct-find" type="search" autocomplete="off"></label>
    <h2 class="owner-count">${esc(t('Accounts'))} (${accounts.length})</h2>
    <ul class="approved" id="acct-list">${accounts.map((row) => `
      <li data-find="${esc(`${row.username} ${row.tag}`.toLowerCase())}">
        <span class="approved-who">
          <b>${esc(row.username)}</b>
          <small>${esc(accountRowLine(row))}</small>
        </span>
        ${row.is_owner
          ? `<small class="acct-you">${esc(t('You'))}</small>`
          : `<button class="ghost owner-danger acct-delete" type="button" data-account="${esc(row.account_id)}">${esc(t('Delete'))}</button>`}
      </li>`).join('')}</ul>
    <p class="lab-intro" id="acct-none" hidden>${esc(t('No account matches.'))}</p>
  `;
  const byId = new Map(accounts.map((row) => [row.account_id, row]));
  panel.querySelectorAll('.acct-delete').forEach((button) => {
    button.addEventListener('click', () => confirmOwnerDelete(byId.get(button.dataset.account)));
  });
  const find = panel.querySelector('#acct-find');
  find.addEventListener('input', () => {
    const wanted = find.value.trim().replace(/^#/, '').toLowerCase();
    let shown = 0;
    panel.querySelectorAll('#acct-list li').forEach((item) => {
      item.hidden = !item.dataset.find.includes(wanted);
      if (!item.hidden) shown += 1;
    });
    panel.querySelector('#acct-none').hidden = shown > 0;
  });
}

function confirmOwnerDelete(row) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Delete this account?'))}</h1>
      <div class="owner-form">
        <p class="acct-name"><b>${esc(row.username)}</b></p>
        <p class="acct-meta">${esc(accountRowLine(row))}</p>
      </div>
      <div class="delete-warn">
        <h2>${esc(t('This cannot be undone'))}</h2>
        <p>${esc(t('This person is signed out at once and their profile, points and history are removed. They leave the leaderboard, and whoever was below them moves up.'))}</p>
        ${row.approved ? `<p>${esc(t('This account is approved for prizes. Deleting it takes this sorter out of this season: they cannot be approved again, on this or any other account.'))}</p>` : ''}
      </div>
      <label class="field">
        <span>${esc(t('Type this account’s tag to confirm'))}</span>
        <input id="acct-tag" type="text" autocomplete="off" autocapitalize="characters">
      </label>
      <p class="notice" id="acct-error" hidden></p>
      <button id="acct-keep" class="primary" type="button">${esc(t('Keep it'))}</button>
      <button id="acct-go" class="ghost owner-danger" type="button" disabled>${esc(t('Delete account'))}</button>
    </section>
  `, 'profile', () => confirmOwnerDelete(row));
  const typed = view.querySelector('#acct-tag');
  const go = view.querySelector('#acct-go');
  const error = view.querySelector('#acct-error');
  const cleaned = () => typed.value.trim().replace(/^#/, '').trim().toUpperCase();
  typed.addEventListener('input', () => { go.disabled = cleaned() !== row.tag; });
  view.querySelector('#acct-keep').addEventListener('click', () => showOwnerAccounts());
  go.addEventListener('click', async () => {
    go.disabled = true;
    const result = await apiSendOwner('POST', `/ranked/owner/accounts/${row.account_id}/delete`, {
      confirm_tag: typed.value,
    });
    if (result.ok) {
      showOwnerAccounts(`${t('Deleted')}: ${row.username} #${row.tag}.`);
      return;
    }
    go.disabled = cleaned() !== row.tag;
    error.textContent = result.reason || t('That did not work. Nothing has been changed.');
    error.hidden = false;
  });
  return view;
}

// The tie-break invite: what the round is, before anything starts.
function showTiebreakInvite(tie) {
  stopTick();
  clock = null;
  const round = tie.round;
  const closes = new Date(round.deadline_at).toLocaleString();
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
  const view = labPage(`
    <section class="lab-screen" id="tb-play">
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
      <div class="rq-prompt">
        <p class="rq-service">${esc(where.service)}</p>
        <p class="rq-code">${esc(where.code)}</p>
      </div>
      <p class="lab-study-meta">${esc(t('Where does this go?'))}</p>
      <div class="belts" role="group" aria-label="${esc(t('Choose a belt'))}">
        ${(q.options || []).map((belt) => beltButton(belt)).join('')}
      </div>
      <p class="lab-study-meta">${esc(t('No feedback: whether you were right stays hidden until the round closes.'))}</p>
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
      if (fill) fill.style.width = `${Math.max(0, Math.min(100, (left / total) * 100))}%`;
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
      <p class="lab-eyebrow">${esc(t('Prize tie-break'))} · ${esc(t('round'))} ${round.number}</p>
      <h1 class="lab-title">${esc(t('Attempt submitted'))}</h1>
      <p class="lab-intro">${esc(t('All five are in. Nothing else is needed from you.'))}</p>
      <div class="board-notice"><h2>${esc(t('Why you see nothing yet'))}</h2>
        <p>${esc(t('Everyone in this round answers the same five questions, at different times. Showing a score now would tell a later player what to expect. Scores stay hidden for everyone until the round closes.'))}</p></div>
      <button id="tb-back" class="ghost">${esc(t('Back to Ranked'))}</button>
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

// Prize selection (#24, slice 6), built to the screen approved on
// 2026-11-15. Where every "wait for the owner" lands: still tied after the
// last round, no fresh question set left, or several players who did not
// finish competing for fewer hats.
//
// The owner sees each player's tie-break history (decided 2026-11-15), so
// the choice is made with the information the quiz had. No points appear,
// because none can change here. The choice is final; nothing in the app
// takes a hat back.
function outcomeLine(h) {
  if (h.outcome === 'completed') return `${t('Round')} ${h.round}: ${h.score}/5`;
  if (h.outcome === 'no_show') return `${t('Round')} ${h.round}: ${t('did not play')}`;
  return `${t('Round')} ${h.round}: ${t('did not finish')}`;
}

function showSelection(message = null) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Prize selection'))}</h1>
      ${message ? `<div class="board-notice" role="status"><p>${esc(message)}</p></div>` : ''}
      <div id="sel-panel"><p class="lab-intro" role="status">${esc(t('Loading\u2026'))}</p></div>
      <button id="sel-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showSelection(message));
  view.querySelector('#sel-back').addEventListener('click', showOwnerTools);
  fillSelection(view.querySelector('#sel-panel'));
  return view;
}

async function fillSelection(panel) {
  const body = await api('/ranked/owner/selections');
  if (!body) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load the ties. Nothing has been changed.'))}</p>`;
    return;
  }
  if (body.cases.length === 0) {
    panel.innerHTML = `<div class="owner-form"><h2>${esc(t('Nothing waiting'))}</h2>
      <p class="lab-study-meta">${esc(t('A tie comes here only when the rules say so: still tied after the last round, no fresh questions left, or several players who did not finish competing for fewer hats.'))}</p></div>`;
    return;
  }
  panel.innerHTML = `
    <aside class="lab-disclaimer">${esc(t('These ties could not be settled by a quiz, so the rules send them to you. Choose who takes the hats. Your choice is final, and it changes nobody\u2019s points, badge or tie-break results.'))}</aside>
    ${body.cases.map((c) => `
      <div class="owner-form sel-case" data-group="${esc(c.group_id)}" data-hats="${c.hats}">
        <p class="lab-eyebrow">${c.hats} ${esc(c.hats === 1 ? t('hat') : t('hats'))} \u00b7 ${c.tied_points.toLocaleString()} ${esc(t('points each'))}</p>
        <ul class="sel-list">${c.players.map((p) => `
          <li><label><input type="checkbox" value="${esc(p.account_id)}" data-name="${esc(p.username)}">
            <b>${esc(p.username)}</b> <small>#${esc(p.tag)}</small></label>
            <small class="sel-hist">${p.history.map((h) => esc(outcomeLine(h))).join(' \u00b7 ') || esc(t('No round was played.'))}</small></li>`).join('')}
        </ul>
        <button class="primary sel-go" type="button" disabled data-ask="${esc(t('Choose'))} ${c.hats} ${esc(t('to continue'))}">${esc(t('Choose'))} ${c.hats} ${esc(t('to continue'))}</button>
      </div>`).join('')}
  `;
  panel.querySelectorAll('.sel-case').forEach((box) => {
    const hats = Number(box.dataset.hats);
    const go = box.querySelector('.sel-go');
    box.querySelectorAll('input[type=checkbox]').forEach((input) => input.addEventListener('change', () => {
      go.disabled = box.querySelectorAll('input:checked').length !== hats;
      // the label asks only while something is still missing
      go.textContent = go.disabled ? go.dataset.ask : t('Continue');
    }));
    go.addEventListener('click', () => {
      const picked = [...box.querySelectorAll('input:checked')];
      const left = [...box.querySelectorAll('input:not(:checked)')].map((i) => i.dataset.name);
      confirmSelection(box.dataset.group, picked.map((i) => i.value), picked.map((i) => i.dataset.name), left);
    });
  });
}

// Final, so it asks first, says plainly who does not take a hat, and makes
// going back the easy answer.
function confirmSelection(groupId, ids, names, others) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Give the hat to'))} ${esc(names.join(', '))}?</h1>
      <p class="lab-intro">${esc(others.length
        ? `${others.join(', ')} ${t('does not take a hat this season.')}`
        : '')} ${esc(t('This cannot be undone from the app. Nobody\u2019s points, badge or tie-break results change.'))}</p>
      <button id="sel-back-to" class="primary">${esc(t('Go back'))}</button>
      <button id="sel-record" class="ghost owner-danger">${esc(t('Record my choice'))}</button>
    </section>
  `, 'profile', () => confirmSelection(groupId, ids, names, others));
  view.querySelector('#sel-back-to').addEventListener('click', () => showSelection());
  view.querySelector('#sel-record').addEventListener('click', async () => {
    view.querySelector('#sel-record').disabled = true;
    const result = await apiSendOwner('POST', `/ranked/owner/selections/${groupId}`, { account_ids: ids });
    showSelection(result.ok
      ? `${t('Recorded')}: ${names.join(', ')}.`
      : (result.reason || t('That did not work. Nothing has been changed.')));
  });
  return view;
}

// Case review (#11, boxes 3 and 6), built to the screen approved on
// 2026-11-15.
//
// Two kinds of case, kept apart because they arrive differently: a ticket
// is a player asking, a flag is the server noticing a pattern. Neither is
// proof that anybody cheated and neither can change points or access, so
// there is no sanction on this screen to press -- only an outcome to
// record, or the choice to leave the case open.
//
// The retention line sits inside each case rather than in a footnote: a
// reviewer deciding what to do should see how long the evidence they are
// looking at will exist.
const CASE_OUTCOMES = [
  ['network_instability', 'Close · network instability'],
  ['insufficient_evidence', 'Close · not enough evidence'],
];

function showCases(kind = 'tickets', message = null) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Case review'))}</h1>
      <aside class="lab-disclaimer">${esc(t('Closing a case records what you found. It never changes anybody’s points, badge or access, and it opens no ticket by itself. A connection flag is a pattern the server noticed, not evidence that somebody cheated.'))}</aside>
      ${message ? `<div class="board-notice" role="status"><p>${esc(message)}</p></div>` : ''}
      <div class="profile-tabs" role="tablist" aria-label="${esc(t('Case kind'))}">
        <button type="button" role="tab" data-case="tickets" aria-selected="${kind === 'tickets'}">${esc(t('Tickets'))}</button>
        <button type="button" role="tab" data-case="flags" aria-selected="${kind === 'flags'}">${esc(t('Flags'))}</button>
      </div>
      <div id="case-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="case-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showCases(kind, message));
  view.querySelectorAll('[data-case]').forEach((button) => button.addEventListener('click', () => {
    if (button.dataset.case !== kind) showCases(button.dataset.case);
  }));
  view.querySelector('#case-back').addEventListener('click', showOwnerTools);
  fillCases(view.querySelector('#case-panel'), kind);
  return view;
}

function caseEvents(events) {
  if (!events || events.length === 0) return '';
  return `
    <details class="lab-fold">
      <summary>${esc(t('Connection events'))} (${events.length})</summary>
      <ul class="case-events">${events.map((event) => `
        <li>${esc(event.kind.replace(/_/g, ' '))} · ${esc(new Date(event.occurred_at).toLocaleString())}</li>
      `).join('')}</ul>
    </details>`;
}

function outcomeButtons(id, kindLabel) {
  return `<div class="case-actions">${CASE_OUTCOMES.map(([outcome, label]) => `
    <button class="ghost case-close" type="button" data-id="${esc(id)}" data-outcome="${outcome}" data-label="${esc(t(label))}">${esc(t(label))}</button>
  `).join('')}</div>
  <p class="lab-study-meta">${esc(t('Or leave it open. Nothing happens until you choose.'))}</p>`;
}

async function fillCases(panel, kind) {
  const body = await api(kind === 'flags' ? '/ranked/flags' : '/ranked/support/review');
  if (!body) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load the cases. Nothing has been changed.'))}</p>`;
    return;
  }
  if (body.length === 0) {
    panel.innerHTML = `
      <div class="owner-form">
        <h2>${esc(t('Nothing waiting'))}</h2>
        <p class="lab-study-meta">${esc(kind === 'flags'
          ? t('No open flags. A flag appears only when the server notices repeated connection loss in one attempt.')
          : t('No open tickets. Tickets only appear when a player opens one; a connection problem does not open a ticket by itself.'))}</p>
      </div>`;
    return;
  }
  panel.innerHTML = `<ul class="cases">${body.map((row) => (kind === 'flags' ? `
    <li>
      <p class="lab-eyebrow">${esc(t('Flag'))} · ${esc(t('noticed'))} ${esc(new Date(row.flagged_at).toLocaleDateString())}</p>
      <h2>${esc(row.username)} · #${esc(row.tag)}</h2>
      <p class="lab-study-meta">${esc(t('Losses between'))} ${esc(new Date(row.first_loss_at).toLocaleString())} ${esc(t('and'))} ${esc(new Date(row.last_loss_at).toLocaleString())}</p>
      <div class="board-notice"><p>${esc(t('This is a pattern the server noticed. It is not proof that anybody cheated, and closing it changes no points and no access.'))}</p></div>
      ${caseEvents(row.events)}
      <p class="case-keep">${esc(t('Kept while this review is open. Fifteen days after it closes, these connection details are deleted, unless a case still open shares the same log.'))}</p>
      ${outcomeButtons(row.attempt_id)}
    </li>` : `
    <li>
      <p class="lab-eyebrow">${esc(t('Ticket'))} · ${esc(t('opened'))} ${esc(new Date(row.opened_at).toLocaleDateString())}</p>
      <h2>${esc(row.username)} · #${esc(row.tag)}</h2>
      ${row.description ? `<blockquote class="case-said">${esc(row.description)}</blockquote>`
        : `<p class="lab-study-meta">${esc(t('They wrote no description.'))}</p>`}
      ${caseEvents(row.events)}
      <p class="case-keep">${esc(t('While this case is open, its description and connection details are kept.'))}</p>
      ${outcomeButtons(row.id)}
    </li>`)).join('')}</ul>`;
  panel.querySelectorAll('.case-close').forEach((button) => {
    button.addEventListener('click', () => confirmCloseCase(
      kind, button.dataset.id, button.dataset.outcome, button.dataset.label,
    ));
  });
}

// Closing asks first and says which words the player will see, because
// the outcome is shown to them and cannot be taken back by this screen.
function confirmCloseCase(kind, id, outcome, label) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(label)}?</h1>
      <p class="lab-intro">${esc(outcome === 'network_instability'
        ? t('The player sees this outcome in those words. Their points, badge and access do not change either way.')
        : t('The player sees “not enough evidence”, which is not an accusation. Their points, badge and access do not change either way.'))}</p>
      <p class="lab-intro">${esc(t('The description and connection details are deleted 15 days after closure, unless a case still open shares the same log.'))}</p>
      <button id="case-keep" class="primary">${esc(t('Keep it open'))}</button>
      <button id="case-go" class="ghost owner-danger">${esc(t('Close the case'))}</button>
    </section>
  `, 'profile', () => confirmCloseCase(kind, id, outcome, label));
  view.querySelector('#case-keep').addEventListener('click', () => showCases(kind));
  view.querySelector('#case-go').addEventListener('click', async () => {
    view.querySelector('#case-go').disabled = true;
    const path = kind === 'flags'
      ? `/ranked/flags/${id}/close`
      : `/ranked/support/review/${id}/close`;
    const result = await apiSend('POST', path, { outcome });
    showCases(kind, result.ok
      ? `${t('Closed')} · ${label.replace(/^Close · /, '')}.`
      : (result.reason || t('That did not work. Nothing has been changed.')));
  });
  return view;
}

// Access recovery (#11, box 2), built to the screen approved on
// 2026-11-15. Two steps on purpose: finding the account asserts nothing,
// and the login ID is issued only after the owner says they have checked
// the person in front of them.
//
// The screen cannot verify the thing that matters most — that this is
// really that sorter — so it says so plainly rather than implying the
// check has been done by showing a confident-looking form.
function showRecovery(message = null, bad = false) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Access recovery'))}</h1>
      ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
      <div class="owner-form">
        <h2>${esc(t('Who is in front of you?'))}</h2>
        <label class="field"><span>${esc(t('Player tag'))}</span>
          <input id="rec-tag" type="text" autocomplete="off" autocapitalize="characters" placeholder="#K7Q2MX"></label>
        <p class="lab-study-meta">${esc(t('The tag is on their profile. It is how you find the account, not proof of who they are.'))}</p>
        <button id="rec-find" class="primary">${esc(t('Find the account'))}</button>
      </div>
      <h2 class="owner-count">${esc(t('Recent recoveries'))}</h2>
      <div id="rec-list"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="rec-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showRecovery(message, bad));
  view.querySelector('#rec-back').addEventListener('click', showOwnerTools);
  view.querySelector('#rec-find').addEventListener('click', () => findForRecovery(view));
  fillRecoveries(view.querySelector('#rec-list'));
  return view;
}

async function fillRecoveries(panel) {
  const body = await api('/ranked/owner/recoveries');
  if (!body) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load the recent recoveries. Nothing has been changed.'))}</p>`;
    return;
  }
  const rows = body.recoveries ?? [];
  if (rows.length === 0) {
    panel.innerHTML = `<p class="lab-intro">${esc(t('No recoveries yet.'))}</p>`;
    return;
  }
  panel.innerHTML = `<ul class="approved">${rows.map((row) => `
    <li>
      <span class="approved-who">
        <b>${esc(row.username)}</b>
        <small>#${esc(row.tag)} · ${esc(row.completed_at
          ? `${t('handed over')} ${new Date(row.completed_at).toLocaleDateString()}`
          : `${t('opened')} ${new Date(row.opened_at).toLocaleDateString()}, ${t('not completed')}`)}</small>
      </span>
    </li>`).join('')}</ul>`;
}

// Recovery messages (#251). What a locked-out player typed on the sign-in
// screen. Anybody can type anything there, including somebody else's name,
// so this screen shows the text as text and says what it is worth: a reason
// to go and find a person. Recovering access is still the other screen.
function showRecoveryMessages(message = null, bad = false) {
  stopTick();
  clock = null;
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Recovery messages'))}</h1>
      ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
      <aside class="lab-disclaimer">${esc(t('A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.'))}</aside>
      <button id="msg-recovery" class="ghost">${esc(t('Open Access recovery'))}</button>
      <div id="msg-list"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      <button id="msg-back" class="ghost">${esc(t('Back to Owner tools'))}</button>
    </section>
  `, 'profile', () => showRecoveryMessages(message, bad));
  view.querySelector('#msg-back').addEventListener('click', showOwnerTools);
  view.querySelector('#msg-recovery').addEventListener('click', () => showRecovery());
  fillRecoveryMessages(view.querySelector('#msg-list'));
  return view;
}

async function fillRecoveryMessages(panel) {
  const body = await api('/ranked/owner/recovery-messages');
  if (!body) {
    panel.innerHTML = `<p class="notice">${esc(t('Could not load the messages. Nothing has been changed.'))}</p>`;
    return;
  }
  const rows = body.messages ?? [];
  if (rows.length === 0) {
    panel.innerHTML = `<p class="lab-intro">${esc(t('No messages.'))}</p>`;
    return;
  }
  panel.innerHTML = `<ul class="approved">${rows.map((row) => `
    <li${row.resolved_at ? ' style="opacity:.6"' : ''}>
      <span class="approved-who">
        <b style="white-space:pre-wrap">${esc(row.body)}</b>
        <small>${esc(row.resolved_at
          ? `${t('received')} ${new Date(row.created_at).toLocaleString()} · ${t('resolved')} ${new Date(row.resolved_at).toLocaleDateString()}`
          : `${t('received')} ${new Date(row.created_at).toLocaleString()}`)}</small>
      </span>
      ${row.resolved_at ? '' : `<button class="ghost" data-resolve="${esc(row.id)}">${esc(t('Mark as resolved'))}</button>`}
    </li>`).join('')}</ul>`;
  panel.querySelectorAll('[data-resolve]').forEach((button) => {
    button.addEventListener('click', async () => {
      button.disabled = true;
      const result = await apiSend('POST', `/ranked/owner/recovery-messages/${button.dataset.resolve}/resolve`);
      if (!result.ok) {
        button.disabled = false;
        button.textContent = result.reason || t('That did not work. Nothing has been changed.');
        return;
      }
      fillRecoveryMessages(panel);
    });
  });
}

async function findForRecovery(view) {
  const button = view.querySelector('#rec-find');
  button.disabled = true;
  const result = await apiSend('POST', '/ranked/owner/recoveries', {
    tag: view.querySelector('#rec-tag').value,
  });
  if (result.ok) {
    showRecoveryCheck(result.data);
    return;
  }
  button.disabled = false;
  const note = view.querySelector('.owner-note') ?? document.createElement('p');
  note.className = 'owner-note notice';
  note.setAttribute('role', 'status');
  note.textContent = result.reason || t('That did not work. Nothing has been changed.');
  button.after(note);
}

// The step that exists to be read, not clicked through. The button says
// what pressing it asserts, rather than "Confirm".
function showRecoveryCheck(request) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(request.username)} · #${esc(request.tag)}</h1>
      <aside class="lab-disclaimer">
        <strong>${esc(t('Check in person first.'))}</strong>
        ${esc(t('Nothing on this screen proves who is standing in front of you. Their username and tag are public, so neither is evidence.'))}
      </aside>
      <p class="lab-intro">${esc(t('Handing over a Quiz Code signs them out everywhere and ends their old one. Their points, badge and history do not change, and this approves nothing for prizes.'))}</p>
      <button id="rec-hand" class="primary">${esc(t('I have checked them in person · show the Quiz Code'))}</button>
      <button id="rec-cancel" class="ghost">${esc(t('Cancel'))}</button>
    </section>
  `, 'profile', () => showRecoveryCheck(request));
  view.querySelector('#rec-cancel').addEventListener('click', () => showRecovery());
  view.querySelector('#rec-hand').addEventListener('click', async () => {
    const button = view.querySelector('#rec-hand');
    button.disabled = true;
    const result = await apiSendOwner('POST', `/ranked/owner/recoveries/${request.id}/handover`);
    if (result.ok) {
      showHandover(result.data);
      return;
    }
    showRecovery(result.reason || t('That did not work. Nothing has been changed.'), true);
  });
  return view;
}

// Shown once. The server keeps only a hash, so leaving this screen is the
// end of it; the copy here is never stored and never fetched again.
function showHandover(handover) {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Owner'))}</p>
      <h1 class="lab-title">${esc(t('Hand this over now'))}</h1>
      <p class="lab-intro">${esc(t('It is shown once and cannot be shown again. Their old Quiz Code and every signed-in device stopped working just now.'))}</p>
      <div class="owner-form">
        <p class="lab-study-meta">${esc(t('New Quiz Code for'))} <b>${esc(handover.username)}</b> · #${esc(handover.tag)}</p>
        <p class="handover-id">${esc(handover.login_id)}</p>
      </div>
      <aside class="lab-disclaimer">${esc(t('Their points, badge and history are unchanged. This did not approve them for prizes and did not restore anything deleted.'))}</aside>
      <button id="rec-done" class="primary">${esc(t('Done'))}</button>
    </section>
  `, 'profile', () => showHandover(handover));
  view.querySelector('#rec-done').addEventListener('click', () => showRecovery());
  return view;
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
  const slot = (row, cls) => !row ? '' : `
    <div class="pslot ${cls}${row.you ? ' pslot-you' : ''}">
      ${row.hat ? '<div class="pcrown" aria-hidden="true">♛</div>' : ''}
      <div class="pdisc${!row.hat && avatarEmoji(row.avatar) ? ' has-avatar' : ''}">${row.hat ? '♛' : (avatarEmoji(row.avatar) || esc(row.username.slice(0, 1).toUpperCase()))}</div>
      <div class="pname">${esc(row.username)}</div>
      <div class="ppts">◆ ${row.points.toLocaleString()}</div>
      <div class="ppillar">${row.place}</div>
    </div>`;
  const podium = hasPodium ? `<div class="podium">
    ${slot(top[1], 'p2')}${slot(top[0], 'p1')}${slot(top[2], 'p3')}
  </div>` : '';
  const listRows = hasPodium ? ordered.slice(3) : ordered;
  const rows = listRows.map((row) => `
    <li class="${row.you ? 'board-you' : ''}${row.hat ? ' board-hat' : (row.tied ? ' board-tied' : '')}">
      <span class="board-place">${row.hat ? '♛' : row.place}</span>
      <span class="board-who">
        <b>${avatarEmoji(row.avatar) ? `<span class="board-avatar" aria-hidden="true">${avatarEmoji(row.avatar)}</span>` : ''}${esc(row.username)}</b>
        <small>#${esc(row.tag)} · ${esc(row.badge)}${row.you ? ` · ${esc(t('your place'))}` : ''}</small>
      </span>
      <b class="board-points">${row.points.toLocaleString()}</b>
      ${row.hat ? `<span class="board-marker board-marker-hat">${esc(t('Hat winner'))}</span>`
        : (row.tied ? `<span class="board-marker">${esc(t(board.prizes_final ? 'Tied on points, no hat' : 'Tied on points'))}</span>` : '')}
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
  const placeChip = board.your_place
    ? `<span class="tab-chip">${esc(t('Your place'))}: ${esc(board.your_place)}</span>` : '';
  const podiumStripe = podium ? `
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Top 3'))}${rows ? '' : placeChip}</p>
      <div class="podium-card">${podium}</div>
    </section>` : '';
  const listStripe = rows ? `
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Standings'))}${placeChip}</p>
      <ol class="board">${rows}</ol>
    </section>` : '';
  // The wrapper is `display: contents` until the desktop breakpoint, so on a
  // phone it changes nothing at all; above it the podium and the standings
  // sit side by side (#273).
  panel.innerHTML = `
    ${preSeasonLine}
    <p class="lab-intro tab-intro">${esc(intro)}</p>
    <div class="board-split${rows ? ' board-split-two' : ''}">
      <div class="board-split-podium">${podiumStripe}</div>
      <div class="board-split-list">${listStripe}</div>
    </div>
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
    open: 'Pre-Season. No start date has been announced for the official season.',
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
  return (SEASON_LINE[season.phase] ?? {})[season.status] ?? '';
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
        <span><strong>${esc(t('Leaderboard'))}</strong><small>${esc(t('See the standings.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
    `;
    panel.querySelector('#ranked-board').addEventListener('click', showLeaderboard);
    return;
  }
  const seasonName = season.phase === 'pre_season' ? t('Pre-Season') : season.label;
  title.textContent = seasonName;
  const closes = season.closes_at ? new Date(season.closes_at).toLocaleString() : null;
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
          <p class="profile-points">${entry.points.toLocaleString()} <i>${esc(t('points'))}</i></p>
        </div>
        <div class="home-obj rk-obj"><span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt=""></div>
      </div>
      ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
      <p class="home-climb-note">${esc(balanceLine(entry))}</p>
      ${open ? `
      <button id="ranked-start" class="primary" type="button">${esc(atCap ? t('Start promotion') : t('Start Ranked quiz'))} <span aria-hidden="true">\u2192</span></button>
      <p class="rk-fine">${esc(t('15 questions, ten seconds each.'))}</p>` : ''}
    </div>
    ${closes ? `<p class="lab-intro">${esc(t(open ? 'Closes' : 'Closed'))}: ${esc(closes)}</p>` : ''}
    ${atCap ? `
    <div class="profile-promo">
      <h2>${esc(t('Promotion available'))}</h2>
      <p>${esc(t('You are at the cap, so promotion is the only Ranked quiz available. It needs a perfect 15 out of 15. Practice is available as usual and never changes these points.'))}</p>
    </div>` : ''}
    <div id="tiebreak-callout" hidden></div>
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Standings'))}</p>
      <button id="ranked-board" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.board}</span>
        <span><strong>${esc(t('Leaderboard'))}</strong><small>${esc(t('See the standings.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
    </section>
    <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Season'))}</p>
      <p class="rk-note">${esc(t(seasonLine(season)))}</p>
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
      <button id="rq-retry-back" class="ghost" type="button">${esc(t('Back to Ranked'))}</button>
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
      { label: 'Back to Ranked', go: showRanked });
    return;
  }
  attempt.startHeartbeat();
  playRankedAttempt(attempt, mode, { correctCount: 0 });
}

async function playRankedAttempt(attempt, mode, tally) {
  stopTick();
  clock = null;
  const current = await attempt.current();
  if (current.status === 410 || current.status === 204 || !current.data) {
    attempt.stop();
    const result = await attempt.result();
    showRankedResult(mode, result.data, tally, { attemptId: attempt.attemptId });
    return;
  }
  const q = current.data;
  const view = labPage(`
    <section class="lab-screen" id="rq-play" data-ranked-music>
      <div class="tb-top">
        <span class="lab-eyebrow" id="rq-count">${esc(t('Question'))} ${q.seq} ${esc(t('of'))} 15</span>
        <div class="rq-ring" id="rq-clock" role="timer" aria-label="${esc(t('seconds'))}"><span id="rq-ring-num"></span></div>
      </div>
      <div class="tb-bar"><i id="rq-bar-fill"></i></div>
      <div id="rq-question"></div>
      <button id="rq-cancel" class="ghost">${esc(t('Cancel this attempt'))}</button>
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
      if (fill) fill.style.width = `${pct}%`;
      if (left <= 0) stopTimer();
    };
    paint();
    timer = setInterval(paint, 200);
  }
  startCountdown(new Date(q.deadline_at).getTime(), 10000);
  view.querySelectorAll('.belt').forEach((button) => button.addEventListener('click', async () => {
    view.querySelectorAll('.belt').forEach((b) => { b.disabled = true; b.classList.toggle('picked', b === button); });
    stopTimer();
    const result = await attempt.answer(q.seq, button.dataset.belt);
    if (!result.ok) { playRankedAttempt(attempt, mode, tally); return; }
    const isRight = Boolean(result.data.correct);
    if (isRight) {
      button.classList.add('belt-correct');
      playCorrectSfx();
    } else {
      button.classList.add('belt-incorrect');
      playIncorrectSfx();
    }
    const nextTally = { correctCount: tally.correctCount + (isRight ? 1 : 0) };
    setTimeout(() => {
      showRankedFeedback(attempt, mode, q, button.dataset.belt, result.data, nextTally);
    }, 550);
  }));
  return view;
}

function showRankedFeedback(attempt, mode, q, chosen, response, tally) {
  stopTick();
  clock = null;
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
    <section class="lab-screen" data-ranked-music>
      <div class="rq-head">
      <div class="rq-mark ${right ? 'good' : 'bad'}" aria-hidden="true">${right ? '\u2713' : '\u2715'}</div>
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
      <button id="rq-next" class="primary" type="button">${esc(t(promoLost ? 'See the result' : 'Next'))}</button>
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
      <div><span>${esc(t('Before this attempt'))}</span><b>${result.points_before.toLocaleString()}</b></div>
      <div class="${result.raw_score < 0 ? 'lost' : ''}"><span>${esc(t(quit ? 'Right before you quit' : 'This attempt'))}</span><b>${result.raw_score >= 0 ? '+' : ''}${result.raw_score.toLocaleString()}</b></div>
      ${quit ? `<div class="lost"><span>${esc(t('Quitting costs'))}</span><b>−${QUIT_PENALTY}</b></div>` : ''}
      ${overflow < 0 ? `<div class="lost"><span>${esc(t('Did not fit in'))} ${esc(result.badge_before)}</span><b>${overflow.toLocaleString()}</b></div>` : ''}
      <div class="total"><span>${esc(t('Your balance now'))}</span><b>${result.points_after.toLocaleString()}</b></div>
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
    <section class="lab-screen">
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
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ranked'))} · ${esc(t(quit ? 'attempt ended' : 'attempt finished'))}</p>
      <div class="home-spot rq-score">
        <h1 class="lab-title rq-score-line"><b>${esc(tally.correctCount)}</b> ${esc(t('of'))} 15 ${esc(t('correct'))}</h1>
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
      <button id="rq-done" class="ghost">${esc(t('Back to Ranked'))}</button>
    </section>
  `, 'ranked', () => showRankedResult(mode, result, tally, { quit, attemptId }));
  view.querySelector('#rq-done').addEventListener('click', showRanked);
  return view;
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
      <button id="rq-done" class="ghost">${esc(t('Back to Ranked'))}</button>
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
      <button id="rq-done" class="ghost">${esc(t('Back to Ranked'))}</button>
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
      <button id="cheer-skip" class="ghost" type="button">${esc(t('Skip animation'))}</button>
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
            <p class="profile-points">${result.points_after.toLocaleString()} ${esc(t('points'))}</p>
            <p class="lab-study-meta">${esc(balanceLine({ badge: result.badge_after, points: result.points_after }))}</p>
          </div>
        </div>
        <p class="lab-intro">${esc(t('Passing sets the new badge’s first point total. Ordinary Ranked quizzes are available again until you reach the next cap.'))}</p>
        <button id="rq-done" class="ghost">${esc(t('Back to Ranked'))}</button>
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
        <div><span>${esc(t('Before this attempt'))}</span><b>${result.points_before.toLocaleString()}</b></div>
        ${mistakes < 0
          ? `<div class="lost"><span>${esc(t('Wrong answers and timeouts'))}</span><b>${mistakes.toLocaleString()}</b></div>`
          : ''}
        ${quit ? `<div class="lost"><span>${esc(t('Quitting costs'))}</span><b>−${QUIT_PENALTY}</b></div>` : ''}
        <div class="total"><span>${esc(t('Your balance now'))}</span><b>${result.points_after.toLocaleString()}</b></div>
      </div>
      ${boardNotice(
          `${(BADGE_CAP[result.badge_before] ?? 0) - result.points_after} ${t('points to the cap again')}`,
          t('Earn them in ordinary Ranked quizzes. Promotion comes back when you reach the cap.'),
        )}
      <button id="rq-done" class="ghost">${esc(t('Back to Ranked'))}</button>
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
          <p class="profile-points">${entry.points.toLocaleString()} ${esc(t('points'))}</p>
          <p class="lab-study-meta">${esc(balanceLine(entry))}</p>
        </div>
      </div>
      <ol class="lab-rules">
        <li>${esc(t('15 questions. You need every one of them right.'))}</li>
        <li>${esc(t('One wrong answer or timeout ends the promotion right there, and that mistake deducts its points.'))}</li>
        <li>${esc(t('Losing points drops you below the cap, so promotion is not available again until you earn them back.'))}</li>
        <li>${esc(t('Passing sets you to'))} ${((BADGE_CAP[entry.badge] ?? entry.points) + 1).toLocaleString()} ${esc(t('points and'))} ${esc(next || entry.badge)}.</li>
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
    box.innerHTML = `
      <button id="tiebreak-go" class="lab-choice lab-choice-quiz" type="button">
        <span class="lab-choice-icon">◇</span>
        <span><strong>${esc(t('You are in a prize tie-break'))}</strong><small>${esc(t(round.restarted
          ? 'The round was restarted after a server outage. Play it again before it closes.'
          : 'A quiz decides the hat. Play once before the round closes.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>`;
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
      <section class="lab-launch" id="launch-callout" hidden aria-live="polite">
        <i aria-hidden="true">!</i>
        <div>
          <h2 id="launch-title">${esc(t('The official season has started'))}</h2>
          <p id="launch-text"></p>
        </div>
      </section>
      <div id="home-tiebreak" hidden></div>
      <div class="home-split">
      <section class="home-stripe home-split-hero">
        <p class="lab-eyebrow">${esc(t('Ranked'))}</p>
        <div class="home-spot">
          <span class="home-pill" id="home-season" hidden></span>
          <h2 class="home-spot-title">${esc(t('Play for the podium'))}</h2>
          <p class="home-spot-desc">${esc(t('15 questions, ten seconds each.'))} ${esc(t('The top 3 win a UPS hat.'))}</p>
          <div class="home-spot-row">
            ${signedIn() ? `
            <div class="home-standing" id="home-ident"><small>${esc(t('Your balance'))}</small><b>…</b></div>
            <button id="home-ranked" class="primary" type="button">${esc(t('Play Ranked'))} <span aria-hidden="true">→</span></button>
            ` : `
            <div class="home-standing"><small>${esc(t('Playing as guest'))}</small><b class="home-standing-note">${esc(t('Sign in to compete in Ranked'))}</b></div>
            <button id="home-signin" class="primary" type="button">${esc(t('Sign in'))} <span aria-hidden="true">→</span></button>
            `}
          </div>
        </div>
      </section>
      ${signedIn() ? '<section class="home-stripe home-split-climb" id="home-climb" hidden></section>' : ''}
      <section class="home-stripe home-split-actions">
        <p class="lab-eyebrow">${esc(t('Practice'))}</p>
        <div class="home-shortcuts">
          <button id="home-practice" class="home-short" type="button">
            <span class="home-short-ic" aria-hidden="true">${ICONS.practice}</span>
            <strong>${esc(t('Practice'))}</strong><small>${esc(t('Practice never changes Ranked points.'))}</small>
          </button>
          <button id="home-study" class="home-short" type="button">
            <span class="home-short-ic" aria-hidden="true">${ICONS.chart}</span>
            <strong>${esc(t('Know the chart'))}</strong><small>${esc(t('Browse every service by state and ZIP range.'))}</small>
          </button>
        </div>
      </section>
      </div>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Your sessions'))}</p>
        <button id="viewlog" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.history}</span>
          <span><strong>${esc(t('Shift log'))}${entries.length ? ` (${entries.length})` : ''}</strong><small>${esc(t('Your practice results saved on this phone.'))}</small></span>
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
  const points = `${entry.points.toLocaleString()} ${t('points')}`;
  const placed = stats && stats.place != null;
  box.innerHTML = `<small>${esc(t(placed ? 'Your standing' : 'Your balance'))}</small><b>${placed ? `#${esc(stats.place)} · ` : ''}${esc(points)}</b>`;

  const climb = view.querySelector('#home-climb');
  if (!climb) return;
  const progress = badgeProgress(entry);
  climb.innerHTML = `
    <p class="lab-eyebrow">${esc(t('Your climb'))}</p>
    <div class="home-climb">
      <div class="home-tiles">
        <div class="home-tile">
          <div class="home-obj"><span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt=""></div>
          <strong>${esc(entry.badge)}</strong><small>${esc(t('Your badge'))}</small>
        </div>
        <div class="home-tile">
          <div class="home-obj"><img class="home-obj-hat" src="assets/prize-hat.svg" alt=""></div>
          <strong>${esc(t('UPS hat'))}</strong><small>${esc(t('Top 3 prize'))}</small>
        </div>
      </div>
      ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
      <p class="home-climb-note">${esc(balanceLine(entry))}</p>
    </div>`;
  climb.hidden = false;
}

// The season-start notice (Decision 15, placement settled 2026-11-15). It
// appears only once a start is confirmed: during Pre-Season there is no
// callout and no invented date. Guests see it too, which is why it reads a
// public endpoint rather than the authenticated one.
async function fillLaunchCallout(view) {
  const box = view.querySelector('#launch-callout');
  if (!box) return;
  let notice;
  try {
    const response = await fetch('/api/ranked/season/notice', { credentials: 'same-origin' });
    if (!response.ok) return;
    notice = await response.json();
  } catch {
    return;  // no backend, as on the static page: show nothing at all
  }
  if (!notice?.started || !notice.started_at) return;
  const started = new Date(notice.started_at).toLocaleDateString();
  const closes = notice.closes_at ? new Date(notice.closes_at).toLocaleDateString() : null;
  // Once the season's end has passed, "has started ... ends on" is stale:
  // nobody can start a quiz for points any more. It does not say points
  // are final: attempts already started have five more minutes.
  if (notice.closes_at && new Date(notice.closes_at).getTime() <= Date.now()) {
    const ran = t('It ran from {start} to {end}.', { start: started, end: closes });
    view.querySelector('#launch-title').textContent = t('The official season has ended');
    view.querySelector('#launch-text').textContent = signedIn()
      ? `${ran} ${t('The leaderboard has the results.')}`
      : ran;
    box.hidden = false;
    return;
  }
  const when = closes
    ? `${t('It started on')} ${started} ${t('and ends on')} ${closes}.`
    : `${t('It started on')} ${started}.`;
  view.querySelector('#launch-text').textContent = signedIn()
    ? `${when} ${t('Everyone began again at 0 points and Iron.')}`
    : `${when} ${t('Log in to play for points this season.')}`;
  box.hidden = false;
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
      <p class="lab-eyebrow">${esc(t('Practice'))}</p>
      <h1 class="lab-title">${esc(t('Quiz yourself'))}</h1>
      <!-- The field and its button were the only ones in the app standing
           straight on the background, with no card and no eyebrow (#332).
           This is the card the sign-in screen uses, which is where a player
           last saw a field and a button together. The way out stays outside
           it: Back is not part of the task the card holds. -->
      <div class="auth-card">
        <label class="field">
          <span>${esc(t('Name or ID (optional)'))}</span>
          <input id="name" type="text" autocomplete="off" autocapitalize="words" placeholder="${esc(t('e.g. J. Rivera'))}" value="${esc(previousName)}">
        </label>
        <button id="begin" class="primary">${esc(t('Pick a test'))}</button>
      </div>
      <button id="back" class="ghost">${esc(t('Back to home'))}</button>
    </section>
  `, 'practice', () => showNameEntry(view.querySelector('#name').value));

  const nameInput = view.querySelector('#name');
  nameInput.focus();

  function begin() {
    const name = nameInput.value.trim();
    showDeckPicker(name);
  }

  view.querySelector('#begin').addEventListener('click', begin);
  nameInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') begin();
  });
  view.querySelector('#back').addEventListener('click', showStart);
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
        <div class="lab-chart-heading"><strong id="service-title"></strong><span>${esc(t('Twilight chart'))}</span></div>
        <p id="chart-count" class="lab-chart-count"></p>
        <label class="lab-search-label" for="chart-search">${esc(t('Find a state or number'))}</label>
        <input id="chart-search" class="lab-chart-search" type="search" placeholder="${esc(t('New Jersey, 079-9, California, 155'))}" value="${esc(studyQuery)}" autocomplete="off">
      </div>
      <div id="chart-rows"></div>
      <aside class="lab-disclaimer"><strong>${esc(t('Made by RJ.'))}</strong> ${esc(t('This study guide does not replace your current worksite chart or UPS training.'))}</aside>
    </section>
  `, 'practice', showStudy);

  const search = view.querySelector('#chart-search');
  const renderRows = () => {
    const section = searchChart(studyService, search.value);
    view.querySelector('#service-title').textContent = language.service(studyService);
    view.querySelector('#chart-count').textContent = t('{shown} of {total} routes shown', { shown: section.main.length + section.exceptions.length, total: section.total });
    view.querySelector('#chart-rows').innerHTML =
      (section.main.length ? `<h2 class="lab-chart-block">${esc(t('Main chart'))}</h2>${section.main.map(chartRow).join('')}` : '') +
      (section.exceptions.length ? `<h2 class="lab-chart-block">${esc(t('Exceptions and special rules'))}</h2>${section.exceptions.map(chartRow).join('')}` : '') ||
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
function deckRow(deck, { index = null, meta, locked = false }) {
  const icon = index === null ? ICONS.quiz : `0${index + 1}`;
  const body = `<span class="lab-choice-icon" aria-hidden="true">${icon}</span>
      <span><strong>${esc(language.deckName(deck))}</strong><small>${esc(language.deckBlurb(deck))}</small><small class="lab-choice-meta">${esc(meta)}</small></span>`;
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
  const entries = log.all();

  const view = labPage(`
    <section class="lab-screen">
      ${backLink('picker-back')}
      <p class="lab-eyebrow">${esc(t('Practice'))}</p>
      <h1 class="lab-title">${esc(t('Pick a test'))}</h1>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Levels · Twilight'))}</p>
        <div class="decks">
          ${DECKS.filter((deck) => deck.questionCount).map((deck, index) => deckRow(deck, {
            index,
            meta: t('{count} questions · {seconds}s each', { count: deck.questionCount, seconds: CARD_SECONDS }),
          })).join('')}
        </div>
      </section>
      <section class="home-stripe">
        <p class="lab-eyebrow">${esc(t('Current quizzes · Twilight'))}</p>
        <div class="decks">
          ${DECKS.filter((deck) => !deck.questionCount).map((deck) => deckRow(deck, {
            locked: !deck.verified,
            meta: deck.verified
              ? t('{count} cards · {seconds}s each', { count: deck.practiceRunSize ?? deck.cards.length, seconds: CARD_SECONDS })
              : t('Not checked against the chart yet'),
          })).join('')}
        </div>
      </section>
      <button id="back" class="ghost">${esc(t('Edit name (optional)'))}</button>
      <button id="main-page" class="ghost">${esc(t('Main page'))}</button>
      ${entries.length ? `<button id="viewlog" class="ghost">${esc(t('Shift log'))} (${entries.length})</button>` : ''}
    </section>
  `, 'practice', () => showDeckPicker(name));

  view.querySelectorAll('.lab-choice[data-deck]').forEach((button) => {
    button.addEventListener('click', () => {
      const deck = deckById(button.dataset.deck);
      if (!deck) return;
      activeDeck = deck;
      run = createRun({ name, cards: selectLevelCards(deck) });
      showCard();
    });
  });
  // The controls below sit under the whole list, out of sight on a phone, so
  // the way back to Practice is also offered before it (#262).
  view.querySelector('#picker-back').addEventListener('click', showPractice);
  view.querySelector('#back').addEventListener('click', () => showNameEntry(name));
  view.querySelector('#main-page').addEventListener('click', showStart);
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
      }, 450);
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
    if (barFill?.style) barFill.style.width = `${Math.max(0, Math.min(100, (remaining / (run.seconds * 1000)) * 100))}%`;

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
        <span class="rq-mark ${right ? 'good' : 'bad'}" aria-hidden="true">${right ? '\u2713' : '\u2715'}</span>
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

  const view = el(`
    <section class="screen">
      <div class="quiz-language">${languageButtons()}</div>
      <div class="score-line">
        <div><div class="big">${summary.correct}/${summary.total}</div><div class="label">${esc(t('Score'))}</div></div>
        <div><div class="big">${elapsed}</div><div class="label">${esc(t('Time'))}</div></div>
      </div>
      <div class="who">${esc(displayName(summary.name))}</div>
      ${summary.deck ? `<div class="deckname">${esc(language.deckLabel(summary.deck))}</div>` : ''}
      ${saved ? '' : `<p class="warn">${esc(t('This result was not saved. This phone is not saving results.'))}</p>`}
      ${summary.missed.length === 0 ? `<p class="clean">${esc(t('No missorts.'))}</p>` : `
        <h2>${esc(t('Missed'))}</h2>
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
  `);
  render(view);
  wireLanguageButtons(view, () => renderResults(summary, saved));

  view.querySelector('#again').addEventListener('click', () => showStart());
  view.querySelector('#viewlog')?.addEventListener('click', showLog);
}

function showLog() {
  const entries = log.all();

  const view = el(`
    <section class="screen">
      <div class="quiz-language">${languageButtons()}</div>
      <h1>${esc(t('Shift log'))}</h1>
      ${entries.length === 0 ? `<p class="sub">${esc(t('Nothing recorded yet.'))}</p>` : `
        <ul class="logl">
          ${entries.map((s) => `
            <li>
              <span class="who">${esc(displayName(s.name))}</span>
              <span class="sc">${esc(s.correct)}/${esc(s.total)}</span>
              <span class="when">${s.deck ? esc(language.deckLabel(s.deck)) + ' &middot; ' : ''}${esc(new Date(s.takenAt).toLocaleString(language.code === 'es' ? 'es-US' : 'en-US'))}</span>
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
  `);
  render(view);
  wireLanguageButtons(view, showLog);

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
        note(t('Preparing the sheet...'));
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
