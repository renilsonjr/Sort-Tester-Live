// The owner's screens: prize eligibility, access recovery, recovery
// messages, prize selection, case review, accounts, and the one-time start
// of the official season. Only an owner account is ever shown the way in,
// and every route these screens call checks the owner again on the server.
//
// Everything the app already owns arrives through `deps` -- the page shell,
// the translator, the ways to reach the server -- so this module draws the
// owner's screens and nothing else, the same arrangement src/versus/ has.
export function createOwnerScreens(deps) {
  const {
    labPage, t, esc, ICONS, language, backLink,
    api, apiSend, apiSendOwner, clearReadCache,
    stopQuizClock, showSettings,
  } = deps;

  // Owner tools (#11), built to the screens approved on 2026-11-15.
  //
  // Scoped on purpose: approving prize eligibility, approving access
  // recovery in person, reviewing cases, and removing an account that should
  // not exist (#271). The account list carries a name, a tag and a date and
  // nothing of a player's record: there is still no points screen and no
  // history browser, because the owner was never granted those. What is
  // missing here is missing on purpose.
  function showOwnerTools() {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen screen-owner">
        ${backLink('owner-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Owner tools'))}</h1>
        <aside class="lab-disclaimer">${esc(t('These are the only administrator powers this app has. Approving does not change anybody’s points, badge or history, and gives you no access to a player’s record.'))}</aside>
        <button id="owner-eligibility" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.prizeEligibility}</span>
          <span><strong>${esc(t('Prize eligibility'))}</strong><small>${esc(t('Who may win a hat this season.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
        <button id="owner-recovery" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.accessRecovery}</span>
          <span><strong>${esc(t('Access recovery'))}</strong><small>${esc(t('In person, for a sorter who lost their Quiz Code.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
        <button id="owner-messages" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.recoveryMessages}</span>
          <span><strong>${esc(t('Recovery messages'))}</strong><small id="owner-messages-count">${esc(t('Left on the sign-in screen by people who are locked out.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
        <button id="owner-select" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.tiebreak}</span>
          <span><strong>${esc(t('Prize selection'))}</strong><small id="owner-select-count">${esc(t('Ties the rules send to you.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">\u2192</span>
        </button>
        <button id="owner-cases" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.caseReview}</span>
          <span><strong>${esc(t('Case review'))}</strong><small>${esc(t('Tickets players opened, and connection flags.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">→</span>
        </button>
        <button id="owner-accounts" class="lab-choice" type="button">
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.accounts}</span>
          <span><strong>${esc(t('Accounts'))}</strong><small>${esc(t('Remove an account that should not exist.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">\u2192</span>
        </button>
        <button id="owner-launch" class="lab-choice lab-choice-quiz" type="button" hidden>
          <span class="lab-choice-icon" aria-hidden="true">${ICONS.ranked}</span>
          <span><strong>${esc(t('Start the official season'))}</strong><small>${esc(t('Once, when the Pre-Season ends.'))}</small></span>
          <span class="lab-arrow" aria-hidden="true">\u2192</span>
        </button>
      </section>
    `, 'profile', showOwnerTools);
    view.querySelector('#owner-accounts').addEventListener('click', () => showOwnerAccounts());
    // The launch is used once. The row exists only while the Pre-Season is
    // still running, so the day after the launch there is no button left to
    // press by mistake, and no disabled row explaining a power nobody has
    // any more (owner decision, #258).
    const launch = view.querySelector('#owner-launch');
    launch.addEventListener('click', () => showOwnerLaunch());
    api('/ranked/season').then((season) => {
      if (season?.phase === 'pre_season') launch.hidden = false;
    });
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
    view.querySelector('#owner-back').addEventListener('click', () => showSettings());
    return view;
  }

  // Prize eligibility. One sorter, one account, recorded while the season is
  // open; withdrawal stays available afterwards, because leaving a wrong
  // approval in place would hand a hat to somebody not entitled to it.
  function showOwnerEligibility(message = null, bad = false) {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('elig-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Prize eligibility'))}</h1>
        ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
        <div id="elig-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
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
          <h2 class="lab-eyebrow">${esc(t('Approve a sorter'))}</h2>
          <label class="field"><span>${esc(t('Player tag'))}</span>
            <input id="elig-tag" type="text" autocomplete="off" autocapitalize="characters" placeholder="#K7Q2MX"></label>
          <label class="field"><span>${esc(t('Roster reference'))}</span>
            <input id="elig-ref" type="text" autocomplete="off" placeholder="${esc(t('Primary Sort · Twilight · badge 4471'))}"></label>
          <p class="lab-intro">${esc(t('The roster reference is how you identify this person on your own roster. It is never shown to players.'))}</p>
          <button id="elig-approve" class="primary">${esc(t('Approve'))}</button>
        </div>
      ` : `<div class="board-notice"><h2>${esc(t('The season is closed to new approvals'))}</h2><p>${esc(t('Approvals close when the season ends, including the five-minute finishing window. You can still withdraw an approval that should not stand.'))}</p></div>`}
      <h2 class="lab-eyebrow owner-count">${approvals.length
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('acct-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Accounts'))}</h1>
        ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
        <div id="acct-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
      </section>
    `, 'profile', () => showOwnerAccounts(message, bad));
    view.querySelector('#acct-back').addEventListener('click', showOwnerTools);
    fillOwnerAccounts(view.querySelector('#acct-panel'));
    return view;
  }

  function accountRowLine(row) {
    const parts = [`#${row.tag}`, `${t('created')} ${language.date(row.created_at)}`];
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
      <h2 class="lab-eyebrow owner-count">${esc(t('Accounts'))} (${accounts.length})</h2>
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

  // Starting the official season (#258). The one irreversible thing in the
  // app: it ends open quizzes with no score, sets every balance to 0 and
  // opens the official season. Three gates, the same ones the route checks:
  // the owner's own account, the word LAUNCH typed by hand, and the Quiz
  // Code re-entered within five minutes (apiSendOwner asks when the server
  // says 428). The console block in infra/azure/rollout-runbook.md does the
  // same thing and stays as the way round if this screen ever fails.
  const LAUNCH_WORD = 'LAUNCH';
  const DEFAULT_SEASON_LABEL = 'Season 1';

  function showOwnerLaunch(message = null, bad = false) {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Start the official season'))}</h1>
        ${message ? `<div class="board-notice board-notice-bad" role="status"><p>${esc(message)}</p></div>` : ''}
        <div class="delete-warn">
          <h2>${esc(t('This cannot be undone'))}</h2>
          <p>${esc(t('Every quiz being played right now ends with no score.'))}</p>
          <p>${esc(t('Every balance goes to 0 and everybody is Iron again.'))}</p>
          <p>${esc(t('Pre-Season history is kept: everybody can still read their own.'))}</p>
          <p>${esc(t('The official season opens and runs to its closing date. It can only be started once.'))}</p>
        </div>
        <label class="field">
          <span>${esc(t('Season name'))}</span>
          <input id="launch-label" type="text" autocomplete="off" value="${esc(DEFAULT_SEASON_LABEL)}">
        </label>
        <p class="lab-study-meta">${esc(t('Players see this name on the leaderboard.'))}</p>
        <label class="field">
          <span>${esc(t('Type LAUNCH to confirm'))}</span>
          <input id="launch-word" type="text" autocomplete="off" autocapitalize="characters">
        </label>
        <p class="notice" id="launch-error" hidden></p>
        <button id="launch-back" class="primary" type="button">${esc(t('Not yet'))}</button>
        <button id="launch-go" class="ghost owner-danger" type="button" disabled>${esc(t('Start the official season'))}</button>
      </section>
    `, 'profile', () => showOwnerLaunch(message, bad));
    const label = view.querySelector('#launch-label');
    const word = view.querySelector('#launch-word');
    const go = view.querySelector('#launch-go');
    const error = view.querySelector('#launch-error');
    const ready = () => word.value.trim().toUpperCase() === LAUNCH_WORD && label.value.trim() !== '';
    const refresh = () => { go.disabled = !ready(); };
    word.addEventListener('input', refresh);
    label.addEventListener('input', refresh);
    view.querySelector('#launch-back').addEventListener('click', showOwnerTools);
    go.addEventListener('click', async () => {
      go.disabled = true;
      error.hidden = true;
      const result = await apiSendOwner('POST', '/ranked/season/launch', {
        label: label.value.trim(),
        confirm: LAUNCH_WORD,
      });
      if (result.ok) {
        // the season and the balance both changed: a kept copy would show
        // the Pre-Season on the very screen that proves it ended
        clearReadCache();
        showLaunchDone(result.data);
        return;
      }
      refresh();
      error.textContent = result.reason || t('That did not work. Nothing has been changed.');
      error.hidden = false;
    });
    return view;
  }

  // What the owner checks after a launch, done by the app instead of asked
  // of them: the season that is open now, and their own balance read back
  // from the server. The history line is the one thing they confirm by eye.
  function showLaunchDone(season) {
    stopQuizClock();
    const closes = season?.closes_at ? language.dateTime(season.closes_at) : '';
    const view = labPage(`
      <section class="lab-screen">
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('The official season has started'))}</h1>
        <div class="owner-form">
          <p class="acct-name"><b>${esc(season?.label ?? '')}</b></p>
          <p class="acct-meta">${esc(t('Closes'))} ${esc(closes)}</p>
        </div>
        <h2 class="owner-count">${esc(t('What changed'))}</h2>
        <ul class="approved">
          <li><span class="approved-who"><b id="launch-points">${esc(t('Checking…'))}</b>
            <small>${esc(t('Every balance was reset in the same step, so yours tells the story.'))}</small></span></li>
          <li><span class="approved-who"><b>${esc(t('Pre-Season history was kept'))}</b>
            <small>${esc(t('Check it yourself: Profile, then See history.'))}</small></span></li>
        </ul>
        <button id="done-back" class="primary" type="button">${esc(t('Back'))}</button>
      </section>
    `, 'profile', () => showLaunchDone(season));
    view.querySelector('#done-back').addEventListener('click', showOwnerTools);
    // read back, rather than claim: the number comes from the server
    api('/ranked/entry').then((entry) => {
      const slot = view.querySelector('#launch-points');
      if (!slot) return;
      slot.textContent = entry
        ? `${t('Your points are now')} ${language.number(entry.points)} (${entry.badge})`
        : t('Your points could not be read just now.');
    });
    return view;
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('sel-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Prize selection'))}</h1>
        ${message ? `<div class="board-notice" role="status"><p>${esc(message)}</p></div>` : ''}
        <div id="sel-panel"><p class="lab-intro" role="status">${esc(t('Loading\u2026'))}</p></div>
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
      panel.innerHTML = `<div class="owner-form"><h2 class="lab-eyebrow">${esc(t('Nothing waiting'))}</h2>
        <p class="lab-intro">${esc(t('A tie comes here only when the rules say so: still tied after the last round, no fresh questions left, or several players who did not finish competing for fewer hats.'))}</p></div>`;
      return;
    }
    panel.innerHTML = `
      <aside class="lab-disclaimer">${esc(t('These ties could not be settled by a quiz, so the rules send them to you. Choose who takes the hats. Your choice is final, and it changes nobody\u2019s points, badge or tie-break results.'))}</aside>
      ${body.cases.map((c) => `
        <div class="owner-form sel-case" data-group="${esc(c.group_id)}" data-hats="${c.hats}">
          <p class="lab-eyebrow">${c.hats} ${esc(c.hats === 1 ? t('hat') : t('hats'))} \u00b7 ${language.number(c.tied_points)} ${esc(t('points each'))}</p>
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('case-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Case review'))}</h1>
        <aside class="lab-disclaimer">${esc(t('Closing a case records what you found. It never changes anybody’s points, badge or access, and it opens no ticket by itself. A connection flag is a pattern the server noticed, not evidence that somebody cheated.'))}</aside>
        ${message ? `<div class="board-notice" role="status"><p>${esc(message)}</p></div>` : ''}
        <div class="profile-tabs" role="tablist" aria-label="${esc(t('Case kind'))}">
          <button type="button" role="tab" data-case="tickets" aria-selected="${kind === 'tickets'}">${esc(t('Tickets'))}</button>
          <button type="button" role="tab" data-case="flags" aria-selected="${kind === 'flags'}">${esc(t('Flags'))}</button>
        </div>
        <div id="case-panel"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
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
          <li>${esc(event.kind.replace(/_/g, ' '))} · ${esc(language.dateTime(event.occurred_at))}</li>
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
          <h2 class="lab-eyebrow">${esc(t('Nothing waiting'))}</h2>
          <p class="lab-intro">${esc(kind === 'flags'
            ? t('No open flags. A flag appears only when the server notices repeated connection loss in one attempt.')
            : t('No open tickets. Tickets only appear when a player opens one; a connection problem does not open a ticket by itself.'))}</p>
        </div>`;
      return;
    }
    panel.innerHTML = `<ul class="cases">${body.map((row) => (kind === 'flags' ? `
      <li>
        <p class="lab-eyebrow">${esc(t('Flag'))} · ${esc(t('noticed'))} ${esc(language.date(row.flagged_at))}</p>
        <h2>${esc(row.username)} · #${esc(row.tag)}</h2>
        <p class="lab-study-meta">${esc(t('Losses between'))} ${esc(language.dateTime(row.first_loss_at))} ${esc(t('and'))} ${esc(language.dateTime(row.last_loss_at))}</p>
        <div class="board-notice"><p>${esc(t('This is a pattern the server noticed. It is not proof that anybody cheated, and closing it changes no points and no access.'))}</p></div>
        ${caseEvents(row.events)}
        <p class="case-keep">${esc(t('Kept while this review is open. Fifteen days after it closes, these connection details are deleted, unless a case still open shares the same log.'))}</p>
        ${outcomeButtons(row.attempt_id)}
      </li>` : `
      <li>
        <p class="lab-eyebrow">${esc(t('Ticket'))} · ${esc(t('opened'))} ${esc(language.date(row.opened_at))}</p>
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('rec-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Access recovery'))}</h1>
        ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
        <div class="owner-form">
          <h2 class="lab-eyebrow">${esc(t('Who is in front of you?'))}</h2>
          <label class="field"><span>${esc(t('Player tag'))}</span>
            <input id="rec-tag" type="text" autocomplete="off" autocapitalize="characters" placeholder="#K7Q2MX"></label>
          <p class="lab-intro">${esc(t('The tag is on their profile. It is how you find the account, not proof of who they are.'))}</p>
          <button id="rec-find" class="primary">${esc(t('Find the account'))}</button>
        </div>
        <h2 class="lab-eyebrow owner-count">${esc(t('Recent recoveries'))}</h2>
        <div id="rec-list"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
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
            ? `${t('handed over')} ${language.date(row.completed_at)}`
            : `${t('opened')} ${language.date(row.opened_at)}, ${t('not completed')}`)}</small>
        </span>
      </li>`).join('')}</ul>`;
  }

  // Recovery messages (#251). What a locked-out player typed on the sign-in
  // screen. Anybody can type anything there, including somebody else's name,
  // so this screen shows the text as text and says what it is worth: a reason
  // to go and find a person. Recovering access is still the other screen.
  function showRecoveryMessages(message = null, bad = false) {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${backLink('msg-back')}
        <p class="lab-eyebrow">${esc(t('Owner'))}</p>
        <h1 class="lab-title">${esc(t('Recovery messages'))}</h1>
        ${message ? `<div class="board-notice${bad ? ' board-notice-bad' : ''}" role="status"><p>${esc(message)}</p></div>` : ''}
        <aside class="lab-disclaimer">${esc(t('A message proves nothing about who wrote it. Find the person, check them in person, then use Access recovery.'))}</aside>
        <button id="msg-recovery" class="ghost">${esc(t('Open Access recovery'))}</button>
        <div id="msg-list"><p class="lab-intro" role="status">${esc(t('Loading…'))}</p></div>
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
            ? `${t('received')} ${language.dateTime(row.created_at)} · ${t('resolved')} ${language.date(row.resolved_at)}`
            : `${t('received')} ${language.dateTime(row.created_at)}`)}</small>
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
        <button id="rec-hand" class="primary">${esc(t('Checked in person · show code'))}</button>
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

  return { showOwnerTools };
}
