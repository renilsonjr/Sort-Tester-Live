// The player's own screens: the profile and its history, support and
// tickets, the avatar, signing out other devices, changing the Quiz Code,
// deleting the account, and Settings.
//
// Everything the app already owns arrives through `deps` -- the page shell,
// the translator, the ways to reach the server, the badge pieces Home draws
// too -- the same arrangement src/ownerScreens.js and src/versus/ have. The
// signed-in account stays in app.js: these screens read it with account()
// and, when an account is deleted, drop it with forgetAccount().
import { AVATARS, avatarEmoji } from './avatars.js';
import { SECURITY_REPORT_URL } from './common.js';
import { seasonBubbleMarkup } from './seasonNotice.js';
import { practiceCountLabel } from './shiftLog.js';
import * as support from './support.js';

export function createProfileScreens(deps) {
  const {
    labPage, t, esc, ICONS, language, backLink, log,
    api, apiSend, apiSendOwner,
    account, forgetAccount, stopQuizClock,
    logout, signOut, showOwnerTools,
    badgeArt, badgeProgress, badgeTrail, balanceLine, fillLaunchCallout,
  } = deps;

  function showProfile(tab = 'overview') {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen screen-profile">
        <p class="lab-eyebrow">${esc(t('Profile'))}</p>
        ${tab !== 'overview' ? `
        <!-- #389: Settings names itself, like every other screen -- eyebrow
             for the section, title for the screen. It used to borrow the
             overview's header, so its h1 was the player's username and nothing
             on it said "Settings"; its own sub-screens (Sign out my other
             devices, Delete account) already use "Settings" as their eyebrow,
             so this completes that ladder. The identity card belongs to the
             overview, which Back goes to. -->
        ${/* #414: history had the same gap Settings had -- it borrowed the
              overview's header, so its h1 was the player's username and
              nothing said which history it was. "Ranked history", not "Shift
              history": the Shift log is the practice list kept on the phone,
              and these are the Ranked attempts the server settled. */ ''}
        <h1 class="lab-title">${esc(t(tab === 'settings' ? 'Settings' : 'Ranked history'))}</h1>` : `
        ${seasonBubbleMarkup('launch-callout')}
        ${/* One card says who the player is and where they stand: the name,
              the balance, and the climb to the next badge. The points used to
              be a tile further down and again in the line under the badges,
              and the badge was drawn here and again in the row of five. */ ''}
        <div class="home-spot pf-hero">
        <div class="pf-ident">
          <div class="home-obj pf-ident-obj" id="profile-badge"></div>
          <div class="pf-ident-text">
            <span id="profile-avatar-mark" class="pf-avatar" aria-hidden="true"></span>
            <h1 class="lab-title" id="profile-name">${esc(account()?.username ?? '\u2026')}</h1>
            <p class="lab-intro" id="profile-tag">${account()?.tag ? esc(`${t('Tag')} #${account().tag}`) : ''}</p>
          </div>
        </div>
        <div class="pf-standing" id="profile-standing"></div>
        </div>`}
        <div id="profile-panel"><p class="lab-intro">${esc(t('Loading\u2026'))}</p></div>
      </section>
    `, 'profile', () => showProfile(tab));

    // #389: the gear chip in the sub-header is the control that OPENS Settings.
    // On Settings itself it re-renders the screen you are already on, and now
    // that the screen says its own name, the word "Settings" appeared twice
    // 150px apart. The chip stays on the tabs it can still take you somewhere
    // from, and Back returns to the overview, where it is.
    if (tab === 'settings') view.querySelector('#top-settings')?.remove();

    const panel = view.querySelector('#profile-panel');
    fillProfile(view, panel, tab);
    fillLaunchCallout(view);  // #452: only the overview has the bubble
    return view;
  }

  // The name and tag come from the session the page already holds, so the
  // panel's own request starts at once instead of waiting behind /auth/me.
  // Only a session without them (which no entry path produces) asks the server.
  async function fillProfile(view, panel, tab) {
    // The player's own icon, beside their name, on every tab. It comes off
    // the session like the name does, so no request is made for it; empty
    // until they choose one, which leaves the header as it was before #272.
    paintProfileAvatar(view, account()?.avatar);
    if (!account()?.username || !account()?.tag) {
      api('/auth/me').then((me) => {
        if (!me) return;
        // Optional since #389: the Settings tab has a title of its own and no
        // identity card, so neither node is on the page there.
        const nameEl = view.querySelector('#profile-name');
        if (nameEl) nameEl.textContent = me.username;
        const tagEl2 = view.querySelector('#profile-tag');
        if (tagEl2) tagEl2.textContent = `${t('Tag')} #${me.tag}`;
        // the icon rides on the session like the name does, so this only
        // runs on the path that was already asking the server anyway (#272)
        if (account()) account().avatar = me.avatar;
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
    // The label reads first and the figure under it, so three tiles in a row
    // line their figures up even when a Spanish label takes two lines.
    const statCell = (value, label) => `<div class="pf-stat"><small>${esc(label)}</small><b${value === t('Not yet') ? ' class="words"' : ''}>${esc(value)}</b></div>`;
    // The badge sits beside the name in the card above the panel. Its name is
    // not added to the tag line any more: the climb line in the same card
    // already begins with it.
    const badgeSlot = panel.closest('.lab-screen')?.querySelector('#profile-badge');
    if (badgeSlot) {
      badgeSlot.innerHTML = `<span class="home-shine" aria-hidden="true"></span><img class="home-obj-badge" src="${badgeArt(entry.badge)}" alt="${esc(entry.badge)}">`;
    }
    const progress = badgeProgress(entry);
    // The balance, how far the badge has to go, and the five badges, in the
    // card that already carries the name.
    const standing = panel.closest('.lab-screen')?.querySelector('#profile-standing');
    if (standing) {
      standing.innerHTML = `
        <p class="lab-study-meta">${esc(t('Your balance'))}</p>
        <p class="profile-points">${language.number(entry.points)} <i>${esc(t('points'))}</i></p>
        ${progress === null ? '' : `<div class="profile-bar home-meter"><i style="width:${progress}%"></i></div>`}
        <p class="home-climb-note">${esc(balanceLine(entry))}</p>
        <div class="pf-badges">
          ${badgeTrail(entry.badge)}
        </div>`;
    }
    panel.innerHTML = `
      <section class="home-stripe">
      <p class="lab-eyebrow">${esc(t('Your numbers'))}</p>
      <div class="pf-stats">
        ${statCell(bestRanked, t('Best Ranked'))}
        ${statCell(place, t('Place'))}
        ${statCell(log.available ? practiceCountLabel(log.all()) : DASH, t('Practices'))}
      </div>
      </section>
      ${entry.mode === 'promotion' ? `
      <div class="profile-promo">
        <h2>${esc(t('Promotion unlocked'))}</h2>
        <p>${esc(t('A perfect 15 out of 15 quiz moves you up. Start promotion is on the Ranked screen; nothing starts from here.'))}</p>
      </div>` : ''}
      <button id="pf-history" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.history}</span>
        <span><strong>${esc(t('See history'))}</strong></span>
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
            <small>${esc(language.date(row.settled_at))}</small>
            <span class="status ${ended ? 'ended' : ''}">${esc(ended ? t('Ended at launch \u00b7 no score applied') : t('Completed'))}</span>
          </li>`;
        }).join('')}
      </ul>`;
  }

  // Support (#10, slice 5; the screen half of #26). Support holds Tickets and
  // nothing else, and a ticket exists only because the player asked for one.
  function showSupport() {
    stopQuizClock();
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
    // #421: a ticket is about a Ranked attempt, so a player with none was sent
    // to a screen that could only say so and offer Cancel. This screen did not
    // know -- only showCreateTicket asked -- so it asks too, alongside the
    // request it already makes, costing no extra wall time.
    const [result, history] = await Promise.all([support.listTickets(), api('/ranked/history')]);
    if (!result || !result.ok) {
      panel.innerHTML = `<p class="notice">${esc(t('Could not load your tickets. Your tickets and your points are safe.'))}</p>`;
      return;
    }
    const tickets = result.data ?? [];
    // Fail open: `api` answers null for a request that did not land, and a
    // support screen must not lock its only action because a second request
    // failed. Locked only when we know there is nothing to write a ticket
    // about -- the same dashed, half-lit row the deck picker already uses.
    const canCreate = history === null || history.length > 0;
    // #420: the screen's job is "see your tickets, or open one", and the
    // retention policy used to outrank both: three paragraphs, 88 words, 284px
    // measured at 375x812 between the title and the only control. The list and
    // the action come first now; the policy keeps every word, below them.
    panel.innerHTML = `
      ${tickets.length === 0 ? `
        <p class="lab-intro">${esc(t('You have no tickets. Support only opens one when you ask for it: nothing here is created automatically, and a connection problem does not open a ticket by itself.'))}</p>
      ` : `<ul class="support-list">
        ${tickets.map((ticket) => `
        <li>
          <span class="support-pill ${ticket.closed_at ? 'closed' : 'open'}">${esc(support.outcomeLabel(ticket))}</span>
          <b>${esc(t('Ranked quiz'))}</b>
          <small>${esc(language.date(ticket.opened_at))}</small>
          <span class="support-keep">${esc(support.retentionLine(ticket, (iso) => language.date(iso)))}</span>
        </li>`).join('')}
      </ul>`}
      ${canCreate ? `
      <button id="support-create" class="lab-choice lab-choice-quiz" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.createTicket}</span>
        <span><strong>${esc(t('Create ticket'))}</strong><small>${esc(t('About one of your own Ranked attempts.'))}</small></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>` : `
      <div class="lab-choice locked">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.createTicket}</span>
        <span><strong>${esc(t('Create ticket'))}</strong><small>${esc(t('A ticket is about a Ranked attempt, and you have none yet.'))}</small></span>
      </div>`}
      <p class="lab-intro">${esc(t('Only you can see your tickets. When a ticket is closed, its description and connection details are deleted 15 days later. Evidence shared with another case that is still open is kept until that case closes.'))}</p>
      <p class="lab-intro">${esc(t('Opening a ticket never changes your points or your access.'))}</p>
    `;
    panel.querySelector('#support-create')?.addEventListener('click', showCreateTicket);
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
            ${attempts.map((a) => `<option value="${a.attempt_id}">${esc(t('Ranked quiz'))} \u00b7 ${esc(language.date(a.settled_at))} \u00b7 ${esc(a.final_outcome)}</option>`).join('')}
          </select>
        </label>
        <label class="field">
          <span>${esc(t('What happened'))}</span>
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
        <button id="ticket-back" class="ghost" type="button">${esc(t('Back'))}</button>
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        ${/* #424: the way out was a full-width ghost, pixel-identical to the
              "No icon" button stacked right under it -- one clears your icon,
              the other leaves, and nothing said which. Same compact Back the
              deck picker and the leaderboard use, in the same place: first. */ ''}
        ${backLink('av-back')}
        <p class="lab-eyebrow">${esc(t('Profile'))}</p>
        <h1 class="lab-title">${esc(t('Choose a profile icon'))}</h1>
        <p class="lab-intro">${esc(t('Shown on your profile and the leaderboard.'))}</p>
        <div class="avatar-grid" id="av-grid" role="group" aria-label="${esc(t('Choose a profile icon'))}">
          ${AVATARS.map(([key, glyph]) => `
            <button type="button" class="avatar-pick" data-avatar="${esc(key)}" aria-pressed="false" aria-label="${esc(key)}">${glyph}</button>`).join('')}
        </div>
        <p class="notice" id="av-said" role="status" hidden></p>
        <button id="av-none" class="ghost" type="button">${esc(t('No icon'))}</button>
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
    mark(chosen === undefined ? (account()?.avatar ?? null) : chosen);

    const save = async (key) => {
      const result = await apiSend('PUT', '/auth/avatar', { avatar: key });
      if (!result.ok) { tell(result.reason || t('That did not work.')); return; }
      if (account()) account().avatar = key;
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
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        <p class="lab-eyebrow">${esc(t('Settings'))}</p>
        <h1 class="lab-title">${esc(t('Sign out other devices'))}</h1>
        <p class="lab-intro">${esc(t('Ends every other phone or computer signed in to your account. This one stays.'))}</p>
        <p class="lab-intro">${esc(t('Your Quiz Code keeps working. Anyone using it elsewhere has to enter it again.'))}</p>
        <p class="lab-intro">${esc(t('If someone else knows your Quiz Code, change it in Settings.'))}</p>
        <p class="notice" id="signout-others-said" role="status" hidden></p>
        <button id="signout-others-go" class="primary" type="button">${esc(t('Sign out other devices'))}</button>
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

  // Change my Quiz Code (owner decision 2026-11-25). Behind the same re-entry
  // gate as signing out other devices: a stolen session alone must not be
  // able to take the account by changing its code. The server ends every
  // other session and keeps this device signed in. The new code is shown
  // here once, next to the username, inside one form, so the browser can
  // offer to update the saved pair.
  function showChangeCode() {
    stopQuizClock();
    const view = labPage(`
      <section class="lab-screen">
        <p class="lab-eyebrow">${esc(t('Settings'))}</p>
        <h1 class="lab-title">${esc(t('Change Quiz Code'))}</h1>
        <p class="lab-intro">${esc(t('You get a new Quiz Code. The old one stops working at once.'))}</p>
        <p class="lab-intro">${esc(t('Every other phone or computer signed in to your account is signed out. This one stays.'))}</p>
        <p class="notice" id="change-code-said" role="status" hidden></p>
        <button id="change-code-go" class="primary" type="button">${esc(t('Change Quiz Code'))}</button>
        <button id="change-code-cancel" class="ghost" type="button">${esc(t('Cancel'))}</button>
        <div id="change-code-result"></div>
      </section>
    `, 'profile', showChangeCode);

    const said = view.querySelector('#change-code-said');
    const go = view.querySelector('#change-code-go');
    const cancel = view.querySelector('#change-code-cancel');
    cancel.addEventListener('click', () => showProfile('settings'));
    go.addEventListener('click', async () => {
      go.disabled = true;
      const result = await apiSendOwner('POST', '/auth/login-id/change');
      if (!result.ok || !result.data?.login_id) {
        said.hidden = false;
        said.classList.remove('done');
        said.textContent = `${result.reason || t('That did not work.')} ${t('Nothing was changed.')}`;
        go.disabled = false;
        return;
      }
      go.hidden = true;
      cancel.hidden = true;
      said.hidden = true;
      const box = view.querySelector('#change-code-result');
      box.innerHTML = `
        <form id="change-code-form" autocomplete="on">
          <p class="notice">${esc(t('Save this Quiz Code. It will not be shown again.'))}</p>
          <label class="field"><span>${esc(t('Username'))}</span>
            <input id="change-code-username" type="text" name="username" autocomplete="username" readonly value="${esc(account()?.username ?? '')}"></label>
          <div class="field">
            <span>${esc(t('Your new Quiz Code'))}</span>
            <div class="code-row">
              <input id="change-code-value" type="text" name="quiz-code" autocomplete="new-password" readonly value="${esc(result.data.login_id)}">
              <button id="change-code-copy" class="code-copy" type="button">${esc(t('Copy'))}</button>
            </div>
          </div>
          <p class="auth-note" id="change-code-copied" role="status"></p>
          <label class="check-row" for="change-code-saved">
            <input id="change-code-saved" type="checkbox">
            <span class="check-box" aria-hidden="true"></span>
            <span class="check-label">${esc(t('I saved my Quiz Code'))}</span>
          </label>
          <button id="change-code-done" class="primary" type="submit" disabled>${esc(t('Done'))}</button>
        </form>`;
      const formEl = box.querySelector('#change-code-form');
      const saved = box.querySelector('#change-code-saved');
      const done = box.querySelector('#change-code-done');
      const field = box.querySelector('#change-code-value');
      const copied = box.querySelector('#change-code-copied');
      saved.addEventListener('change', () => { done.disabled = !saved.checked; });
      box.querySelector('#change-code-copy').addEventListener('click', async () => {
        try {
          await navigator.clipboard.writeText(field.value);
          copied.textContent = t('Copied');
        } catch {
          field.select();
          copied.textContent = t('Could not copy. Select the code and copy it by hand.');
        }
      });
      // A password field is what a password manager looks for when the form
      // is submitted. The page does not navigate; it goes back to Settings.
      formEl.addEventListener('submit', (event) => {
        event.preventDefault();
        field.type = 'password';
        setTimeout(() => showProfile('settings'), 0);
      });
    });
    return view;
  }

  function showDeleteAccount() {
    stopQuizClock();
    // Reopening always starts clean: the box unchecked, the field empty, the
    // final action disabled. Decision 14 requires the reset.
    const view = labPage(`
      <section class="lab-screen">
        <p class="lab-eyebrow">${esc(t('Settings'))}</p>
        <h1 class="lab-title">${esc(t(DELETE_QUESTION))}</h1>
        <p class="lab-intro">${esc(t(DELETE_CONSEQUENCE))}</p>
        <label class="delete-ack" for="delete-ack">
          <input type="checkbox" id="delete-ack">
          <span class="check-box" aria-hidden="true"></span>
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
    forgetAccount();
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
    // The order the owner set on 2026-11-25, read top to bottom: the things
    // you change about yourself first, then the ways out, then the one that
    // ends the account. Owner tools sits above all of it, because on the one
    // account that has it, it is what that account is for.
    panel.innerHTML = `
      <button id="profile-owner" class="lab-choice" type="button" hidden>
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.owner}</span>
        <span><strong>${esc(t('Owner tools'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>` + `
      <button id="profile-avatar" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.avatar}</span>
        <span><strong>${esc(t('Profile icon'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="profile-change-code" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.accessRecovery}</span>
        <span><strong>${esc(t('Change Quiz Code'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="profile-signout-others" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.devices}</span>
        <span><strong>${esc(t('Sign out other devices'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="profile-support" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.support}</span>
        <span><strong>${esc(t('Support'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="profile-logout" class="lab-choice" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.logOut}</span>
        <span><strong>${esc(t('Log out'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <button id="profile-delete" class="lab-choice lab-choice-quiz" type="button">
        <span class="lab-choice-icon" aria-hidden="true">${ICONS.deleteAccount}</span>
        <span><strong>${esc(t('Delete account'))}</strong></span>
        <span class="lab-arrow" aria-hidden="true">\u2192</span>
      </button>
      <p class="profile-version" id="profile-version"></p>
      <p class="profile-security"><a class="security-badge-link" href="${SECURITY_REPORT_URL}" target="_blank" rel="noopener noreferrer"><img class="security-badge" src="assets/immuniweb-badge.png" width="150" height="50" alt="${esc(t('Security tested: grade A by ImmuniWeb'))}"></a></p>
      <p class="auth-footer"><a id="profile-privacy" class="auth-footer-link" href="assets/privacy/privacy-${language.code === 'es' ? 'es' : 'en'}.html" target="_blank" rel="noopener">${esc(t('Privacy'))}</a></p>
    `;
    panel.querySelector('#profile-support').addEventListener('click', showSupport);
    panel.querySelector('#profile-logout').addEventListener('click', () => signOut());
    panel.querySelector('#profile-avatar').addEventListener('click', () => showAvatarPicker());
    panel.querySelector('#profile-signout-others').addEventListener('click', showSignOutOthers);
    panel.querySelector('#profile-change-code').addEventListener('click', showChangeCode);
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

  return { showProfile };
}
