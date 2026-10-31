import { BELT_STYLE } from './belts.js';
import { SERVICE_LABEL } from './questions.js';
import { DECKS, deckById, deckLabel } from './decks.js';
import { CARD_SECONDS, createRun, currentCard, answerCard, timeoutCard, summarize } from './quiz.js';
import { createClock } from './clock.js';
import { createShiftLog } from './shiftLog.js';
import { saveWorkbook } from './exportFile.js';
import { CHART, searchChart } from './study.js';
import { selectLevelCards } from './levels.js';
import { createLanguage } from './i18n.js';

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
        Service: serviceName(r.svc),
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

function serviceName(svc) {
  return language.service(SERVICE_LABEL[svc] || svc);
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
  window.scrollTo(0, 0);
}

function languageButtons() {
  return `<div class="lab-language" role="group" aria-label="Language / Idioma">
    <button type="button" data-language="en" aria-label="English" aria-pressed="${language.code === 'en'}"><span aria-hidden="true">🇺🇸</span><span>EN</span></button>
    <button type="button" data-language="es" aria-label="Español" aria-pressed="${language.code === 'es'}"><span aria-hidden="true">🇪🇸</span><span>ES</span></button>
  </div>`;
}

function wireLanguageButtons(view, rerender) {
  view.querySelectorAll('[data-language]').forEach((button) => button.addEventListener('click', () => {
    if (language.code === button.dataset.language) return;
    language.set(button.dataset.language);
    rerender();
  }));
}

