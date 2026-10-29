import { BELT_STYLE } from './belts.js';
import { SERVICE_LABEL } from './questions.js';
import { DECKS, deckById, deckLabel } from './decks.js';
import { CARD_SECONDS, createRun, currentCard, answerCard, timeoutCard, summarize } from './quiz.js';
import { createClock } from './clock.js';
import { createShiftLog } from './shiftLog.js';
import { saveWorkbook } from './exportFile.js';
import { STUDY_SECTIONS, cardsForStudy } from './study.js';

const app = document.getElementById('app');
const log = createShiftLog(typeof localStorage === 'undefined' ? null : localStorage);

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
    Name: s.name,
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
        Name: s.name,
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
  return SERVICE_LABEL[svc] || svc;
}

function el(html) {
  const template = document.createElement('template');
  template.innerHTML = html.trim();
  return template.content.firstElementChild;
}

function render(node) {
  app.className = node.classList.contains('lab-shell') ? 'lab-page' : 'quiz-page';
  app.replaceChildren(node);
  window.scrollTo(0, 0);
}

function labPage(content, active = 'home') {
  const view = el(`
    <div class="lab-shell">
      <header class="lab-top">
        <div class="lab-brand"><span class="lab-mark">RJ</span> Sort Lab</div>
        <span class="lab-tag">Independent practice</span>
      </header>
      <main class="lab-main">${content}</main>
      <nav class="lab-nav" aria-label="Main navigation">
        <button type="button" data-nav="home" ${active === 'home' ? 'aria-current="page"' : ''}><i aria-hidden="true">⌂</i>Home</button>
        <button type="button" data-nav="study" ${active === 'study' ? 'aria-current="page"' : ''}><i aria-hidden="true">≡</i>Study</button>
        <button type="button" data-nav="quiz" ${active === 'quiz' ? 'aria-current="page"' : ''}><i aria-hidden="true">◉</i>Quiz</button>
      </nav>
    </div>
  `);
  render(view);
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
        <p class="lab-eyebrow">Practice with purpose</p>
        <h1>Test your skills and study the chart.</h1>
        <p>Study one part of the chart, then put it to work in a timed sort quiz.</p>
        <div class="lab-route" aria-hidden="true"><span></span><span></span><span></span><span></span></div>
      </div>
      <h2 class="lab-section-heading">Where do you want to start?</h2>
      <button id="study" class="lab-choice" type="button">
        <span class="lab-choice-icon">01</span>
        <span><strong>Know the chart</strong><small>Study ranges, sort changes, and exceptions in small sections.</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="quiz" class="lab-choice lab-choice-quiz" type="button">
        <span class="lab-choice-icon">02</span>
        <span><strong>Take a quiz</strong><small>Choose a test, beat the clock, and review every missort.</small></span>
        <span class="lab-arrow" aria-hidden="true">→</span>
      </button>
      <button id="viewlog" class="lab-log-link" type="button">Shift log${entries.length ? ` <span>(${entries.length})</span>` : ''} <span aria-hidden="true">→</span></button>
      ${log.available ? '' : '<p class="warn">This phone is not saving results. Each score is shown once and then gone.</p>'}
      <aside class="lab-disclaimer" aria-label="Independent practice notice">
        <strong>Made by RJ.</strong> Not affiliated with or endorsed by UPS. This practice
        does not replace any required UPS test or training. Follow your current worksite chart and instructions.
      </aside>
    </section>
  `, 'home');
  view.querySelector('#study').addEventListener('click', showStudy);
  view.querySelector('#quiz').addEventListener('click', () => showNameEntry());
  view.querySelector('#viewlog').addEventListener('click', showLog);
}

function showNameEntry(notice = '', previousName = '') {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">Ready to practice?</p>
      <h1 class="lab-title">Who is taking the test?</h1>
      <p class="lab-intro">Enter a name or ID so the result can be found in the shift log on this phone.</p>
      ${notice ? `<p class="notice">${esc(notice)}</p>` : ''}
      <label class="field">
        <span>Name or ID</span>
        <input id="name" type="text" autocomplete="off" autocapitalize="words" placeholder="e.g. J. Rivera" value="${esc(previousName)}">
      </label>
      <button id="begin" class="primary">Pick a test</button>
      <button id="back" class="ghost">Back to home</button>
    </section>
  `, 'quiz');

  const nameInput = view.querySelector('#name');
  nameInput.focus();

  function begin() {
    const name = nameInput.value.trim();
    if (!name) {
      showNameEntry('Enter a name or ID first.');
      return;
    }
    showDeckPicker(name);
  }

  view.querySelector('#begin').addEventListener('click', begin);
  nameInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') begin();
  });
  view.querySelector('#back').addEventListener('click', showStart);
}

