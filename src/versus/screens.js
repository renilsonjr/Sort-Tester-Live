// Versus -- the screens. A 1 vs 1 frame over the two mini-games that
// already exist: nothing here asks a new question or deals a new package.
// The quiz duel draws from the Ranked bank on the server; the handler duel
// mounts the Handler's own screen with the match's shared seed.
//
// Everything the app already owns arrives through `deps` -- the page
// shell, the translator, the belt buttons, the sounds -- so this module
// draws Versus and nothing else, and app.js stays the one place that
// knows how a screen gets on the page.
import { POLL_MS, REVIEW_MS, normalizeCode, tugShare, standing } from './logic.js';

const QUESTION_MS = 5000;

export function createVersusScreens(deps) {
  const {
    labPage, t, esc, ICONS, client, language, avatarEmoji,
    beltButton, destinationLine, rqChip, backLink,
    playCorrectSfx, playIncorrectSfx, mountHandlerDuel,
  } = deps;

  const GAME_NAME = { quiz: 'Quiz duel', handler: 'Handler duel' };
  const gameIcon = game => (game === 'handler' ? ICONS.handlerSolid : ICONS.quizSolid);

  // One poll per screen. It stops itself the moment its screen is no
  // longer the one on the page, so no way out of a screen can leave a
  // timer asking the server about a room nobody is looking at.
  function every(view, work) {
    let busy = false;
    const timer = setInterval(async () => {
      if (!view.isConnected) { clearInterval(timer); return; }
      if (busy) return;
      busy = true;
      try { await work(); } finally { busy = false; }
    }, POLL_MS);
    return () => clearInterval(timer);
  }

  function face(player) {
    const icon = avatarEmoji(player.avatar);
    return `<span class="vs-face" aria-hidden="true">${icon || esc(String(player.username).slice(0, 1).toUpperCase())}</span>`;
  }

  // ------------------------------------------------------------- the lobby

  function showVersus(message = null) {
    const view = labPage(`
      <section class="lab-screen screen-versus">
        <p class="lab-eyebrow">${esc(t('1 vs 1'))}</p>
        <h1 class="lab-title tab-title">${esc(t('Versus'))}</h1>
        ${message ? `<p class="notice" role="status">${esc(message)}</p>` : ''}
        <section class="home-stripe">
          <p class="lab-eyebrow">${esc(t('Create a room'))}</p>
          <div class="home-shortcuts">
            <button class="home-short" type="button" data-vs-create="quiz">
              <span class="home-short-ic is-solid" aria-hidden="true">${ICONS.quizSolid}</span>
              <strong>${esc(t('Quiz duel'))}</strong>
            </button>
            <button class="home-short" type="button" data-vs-create="handler">
              <span class="home-short-ic is-solid" aria-hidden="true">${ICONS.handlerSolid}</span>
              <strong>${esc(t('Handler duel'))}</strong>
            </button>
          </div>
        </section>
        <section class="home-stripe">
          <p class="lab-eyebrow">${esc(t('Join a room'))}</p>
          <form id="vs-join" class="vs-join" novalidate>
            <label class="field">
              <span>${esc(t('Room code'))}</span>
              <input id="vs-code" type="text" inputmode="text" autocomplete="off" autocapitalize="characters" spellcheck="false" maxlength="10" placeholder="HAT-42">
            </label>
            <p class="notice" id="vs-error" role="alert" hidden></p>
            <button class="primary" type="submit">${esc(t('Join'))}</button>
          </form>
        </section>
        <section class="home-stripe">
          <button id="vs-board" class="lab-choice" type="button">
            <span class="lab-choice-icon" aria-hidden="true">${ICONS.board}</span>
            <span><strong>${esc(t('Versus leaderboard'))}</strong></span>
            <span class="lab-arrow" aria-hidden="true">→</span>
          </button>
        </section>
      </section>
    `, 'versus', () => showVersus(message));
    const error = view.querySelector('#vs-error');
    const fail = text => { error.textContent = text; error.hidden = false; };
    view.querySelectorAll('[data-vs-create]').forEach(button => button.addEventListener('click', async () => {
      view.querySelectorAll('[data-vs-create]').forEach(b => { b.disabled = true; });
      const answer = await client.createRoom(button.dataset.vsCreate);
      if (!answer.ok) {
        view.querySelectorAll('[data-vs-create]').forEach(b => { b.disabled = false; });
        fail(t('The room could not be opened. Try again in a moment.'));
        return;
      }
      showRoom(answer.data);
    }));
    view.querySelector('#vs-join').addEventListener('submit', async event => {
      event.preventDefault();
      const code = normalizeCode(view.querySelector('#vs-code').value);
      if (!code) { fail(t('Type the room code first.')); return; }
      const answer = await client.joinRoom(code);
      if (!answer.ok) {
        fail(answer.status === 404
          ? t('No room is waiting with that code. Check it and try again.')
          : t('Could not join the room. Try again in a moment.'));
        return;
      }
      showRoom(answer.data);
    });
    view.querySelector('#vs-board').addEventListener('click', showBoard);
    return view;
  }

  // -------------------------------------------------------------- the room

  function seatRow(player, label) {
    if (!player) {
      return `<li class="vs-seat vs-seat-empty"><span class="vs-face" aria-hidden="true">?</span><span class="vs-seat-name">${esc(t('Waiting for a player'))}</span></li>`;
    }
    return `<li class="vs-seat">${face(player)}<span class="vs-seat-name">${esc(player.username)}<small>#${esc(player.tag)}</small></span>${label ? `<em>${esc(label)}</em>` : ''}</li>`;
  }

  function showRoom(room) {
    if (room.match_id) { openMatch(room.match_id); return null; }
    if (room.state === 'closed') { showVersus(t('That room has closed.')); return null; }
    const full = room.state === 'full';
    const view = labPage(`
      <section class="lab-screen screen-versus">
        <p class="lab-eyebrow">${esc(t(GAME_NAME[room.game]))}</p>
        <h1 class="lab-title">${esc(t(full ? 'Both players are in' : 'Share this code'))}</h1>
        <div class="vs-room home-spot">
          <span class="home-short-ic is-solid" aria-hidden="true">${gameIcon(room.game)}</span>
          <p class="vs-code" aria-label="${esc(t('Room code'))}">${esc(room.code)}</p>
        </div>
        <ul class="vs-seats">
          ${seatRow(room.host, room.you_are_host ? t('You') : null)}
          ${seatRow(room.guest, room.guest && !room.you_are_host ? t('You') : null)}
        </ul>
        ${full && room.you_are_host ? `<button id="vs-start" class="primary" type="button">${esc(t('Start the duel'))}</button>` : ''}
        ${full && !room.you_are_host ? `<p class="lab-intro" role="status">${esc(t('Waiting for {name} to start.', { name: room.host.username }))}</p>` : ''}
        <p class="notice" id="vs-error" role="alert" hidden></p>
        <button id="vs-leave" class="ghost" type="button">${esc(t('Leave room'))}</button>
      </section>
    `, 'versus', () => showRoom(room));
    const shape = current => `${current.state}|${current.guest?.username ?? ''}|${current.match_id ?? ''}`;
    every(view, async () => {
      const answer = await client.readRoom(room.id);
      if (!view.isConnected) return;
      if (answer.status === 404) { showVersus(t('That room has closed.')); return; }
      if (!answer.ok) return;
      // Redrawn only when something a player can see has changed, so the
      // screen is not rebuilt under a thumb once a second.
      if (shape(answer.data) !== shape(room)) showRoom(answer.data);
    });
    view.querySelector('#vs-start')?.addEventListener('click', async () => {
      view.querySelector('#vs-start').disabled = true;
      const answer = await client.startMatch(room.id);
      if (!answer.ok) {
        view.querySelector('#vs-start').disabled = false;
        const error = view.querySelector('#vs-error');
        error.textContent = t('The duel could not start. Try again in a moment.');
        error.hidden = false;
        return;
      }
      showMatch(answer.data);
    });
    view.querySelector('#vs-leave').addEventListener('click', async () => {
      await client.leaveRoom(room.id);
      showVersus();
    });
    return view;
  }

  // ------------------------------------------------------------ the tug bar

  function tugMarkup(state) {
    return `
      <div class="vs-tug-wrap">
        <div class="vs-tug-names" aria-hidden="true">
          <span class="vs-tug-you"><b>${esc(state.you.username)}</b> <span data-vs-you>0</span></span>
          <span class="vs-tug-opp"><span data-vs-opp>0</span> <b>${esc(state.opponent.username)}</b></span>
        </div>
        <div class="vs-tug" data-vs-tug role="img"><i class="vs-tug-fill" data-vs-fill></i></div>
        <p class="vs-tug-note" data-vs-note role="status"></p>
      </div>`;
  }

  function paintTug(view, state) {
    const fill = view.querySelector('[data-vs-fill]');
    if (!fill) return;
    const share = tugShare(state.you.score, state.opponent.score);
    fill.style.transform = `scaleX(${share / 100})`;
    view.querySelector('[data-vs-you]').textContent = language.number(state.you.score);
    view.querySelector('[data-vs-opp]').textContent = language.number(state.opponent.score);
    const where = standing(state.you.score, state.opponent.score);
    const note = where.key === 'level'
      ? t('Level')
      : where.key === 'ahead'
        ? t('You are ahead by {n}', { n: language.number(where.margin) })
        : t('You are behind by {n}', { n: language.number(where.margin) });
    const noteNode = view.querySelector('[data-vs-note]');
    if (noteNode.textContent !== note) noteNode.textContent = note;
    view.querySelector('[data-vs-tug]').setAttribute('aria-label',
      `${state.you.username} ${state.you.score}, ${state.opponent.username} ${state.opponent.score}`);
  }

  // The poll behind every live duel screen: repaint the bar, and leave for
  // the result the moment the server says the duel is over.
  function followMatch(view, matchId) {
    return every(view, async () => {
      const answer = await client.readMatch(matchId);
      if (!view.isConnected || !answer.ok) return;
      if (answer.data.state === 'finished') { showResult(answer.data); return; }
      paintTug(view, answer.data);
    });
  }

  // Two shapes of the same control. The quiz duel carries it as a pill
  // beside the clock, because a full-width button under the belts is where
  // a racing thumb lands -- the same trap #504 took off the Ranked
  // question. The Handler duel has no belts under it and keeps the wide
  // button it had.
  function leaveButton({ compact = false } = {}) {
    return compact
      ? `<button id="vs-forfeit" class="ghost rq-quit" type="button">${esc(t('Leave'))}</button>`
      : `<button id="vs-forfeit" class="ghost" type="button">${esc(t('Leave duel'))}</button>`;
  }

  // Leaving costs the duel, so it takes two presses. The first says what it
  // will cost: in the warning line when the screen has one, so the pill
  // beside the clock keeps its size, and in the button itself otherwise.
  function wireLeave(view, matchId) {
    const button = view.querySelector('#vs-forfeit');
    if (!button) return;
    const warn = view.querySelector('[data-vs-warn]');
    let armed = false;
    button.addEventListener('click', async () => {
      if (!armed) {
        armed = true;
        const said = t('Press again to leave. Leaving counts as a loss.');
        if (warn) { warn.textContent = said; warn.hidden = false; }
        else button.textContent = said;
        button.classList.add('vs-armed');
        return;
      }
      button.disabled = true;
      await client.forfeit(matchId);
      const answer = await client.readMatch(matchId);
      if (answer.ok && answer.data.state === 'finished') showResult(answer.data);
      else showVersus(t('You left the duel.'));
    });
  }

  // ------------------------------------------------------------- the match

  async function openMatch(matchId) {
    const answer = await client.readMatch(matchId);
    if (!answer.ok) { showVersus(t('That duel could not be found.')); return; }
    showMatch(answer.data);
  }

  function showMatch(state) {
    if (state.state === 'finished') { showResult(state); return; }
    if (state.game === 'handler') playHandler(state);
    else playQuiz(state);
  }

  async function playQuiz(state) {
    if (state.you.finished) { showWaiting(state); return; }
    const current = await client.question(state.id);
    if (!current.ok || !current.data || current.data.seq === undefined) {
      // No live question: this player is done, or the duel ended under them.
      const latest = await client.readMatch(state.id);
      if (latest.ok && latest.data.state === 'finished') showResult(latest.data);
      else showWaiting(latest.ok ? latest.data : state);
      return;
    }
    const q = current.data;
    const where = destinationLine(q);
    const view = labPage(`
      <section class="lab-screen screen-versus" data-attempt-live>
        ${tugMarkup(state)}
        <div class="tb-top">
          <span class="lab-eyebrow">${esc(t('Question'))} ${q.seq} ${esc(t('of'))} ${q.of}</span>
          <div class="rq-top-end">
            ${leaveButton({ compact: true })}
            <div class="rq-ring" id="vs-clock" role="timer" aria-label="${esc(t('seconds'))}"><span id="vs-ring-num"></span></div>
          </div>
        </div>
        <p class="notice vs-leave-warn" data-vs-warn role="alert" hidden></p>
        <div id="vs-question">
          <div class="rq-prompt rq-route home-spot">
            <span class="home-pill">${esc(t('Quiz duel'))}</span>
            <p class="rq-service">${esc(where.service)}</p>
            <p class="rq-code">${esc(where.code)}</p>
          </div>
          <p class="lab-eyebrow rq-cue">${esc(t('Where does this go?'))}</p>
          <div class="belts" role="group" aria-label="${esc(t('Choose a belt'))}">
            ${(q.options || []).map(belt => beltButton(belt)).join('')}
          </div>
        </div>
        <div id="vs-review" hidden></div>
      </section>
    `, 'versus', () => playQuiz(state));
    paintTug(view, state);
    followMatch(view, state.id);
    wireLeave(view, state.id);

    const belts = [...view.querySelectorAll('.belt')];
    let over = false;
    let timer = null;
    const stopTimer = () => { if (timer) clearInterval(timer); timer = null; };
    const deadline = new Date(q.deadline_at).getTime();
    const paint = () => {
      if (!view.isConnected) { stopTimer(); return; }
      const left = deadline - Date.now();
      const ring = view.querySelector('#vs-clock');
      view.querySelector('#vs-ring-num').textContent = Math.max(0, Math.ceil(left / 1000));
      ring.style.setProperty('--pct', Math.max(0, Math.min(100, (left / QUESTION_MS) * 100)));
      ring.classList.toggle('low', left <= 2000);
      if (left <= 0) { stopTimer(); submit(null, null); }
    };

    async function submit(choice, button) {
      if (over) return;
      over = true;
      stopTimer();
      belts.forEach(b => { b.disabled = true; b.classList.toggle('picked', b === button); });
      const result = await client.answer(state.id, q.seq, choice);
      if (!view.isConnected) return;
      if (!result.ok) { openMatch(state.id); return; }
      const right = Boolean(result.data.correct);
      if (button) button.classList.add(right ? 'belt-correct' : 'belt-incorrect');
      if (right) playCorrectSfx(); else playIncorrectSfx();
      // The review replaces the belts in place: the bar above keeps moving,
      // and the right belt is named whether the answer was right or not.
      const review = view.querySelector('#vs-review');
      const verdict = right ? t('Correct') : (choice === null ? t('Time ran out') : t('Review this route'));
      review.innerHTML = `
        <div class="rq-head">
          <div class="rq-mark ${right ? 'good' : 'bad'}" aria-hidden="true">${right ? ICONS.verdictGood : ICONS.verdictBad}</div>
          <div class="rq-head-text">
            <p class="lab-title rq-verdict ${right ? 'good' : 'bad'}">${esc(verdict)}</p>
            <p class="rq-worth ${right ? 'good' : 'bad'}">+${language.number(result.data.gained)} ${esc(t('points'))}</p>
          </div>
        </div>
        <div class="rq-cmp">
          ${!right && choice !== null ? `<div><span>${esc(t('Your choice'))}</span>${rqChip(choice)}</div>` : ''}
          <div><span>${esc(t('Correct belt'))}</span>${rqChip(result.data.correct_belt)}</div>
        </div>`;
      view.querySelector('.rq-cue').hidden = true;
      view.querySelector('.belts').hidden = true;
      review.hidden = false;
      setTimeout(() => {
        if (!view.isConnected) return;
        if (result.data.finished) openMatch(state.id);
        else client.readMatch(state.id).then(latest => playQuiz(latest.ok ? latest.data : state));
      }, REVIEW_MS);
    }

    belts.forEach((button, index) => {
      button.querySelector('.belt-key')?.setAttribute('data-key', String(index + 1));
      button.addEventListener('click', () => submit(button.dataset.belt, button));
    });
    const onKey = event => {
      if (!view.isConnected) { document.removeEventListener('keydown', onKey); return; }
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      const index = Number(event.key) - 1;
      if (!Number.isInteger(index) || index < 0 || index >= belts.length || belts[index].disabled) return;
      event.preventDefault();
      belts[index].click();
    };
    document.addEventListener('keydown', onKey);
    paint();
    timer = setInterval(paint, 200);
    return view;
  }

  // This player has finished and the other has not: the bar keeps moving
  // until the server calls the duel.
  function showWaiting(state) {
    if (state.state === 'finished') { showResult(state); return null; }
    const view = labPage(`
      <section class="lab-screen screen-versus" data-attempt-live>
        ${tugMarkup(state)}
        <p class="lab-eyebrow">${esc(t(GAME_NAME[state.game]))}</p>
        <h1 class="lab-title">${esc(t('You are done'))}</h1>
        <p class="lab-intro" role="status">${esc(t('Waiting for {name} to finish.', { name: state.opponent.username }))}</p>
      </section>
    `, 'versus', () => showWaiting(state));
    paintTug(view, state);
    followMatch(view, state.id);
    return view;
  }

  function playHandler(state) {
    if (state.you.finished) { showWaiting(state); return null; }
    const view = labPage(`
      <section class="lab-screen screen-versus screen-handler" data-attempt-live>
        ${tugMarkup(state)}
        <div data-handler-root></div>
        ${leaveButton()}
      </section>
    `, 'versus', () => playHandler(state));
    paintTug(view, state);
    followMatch(view, state.id);
    wireLeave(view, state.id);
    // The score goes to the server as it changes, at most one report in
    // flight: the newest number waits its turn rather than racing an older
    // one. That ordering matters -- the server keeps the LAST score it is
    // told, because a wrong belt takes a point off and the duel is decided
    // by where the round ended, not by the highest it touched.
    let latest = 0;
    let sent = 0;
    let sending = false;
    async function flush() {
      if (sending || latest === sent) return;
      sending = true;
      const going = latest;
      await client.progress(state.id, going, false);
      sent = going;
      sending = false;
      if (view.isConnected) flush();
    }
    mountHandlerDuel(view.querySelector('[data-handler-root]'), {
      seed: state.seed,
      onScore: score => { latest = score; flush(); },
      onEnd: async summary => {
        // Let a report already in flight land first, so the final score
        // is the last thing the server hears from this round.
        latest = summary.score;
        while (sending) await new Promise(resolve => setTimeout(resolve, 40));
        sent = summary.score;
        await client.progress(state.id, summary.score, true);
        if (!view.isConnected) return;
        openMatch(state.id);
      },
    });
    return view;
  }

  // ------------------------------------------------------------ the result

  function showResult(state) {
    const title = state.outcome === 'you' ? 'You won' : state.outcome === 'opponent' ? 'You lost' : 'A tie';
    // Both tiles used to look the same, so only the title said who won.
    // A tie marks neither.
    const won = state.outcome === 'you' ? state.you : state.outcome === 'opponent' ? state.opponent : null;
    const line = player => `
      <div class="vs-final${player === state.you ? ' vs-final-you' : ''}${player === won ? ' vs-final-won' : ''}">
        ${/* The other tile keeps the chip's room, so the two names and the
              two scores stay level. A tie leaves both blank. */ ''}
        ${player === won
          ? `<span class="vs-final-crown">${esc(t('Winner'))}</span>`
          : '<span class="vs-final-crown is-blank" aria-hidden="true"></span>'}
        ${face(player)}
        <span class="vs-final-name">${esc(player.username)}</span>
        <b class="vs-final-score">${language.number(player.score)}</b>
        ${state.game === 'quiz' ? `<small>${player.correct} ${esc(t('of'))} ${state.question_count} ${esc(t('right'))}</small>` : ''}
      </div>`;
    const view = labPage(`
      <section class="lab-screen screen-versus">
        <p class="lab-eyebrow">${esc(t(GAME_NAME[state.game]))}</p>
        <div class="vs-result home-spot ${state.outcome === 'you' ? 'vs-won' : ''}">
          <span class="home-short-ic is-solid" aria-hidden="true">${gameIcon(state.game)}</span>
          <h1 class="lab-title">${esc(t(title))}</h1>
          <div class="vs-finals">${line(state.you)}${line(state.opponent)}</div>
        </div>
        <button id="vs-again" class="primary" type="button">${esc(t('Play again'))}</button>
        <button id="vs-board" class="ghost" type="button">${esc(t('Versus leaderboard'))}</button>
      </section>
    `, 'versus', () => showResult(state));
    view.querySelector('#vs-again').addEventListener('click', () => showVersus());
    view.querySelector('#vs-board').addEventListener('click', showBoard);
    return view;
  }

  // ------------------------------------------------------- the leaderboard

  function showBoard() {
    const view = labPage(`
      <section class="lab-screen screen-versus">
        ${backLink('vs-board-back')}
        <p class="lab-eyebrow" id="vs-board-season">${esc(t('Versus'))}</p>
        <h1 class="lab-title tab-title">${esc(t('Versus leaderboard'))}</h1>
        <div id="vs-board-panel"><p class="lab-intro" role="status">${esc(t('Loading the standings…'))}</p></div>
      </section>
    `, 'versus', showBoard);
    view.querySelector('#vs-board-back').addEventListener('click', () => showVersus());
    fillBoard(view);
    return view;
  }

  async function fillBoard(view) {
    const answer = await client.leaderboard();
    if (!view.isConnected) return;
    const panel = view.querySelector('#vs-board-panel');
    if (!answer.ok) {
      panel.innerHTML = `<div class="board-notice"><h2>${esc(t('Could not load the standings'))}</h2><p>${esc(t('Try again in a moment.'))}</p></div>`;
      return;
    }
    const board = answer.data;
    if (board.season_label) view.querySelector('#vs-board-season').textContent = `${t('Versus')} · ${board.season_label}`;
    if (board.rows.length === 0) {
      panel.innerHTML = `<div class="board-notice"><h2>${esc(t('No duels yet'))}</h2><p>${esc(t('Nobody has finished a duel this season. Be the first.'))}</p></div>`;
      return;
    }
    const rows = board.rows.map(row => `
      <li class="${row.you ? 'board-you' : ''}${row.tied ? ' board-tied' : ''}">
        <span class="board-place">${row.place}</span>
        <span class="board-who">
          <b>${avatarEmoji(row.avatar) ? `<span class="board-avatar" aria-hidden="true">${avatarEmoji(row.avatar)}</span>` : ''}${esc(row.username)}</b>
          <small>#${esc(row.tag)} · ${language.number(row.points)} ${esc(t('points'))} · ${row.played} ${esc(t(row.played === 1 ? 'duel' : 'duels'))}${row.you ? ` · ${esc(t('your place'))}` : ''}</small>
        </span>
        <b class="board-points">${row.wins} <small class="vs-wins">${esc(t(row.wins === 1 ? 'win' : 'wins'))}</small></b>
      </li>`).join('');
    const intro = board.open
      ? t('Duels won this season. Points separate players level on wins.')
      : t('The season is over. This is how Versus finished.');
    // The player's place leads the screen, as it does on the Ranked board.
    // Their wins and duels come from their own row when the server sent
    // one; a player ranked past those rows gets the place alone.
    const mine = board.rows.find(row => row.you) ?? board.you ?? null;
    const place = mine?.place ?? board.you?.place ?? null;
    const counted = board.rows.find(row => row.you);
    const placeCard = place === null ? '' : `
      <div class="board-mine" id="vs-mine">
        <div>
          <p class="lab-study-meta">${esc(t('Your place'))}</p>
          <p class="board-mine-place">#${esc(place)}</p>
        </div>
        ${counted ? `<div class="board-mine-pts">
          <b>${counted.wins} ${esc(t(counted.wins === 1 ? 'win' : 'wins'))}</b>
          <small>${counted.played} ${esc(t(counted.played === 1 ? 'duel' : 'duels'))} · ${language.number(counted.points)} ${esc(t('points'))}</small>
        </div>` : ''}
      </div>`;
    const youBeyond = board.you && !counted
      ? `<p class="board-your-place">${esc(t('Your place'))}: <b>${board.you.place}</b></p>`
      : '';
    // The note about how the standings are kept is a footnote to them.
    panel.innerHTML = `${placeCard}<section class="home-stripe"><p class="lab-eyebrow">${esc(t('Standings'))}</p><ol class="board">${rows}</ol></section>${youBeyond}<p class="lab-intro tab-intro">${esc(intro)}</p>`;
  }

  return { showVersus, showRoom, showMatch, showResult, showBoard };
}