function labPage(content, active = 'home', rerender = showStart) {
  const view = el(`
    <div class="lab-shell">
      <header class="lab-top">
        <div class="lab-top-row">
          <div class="lab-brand"><span class="lab-mark">RJ</span> Sort Lab</div>
          ${languageButtons()}
        </div>
        <div class="lab-site">UPS Saddle Brook <span aria-hidden="true">·</span> Twilight</div>
        <span class="lab-tag">${esc(t('Independent practice'))}</span>
      </header>
      <main class="lab-main">${content}</main>
      <nav class="lab-nav" aria-label="${esc(t('Main navigation'))}">
        <button type="button" data-nav="home" ${active === 'home' ? 'aria-current="page"' : ''}><i aria-hidden="true">⌂</i>${esc(t('Home'))}</button>
        <button type="button" data-nav="study" ${active === 'study' ? 'aria-current="page"' : ''}><i aria-hidden="true">≡</i>${esc(t('Study'))}</button>
        <button type="button" data-nav="quiz" ${active === 'quiz' ? 'aria-current="page"' : ''}><i aria-hidden="true">◉</i>${esc(t('Quiz'))}</button>
      </nav>
    </div>
  `);
  render(view);
  wireLanguageButtons(view, rerender);
  view.querySelectorAll('[data-nav]').forEach((button) => button.addEventListener('click', () => {
    if (button.dataset.nav === active) return;
    if (button.dataset.nav === 'study') showStudy();
    else if (button.dataset.nav === 'quiz') showNameEntry();
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
  return `<div class="${className}" style="background:${style.bg};color:${style.fg}">${belt}</div>`;
}

function showStart() {
  clearTimeout(feedbackTimer);
  feedbackTimer = null;
  resumeTick = null;
  stopTick();
  clock = null;
  const entries = log.all();

  const view = labPage(`
    <section class="lab-screen">
      <div class="lab-hero">
        <div class="lab-hero-copy">
          <p class="lab-eyebrow">${esc(t('Sort practice, one route at a time'))}</p>
          <h1>${esc(t('Practice'))}<br>${esc(t('the chart.'))}</h1>
          <p>${esc(t('Learn the belt. Then test your recall.'))}</p>
        </div>
        <img class="lab-mascot" src="assets/parcel-buddy.jpg" alt="${language.code === 'es' ? 'Personaje azul sonriente con una caja de cartón' : 'Smiling blue character holding a cardboard package'}">
      </div>
      <h2 class="lab-section-heading">${esc(t('Where do you want to start?'))}</h2>
      <button id="study" class="lab-choice" type="button">
        <span class="lab-choice-icon">01</span>
        <span><strong>${esc(t('Know the chart'))}</strong><small>${esc(t('Browse every service by state and ZIP range.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="quiz" class="lab-choice lab-choice-quiz" type="button">
        <span class="lab-choice-icon">02</span>
        <span><strong>${esc(t('Take a quiz'))}</strong><small>${esc(t('Start with Ground, then build up to the full chart.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="viewlog" class="lab-log-link" type="button">${esc(t('Shift log'))}${entries.length ? ` <span>(${entries.length})</span>` : ''} <span aria-hidden="true">→</span></button>
      ${log.available ? '' : `<p class="warn">${esc(t('This phone is not saving results. Each score is shown once and then gone.'))}</p>`}
      <aside class="lab-disclaimer" aria-label="${esc(t('Independent practice'))}">
        <strong>${esc(t('Made by RJ.'))}</strong> ${esc(t('Not affiliated with or endorsed by UPS. This practice does not replace any required UPS test or training. Follow your current worksite chart and instructions.'))}
      </aside>
    </section>
  `, 'home');
  view.querySelector('#study').addEventListener('click', showStudy);
  view.querySelector('#quiz').addEventListener('click', () => showNameEntry());
  view.querySelector('#viewlog').addEventListener('click', showLog);
}

function showNameEntry(previousName = '') {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Ready to practice?'))}</p>
      <h1 class="lab-title">${esc(t('Who is taking the test?'))}</h1>
      <p class="lab-intro">${esc(t('A name or ID is optional. If you leave it blank, your result appears as Guest in the shift log on this phone.'))}</p>
      <label class="field">
        <span>${esc(t('Name or ID (optional)'))}</span>
        <input id="name" type="text" autocomplete="off" autocapitalize="words" placeholder="${esc(t('e.g. J. Rivera'))}" value="${esc(previousName)}">
      </label>
      <button id="begin" class="primary">${esc(t('Pick a test'))}</button>
      <button id="back" class="ghost">${esc(t('Back to home'))}</button>
    </section>
  `, 'quiz', () => showNameEntry(view.querySelector('#name').value));

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
      <strong>${esc(code)}</strong>${detail ? `<small>${esc(language.detail(detail))}</small>` : ''}</div>
    ${beltChip(belt, 'lab-belt-chip')}
  </div>`;
}

function showStudy() {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Twilight study guide'))}</p>
      <h1 class="lab-title">${esc(t('Know the chart.'))}</h1>
      <p class="lab-intro">${esc(t('Choose a service, then read its states, ZIP ranges, belts, and exceptions.'))}</p>
      <div class="lab-service-tabs" role="group" aria-label="${esc(t('Choose service'))}">
        ${Object.keys(CHART).map((service) => `<button type="button" data-service="${esc(service)}" aria-pressed="${service === studyService}">${esc(language.service(service))}</button>`).join('')}
      </div>
      <div class="lab-chart-heading"><strong id="service-title"></strong><span>${esc(t('Twilight chart'))}</span></div>
      <p id="chart-count" class="lab-chart-count"></p>
      <label class="lab-search-label" for="chart-search">${esc(t('Find a state or number'))}</label>
      <input id="chart-search" class="lab-chart-search" type="search" placeholder="${esc(t('New Jersey, 079-9, California, 155'))}" value="${esc(studyQuery)}" autocomplete="off">
      <div id="chart-rows"></div>
      <aside class="lab-disclaimer"><strong>${esc(t('Made by RJ.'))}</strong> ${esc(t('This study guide does not replace your current worksite chart or UPS training.'))}</aside>
    </section>
  `, 'study', showStudy);

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

function showDeckPicker(name) {
  stopTick();
  clock = null;
  const entries = log.all();

  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">${esc(t('Time to practice'))}</p>
      <h1 class="lab-title">${esc(t('Pick a test'))}</h1>
      <p class="lab-intro">${esc(t('{name} · Four belt choices per card. The clock starts when the first card appears.', { name: displayName(name) }))}</p>
      <h2 class="lab-picker-heading">${esc(t('New challenge levels'))}</h2>
      <div class="decks">
        ${DECKS.filter((deck) => deck.questionCount).map((deck, index) => `
          <button class="deckbtn" data-deck="${deck.id}">
            <span class="dname">0${index + 1} &middot; ${esc(language.deckName(deck))}<em class="dsort">Twilight</em></span>
            <span class="dblurb">${esc(language.deckBlurb(deck))}</span>
            <span class="dmeta">${esc(t('{count} questions · {seconds}s each', { count: deck.questionCount, seconds: CARD_SECONDS }))}</span>
          </button>
        `).join('')}
      </div>
      <h2 class="lab-picker-heading">${esc(t('Current quizzes · Twilight'))}</h2>
      <div class="decks">
        ${DECKS.filter((deck) => !deck.questionCount).map((deck) => (deck.verified ? `
          <button class="deckbtn" data-deck="${deck.id}">
            <span class="dname">${esc(language.deckName(deck))}<em class="dsort">${esc(deck.sort)}</em></span>
            <span class="dblurb">${esc(language.deckBlurb(deck))}</span>
            <span class="dmeta">${esc(t('{count} cards · {seconds}s each', { count: deck.cards.length, seconds: CARD_SECONDS }))}</span>
          </button>
        ` : `
          <div class="deckbtn locked">
            <span class="dname">${esc(language.deckName(deck))}<em class="dsort">${esc(deck.sort)}</em></span>
            <span class="dblurb">${esc(language.deckBlurb(deck))}</span>
            <span class="dmeta">${esc(t('Not checked against the chart yet'))}</span>
          </div>
        `)).join('')}
      </div>
      <button id="back" class="ghost">${esc(t('Edit name (optional)'))}</button>
      <button id="main-page" class="ghost">${esc(t('Main page'))}</button>
      ${entries.length ? `<button id="viewlog" class="ghost">${esc(t('Shift log'))} (${entries.length})</button>` : ''}
    </section>
  `, 'quiz', () => showDeckPicker(name));

  view.querySelectorAll('.deckbtn[data-deck]').forEach((button) => {
    button.addEventListener('click', () => {
      const deck = deckById(button.dataset.deck);
      if (!deck) return;
      activeDeck = deck;
      run = createRun({ name, cards: selectLevelCards(deck) });
      showCard();
    });
  });
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
    <section class="screen card-screen">
      <div class="card-header">
        <div class="progress-row">
          <div class="progress">${activeDeck ? esc(activeDeck.sort) + ' &middot; ' : ''}${esc(t('Card {current} of {total}', { current: run.index + 1, total: run.cards.length }))}</div>
          ${languageButtons()}
        </div>
        <button id="cancel" type="button" class="stopbtn">${esc(t('Cancel'))}</button>
      </div>
      <div class="prompt">
        <div class="ring" id="ring"><i id="ringNum">${run.seconds}</i></div>
        <div class="p-line">${esc(serviceName(card.svc))} &middot; ${esc(card.state)}</div>
        <div class="p-code">${esc(card.code)}</div>
      </div>
      <div class="options">
        ${options.map((belt) => {
          const style = BELT_STYLE[belt];
          return `<button class="belt" data-belt="${belt}" style="background:${style.bg};color:${style.fg}">${belt}</button>`;
        }).join('')}
      </div>
      <div class="bail" id="bail" hidden>
        <h1>${esc(t('Test stopped'))}</h1>
        <p class="sub">${esc(t('Nothing is saved until a test is finished, so leaving now records nothing.'))}</p>
        <button id="bail-stay" class="primary">${esc(t('Keep going'))}</button>
        <button id="bail-picker" class="ghost">${esc(t('Pick another test'))}</button>
        <button id="bail-main" class="ghost">${esc(t('Main page'))}</button>
      </div>
    </section>
  `);
  render(view);
  view.querySelectorAll('[data-language]').forEach((button) => button.addEventListener('click', () => {
    if (language.code === button.dataset.language) return;
    language.set(button.dataset.language);
    document.documentElement.lang = language.code;
    view.querySelectorAll('[data-language]').forEach((option) => option.setAttribute('aria-pressed', String(option.dataset.language === language.code)));
    view.querySelector('.progress').textContent = `${activeDeck ? `${activeDeck.sort} · ` : ''}${t('Card {current} of {total}', { current: run.index + 1, total: run.cards.length })}`;
    view.querySelector('#cancel').textContent = t('Cancel');
    view.querySelector('.p-line').textContent = `${serviceName(card.svc)} · ${card.state}`;
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

  // window.confirm is blocked in the artifact's sandboxed frame — it returns
  // false without ever showing a dialog, which made the old Cancel do nothing.
  // The panel below is the confirmation instead.
  const bail = view.querySelector('#bail');
  const sorterName = run.name;

  view.querySelector('#cancel').addEventListener('click', () => {
    if (run.finished || run.index !== cardIndex || !bail.hidden) return;
    bailOpen = true;
    clock.pause();
    stopTick();
    bail.hidden = false;
  });

  view.querySelector('#bail-stay').addEventListener('click', () => {
    bailOpen = false;
    bail.hidden = true;
    clock.resume();
    resumeTick?.();
  });

  view.querySelector('#bail-picker').addEventListener('click', () => {
    leaveRun();
    showDeckPicker(sorterName);
  });

  view.querySelector('#bail-main').addEventListener('click', () => {
    leaveRun();
    showStart();
  });

  view.querySelectorAll('.belt').forEach((button) => {
    button.addEventListener('click', () => {
      if (run.finished || run.index !== cardIndex) return;
      stopTick();
      showFeedback(answerCard(run, button.dataset.belt, clock.elapsed()));
    });
  });

  function tick() {
    if (run.finished || run.index !== cardIndex) {
      stopTick();
      return;
    }

    const remaining = clock.remaining();
    const pct = (remaining / durationMs) * 100;
    ring.style.background = `conic-gradient(var(--accent) 0 ${pct}%, var(--sunk) ${pct}% 100%)`;
    ringNum.textContent = Math.ceil(remaining / 1000);

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

  const right = response.outcome === 'correct';
  const verdict = t(right ? 'Correct' : response.outcome === 'timeout' ? 'Out of time' : 'Missort');

  const view = el(`
    <section class="screen feedback ${right ? 'good' : 'bad'}">
      <div class="verdict">${verdict}</div>
      <div class="prompt small">
        <div class="p-line">${esc(serviceName(response.svc))} &middot; ${esc(response.state)}</div>
        <div class="p-code">${esc(response.code)}</div>
      </div>
      ${beltChip(response.correctBelt, 'answer')}
      ${right ? '' : `<p class="why">${esc(language.explanation(response))}</p>`}
    </section>
  `);
  render(view);

  feedbackTimer = setTimeout(() => {
    feedbackTimer = null;
    if (run.finished) showResults();
    else showCard();
  }, right ? 900 : 2400);
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
              <div class="mcard">${esc(serviceName(r.svc))} &middot; ${esc(r.state)} &middot; ${esc(r.code)}</div>
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
              <span class="sc">${s.correct}/${s.total}</span>
              <span class="when">${s.deck ? esc(language.deckLabel(s.deck)) + ' &middot; ' : ''}${esc(new Date(s.takenAt).toLocaleString(language.code === 'es' ? 'es-US' : 'en-US'))}</span>
              ${s.missed.length ? `
                <ul class="logmiss">
                  ${s.missed.map((r) => `
                    <li>
                      <div class="mcard">${esc(serviceName(r.svc))} &middot; ${esc(r.state)} &middot; ${esc(r.code)}</div>
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

  if (exportButton && canBuildWorkbook()) {
    getDownloads().then((downloads) => {
      exportButton.hidden = false;

      exportButton.addEventListener('click', async () => {
        exportButton.disabled = true;
        note(t('Preparing the sheet...'));
        try {
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

showStart();