function studyRows(section, sort) {
  return cardsForStudy(section, sort).map((card) => `
    <article class="lab-study-row">
      <div class="lab-study-meta">${esc(sort === 'Both' ? 'Preload & Twilight' : sort)} &middot; ${esc(serviceName(card.svc))} &middot; ${esc(card.state)}</div>
      <div class="lab-study-answer"><strong>${esc(card.code)}</strong>${beltChip(card.belt, 'lab-belt-chip')}</div>
      <p>${esc(card.why)}</p>
    </article>
  `).join('');
}

function showStudy() {
  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">Learn in small pieces</p>
      <h1 class="lab-title">Know the chart</h1>
      <p class="lab-intro">Selected routes from the current quizzes, grouped for study. Each example names its sort and service.</p>
      <div class="lab-study-sections">
        ${STUDY_SECTIONS.map((section, index) => `
          <details class="lab-study-card" data-study-section="${esc(section.id)}" ${index === 0 ? 'open' : ''}>
            <summary>
              <span class="lab-count">${String(index + 1).padStart(2, '0')}</span>
              <span><strong>${esc(section.title)}</strong><small>${esc(section.subtitle)}</small></span>
            </summary>
            <div class="lab-study-body">
              ${section.sorts.length > 1 ? `<div class="lab-sort-tabs" role="group" aria-label="Choose sort">
                ${section.sorts.map((sort, sortIndex) => `<button type="button" data-study-sort="${esc(sort)}" aria-pressed="${sortIndex === 0}">${esc(sort)}</button>`).join('')}
              </div>` : ''}
              <div class="lab-study-cards">${studyRows(section, section.sorts[0])}</div>
            </div>
          </details>
        `).join('')}
      </div>
      <button id="study-quiz" class="primary">Ready? Take a quiz</button>
      <aside class="lab-disclaimer"><strong>Study guide scope:</strong> these are selected routes from the practice tests, not the full chart. Your current worksite chart and instructions take priority.</aside>
    </section>
  `, 'study');

  view.querySelectorAll('[data-study-sort]').forEach((button) => button.addEventListener('click', () => {
    const card = button.closest('[data-study-section]');
    const section = STUDY_SECTIONS.find((item) => item.id === card.dataset.studySection);
    const sort = button.dataset.studySort;
    card.querySelectorAll('[data-study-sort]').forEach((option) => option.setAttribute('aria-pressed', String(option === button)));
    card.querySelector('.lab-study-cards').innerHTML = studyRows(section, sort);
  }));
  view.querySelector('#study-quiz').addEventListener('click', () => showNameEntry());
}

function showDeckPicker(name) {
  stopTick();
  clock = null;
  const entries = log.all();

  const view = labPage(`
    <section class="lab-screen">
      <p class="lab-eyebrow">Time to practice</p>
      <h1 class="lab-title">Pick a test</h1>
      <p class="lab-intro">${esc(name)} &middot; Four belt choices per card. The clock starts when the first card appears.</p>
      <div class="decks">
        ${DECKS.map((deck) => (deck.verified ? `
          <button class="deckbtn" data-deck="${deck.id}">
            <span class="dname">${esc(deck.name)}<em class="dsort">${esc(deck.sort)}</em></span>
            <span class="dblurb">${esc(deck.blurb)}</span>
            <span class="dmeta">${deck.cards.length} cards &middot; ${CARD_SECONDS}s each</span>
          </button>
        ` : `
          <div class="deckbtn locked">
            <span class="dname">${esc(deck.name)}<em class="dsort">${esc(deck.sort)}</em></span>
            <span class="dblurb">${esc(deck.blurb)}</span>
            <span class="dmeta">Not checked against the chart yet</span>
          </div>
        `)).join('')}
      </div>
      <button id="back" class="ghost">Change name</button>
      ${entries.length ? `<button id="viewlog" class="ghost">Shift log (${entries.length})</button>` : ''}
    </section>
  `, 'quiz');

  view.querySelectorAll('.deckbtn[data-deck]').forEach((button) => {
    button.addEventListener('click', () => {
      const deck = deckById(button.dataset.deck);
      if (!deck) return;
      activeDeck = deck;
      run = createRun({ name, cards: deck.cards });
      showCard();
    });
  });
  view.querySelector('#back').addEventListener('click', () => showNameEntry('', name));
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
      <div class="progress-row">
        <div class="progress">${activeDeck ? esc(activeDeck.sort) + ' &middot; ' : ''}Card ${run.index + 1} of ${run.cards.length}</div>
        <button id="cancel" type="button" class="stopbtn">Cancel</button>
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
        <h1>Test stopped</h1>
        <p class="sub">Nothing is saved until a test is finished, so leaving now records nothing.</p>
        <button id="bail-stay" class="primary">Keep going</button>
        <button id="bail-picker" class="ghost">Pick another test</button>
        <button id="bail-main" class="ghost">Main page</button>
      </div>
    </section>
  `);
  render(view);

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
  const verdict = right ? 'Correct' : response.outcome === 'timeout' ? 'Out of time' : 'Missort';

  const view = el(`
    <section class="screen feedback ${right ? 'good' : 'bad'}">
      <div class="verdict">${verdict}</div>
      <div class="prompt small">
        <div class="p-line">${esc(serviceName(response.svc))} &middot; ${esc(response.state)}</div>
        <div class="p-code">${esc(response.code)}</div>
      </div>
      ${beltChip(response.correctBelt, 'answer')}
      ${right ? '' : `<p class="why">${esc(response.why)}</p>`}
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

  const elapsed = clockText(summary.totalMs);

  const view = el(`
    <section class="screen">
      <div class="score-line">
        <div><div class="big">${summary.correct}/${summary.total}</div><div class="label">Score</div></div>
        <div><div class="big">${elapsed}</div><div class="label">Time</div></div>
      </div>
      <div class="who">${esc(summary.name)}</div>
      ${summary.deck ? `<div class="deckname">${esc(summary.deck)}</div>` : ''}
      ${saved ? '' : '<p class="warn">This result was not saved. This phone is not saving results.</p>'}
      ${summary.missed.length === 0 ? '<p class="clean">No missorts.</p>' : `
        <h2>Missed</h2>
        <ul class="missed">
          ${summary.missed.map((r) => `
            <li>
              <div class="mcard">${esc(serviceName(r.svc))} &middot; ${esc(r.state)} &middot; ${esc(r.code)}</div>
              <div class="mans${r.outcome === 'timeout' ? ' timeout' : ''}">${r.outcome === 'timeout' ? 'ran out of time' : `said ${esc(r.answered)}`} &rarr; <strong>${esc(r.correctBelt)}</strong></div>
              <div class="why">${esc(r.why)}</div>
            </li>
          `).join('')}
        </ul>
      `}
      <button id="again" class="primary">Back to main page</button>
      <button id="viewlog" class="ghost">Shift log</button>
    </section>
  `);
  render(view);

  view.querySelector('#again').addEventListener('click', () => showStart());
  view.querySelector('#viewlog')?.addEventListener('click', showLog);
}

function showLog() {
  const entries = log.all();

  const view = el(`
    <section class="screen">
      <h1>Shift log</h1>
      ${entries.length === 0 ? '<p class="sub">Nothing recorded yet.</p>' : `
        <ul class="logl">
          ${entries.map((s) => `
            <li>
              <span class="who">${esc(s.name)}</span>
              <span class="sc">${s.correct}/${s.total}</span>
              <span class="when">${s.deck ? esc(s.deck) + ' &middot; ' : ''}${esc(new Date(s.takenAt).toLocaleString())}</span>
              ${s.missed.length ? `
                <ul class="logmiss">
                  ${s.missed.map((r) => `
                    <li>
                      <div class="mcard">${esc(serviceName(r.svc))} &middot; ${esc(r.state)} &middot; ${esc(r.code)}</div>
                      <div class="mans${r.outcome === 'timeout' ? ' timeout' : ''}">${r.outcome === 'timeout' ? 'ran out of time' : `said ${esc(r.answered)}`} &rarr; <strong>${esc(r.correctBelt)}</strong></div>
                    </li>
                  `).join('')}
                </ul>
              ` : '<div class="logclean">No missorts.</div>'}
            </li>
          `).join('')}
        </ul>
      `}
      <button id="back" class="primary">Main page</button>
      ${entries.length ? '<button id="export" class="ghost" hidden>Export to Excel</button>' : ''}
      <p id="exportnote" class="exportnote" hidden></p>
      ${entries.length ? '<button id="clear" class="ghost danger">Clear log</button>' : ''}
    </section>
  `);
  render(view);

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
        note('Preparing the sheet...');
        try {
          const workbook = buildWorkbook(log.all());
          const stamp = new Date().toISOString().slice(0, 10);
          const result = await saveWorkbook(workbook, `sort-test-log-${stamp}.xlsx`, downloads);
          note(result.status === 'saved' ? 'Saved.' : 'Sent.');
        } catch (error) {
          const code = error && error.code;
          if (code === 'declined') note('');
          else if (code === 'rate_limited') note('Already asking. Try again in a moment.', true);
          else if (code === 'too_large') note('The log is too big to send. Clear it and start a fresh shift.', true);
          else note('This phone could not save the file.', true);
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
      clearButton.textContent = 'Tap again to erase every result';
      armedTimer = setTimeout(() => {
        armed = false;
        clearButton.textContent = 'Clear log';
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
