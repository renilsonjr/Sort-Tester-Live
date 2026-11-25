// Minimal client for login-ID authentication.
// The session token lives in an HttpOnly cookie managed by the browser;
// this module never stores it in localStorage.

const API_BASE = (typeof window !== 'undefined' && window.SORT_TESTER_API_BASE)
  ? window.SORT_TESTER_API_BASE
  : '/api';

async function api(method, path, body) {
  const options = {
    method,
    headers: { 'Content-Type': 'application/json' },
    credentials: 'same-origin',
  };
  if (body !== undefined) {
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, options);
  } catch {
    // No answer came back at all. Status 0 says so, and every caller here
    // already checks `ok` before reading `data`.
    return { ok: false, status: 0, data: null };
  }
  if (response.status === 204) {
    return null;
  }
  const data = response.headers.get('content-type')?.includes('application/json')
    ? await response.json().catch(() => null)
    : null;
  return { ok: response.ok, status: response.status, data };
}

export async function registerAccount(username) {
  return api('POST', '/auth/register', { username });
}

export async function loginWithId(username, loginId) {
  return api('POST', '/auth/login', { username, login_id: loginId });
}

export async function logout() {
  return api('POST', '/auth/logout');
}

export async function fetchMe() {
  return api('GET', '/auth/me');
}

export async function leaveRecoveryMessage(message) {
  return api('POST', '/auth/recovery-messages', { message });
}

// The rest of this panel is English only. These are the sentences added with
// the recovery message (#251), in both of the app's languages. The table
// lives here, not in i18n.js, because this file is loaded on its own and
// imports nothing; the storage key is the one i18n.js keeps the choice in.
// The public result of an outside security test of this site, shown at the
// foot of the sign-in screen as ImmuniWeb's own badge, served from here. A
// link and a local image: nothing from another site runs or loads on the
// page where the Quiz Code is typed. The same address is in app.js
// (Settings); this file imports nothing, so it is written in both, and a
// test keeps the two the same.
const SECURITY_REPORT_URL = 'https://www.immuniweb.com/websec/sortquiz.app/8SXNOVH5/';

const FORGOT_ES = {
  'Forgot my Quiz Code?':
    '¿Olvidaste tu Quiz Code?',
  // #422: the two cards behind the login card never named themselves. Their
  // first words were a field label -- "Choose a username", "Message for the
  // owner" -- while the login card has carried "Log in" all along.
  'New account':
    'Cuenta nueva',
  'Recover your access':
    'Recupera tu acceso',
  'Message for the owner':
    'Mensaje para el responsable',
  'Say who you are and what happened. The owner reads this and recovers your access in person. Nothing is recovered from this screen.':
    'Di quién eres y qué pasó. El responsable lee esto y recupera tu acceso en persona. Desde esta pantalla no se recupera nada.',
  'Send message':
    'Enviar mensaje',
  'Cancel':
    'Cancelar',
  'Write a message first.':
    'Escribe un mensaje primero.',
  'Message received. The owner recovers access in person: find them at work.':
    'Mensaje recibido. El responsable recupera el acceso en persona: búscalo en el trabajo.',
  'Too many messages for now. Find the owner in person.':
    'Demasiados mensajes por ahora. Busca al responsable en persona.',
  'Could not reach the server. Nothing was sent; try again in a moment.':
    'No se pudo contactar con el servidor. No se envió nada; inténtalo de nuevo en un momento.',
  'The message could not be sent. Find the owner in person.':
    'No se pudo enviar el mensaje. Busca al responsable en persona.',
  // #451: the player manual, a PDF per language, opened before login.
  'Privacy': 'Privacidad',
  'How to play':
    'Cómo jugar',
  'Sign up, play, and how to win a hat.':
    'Crear cuenta, jugar y cómo ganar una gorra.',
  'Made by RJ. Meet the person behind the app':
    'Hecho por RJ. Conoce a quien está detrás de la app',
  'Security tested: grade A by ImmuniWeb': 'Seguridad probada: calificación A de ImmuniWeb',
  // The whole new-account flow (#333). The rest of this module is still
  // English only, but this is the one screen where not understanding the
  // warning costs the account: the Quiz Code is shown exactly once, and
  // there is no recovery except finding the owner in person. Translating
  // half of it would have left "Continue" in English beside a Spanish tick
  // row, which reads worse than the all-English screen it replaced.
  'Choose a username':
    'Elige un nombre de usuario',
  'Create account':
    'Crear cuenta',
  'Cancel':
    'Cancelar',
  'Save this Quiz Code. It will not be shown again.':
    'Guarda este Quiz Code. No se volverá a mostrar.',
  'Your Quiz Code':
    'Tu Quiz Code',
  'Continue':
    'Continuar',
  'I saved my Quiz Code':
    'Guardé mi Quiz Code',
  'Copy':
    'Copiar',
  'Copied':
    'Copiado',
  'Show':
    'Mostrar',
  'Hide':
    'Ocultar',
  'Your username':
    'Tu nombre de usuario',
  'Username':
    'Nombre de usuario',
  'Invalid username or Quiz Code. Please try again.':
    'Nombre de usuario o Quiz Code incorrecto. Inténtalo de nuevo.',
  'Your account was created. Sign in with your username and the Quiz Code above.':
    'Tu cuenta se creó. Inicia sesión con tu nombre de usuario y el Quiz Code de arriba.',
  'Show Quiz Code':
    'Mostrar Quiz Code',
  'Hide Quiz Code':
    'Ocultar Quiz Code',
  'Could not copy. Select the code and copy it by hand.':
    'No se pudo copiar. Selecciona el código y cópialo a mano.',
};

// The manual PDF in the visitor's language (#451); built by
// docs/player-manual/build_pdf.py into assets/manual/.
// Bump MANUAL_VERSION whenever the PDFs are rebuilt, so a phone that opened
// an older manual doesn't keep showing it from its cache.
const MANUAL_VERSION = '2026-11-25c';

// What the app keeps about a player, and for how long: a plain page in each
// language, opened in a new tab like the manual.
function privacyHref() {
  return `assets/privacy/privacy-${forgotText('Privacy') === 'Privacy' ? 'en' : 'es'}.html`;
}

function manualHref() {
  return `assets/manual/sortquiz-manual-${forgotText('How to play') === 'How to play' ? 'en' : 'es'}.pdf?v=${MANUAL_VERSION}`;
}

function forgotText(source) {
  let spanish = false;
  try {
    spanish = globalThis.localStorage?.getItem('sortTest.language.v1') === 'es';
  } catch { /* no storage: English */ }
  return spanish ? FORGOT_ES[source] ?? source : source;
}

export function createAuthPanel(container, onContinueAsGuest, onLoggedIn) {
  // Keep entry choices compact; a form replaces them while it is open.
  container.innerHTML = `
    <div class="auth-screen">
      ${/* #452: the season bubble. This panel imports nothing, so it only
            draws the empty bubble; app.js fills it (seasonNotice.js). */ ''}
      <section class="season-bubble" id="auth-season" hidden aria-live="polite">
        <i aria-hidden="true">!</i>
        <div class="season-bubble-body"><h2 data-bubble-title></h2><p data-bubble-text></p></div>
        <button type="button" class="season-bubble-close" data-bubble-close aria-label="Close">×</button>
      </section>
      <div class="brandmark" aria-hidden="true">RJ</div>
      <div class="auth-head">
        <h1 class="auth-title">Sort Quiz</h1>
      </div>
      <form id="auth-choices" class="auth-card" autocomplete="on">
        <p class="auth-eyebrow">Log in</p>
        <label class="sr-only" for="login-username-input">${forgotText('Username')}</label>
        <input id="login-username-input" class="glass-input" type="text" name="username" autocomplete="username" autocapitalize="none" spellcheck="false" placeholder="${forgotText('Your username')}">
        <label class="sr-only" for="login-id-input">Quiz Code</label>
        <div class="code-field">
          <input id="login-id-input" class="glass-input" type="password" name="quiz-code" autocomplete="current-password" placeholder="Your Quiz Code">
          <button id="auth-show-code-btn" class="code-eye" type="button" aria-pressed="false" aria-label="${forgotText('Show Quiz Code')}">${forgotText('Show')}</button>
        </div>
        <button id="auth-login-btn" class="primary" type="submit">Log in with Quiz Code</button>
        <button id="auth-guest-btn" class="ghost" type="button">Continue as guest</button>
        <button id="auth-register-btn" class="auth-link" type="button">Need a Quiz Code? Create an account</button>
        <button id="auth-forgot-btn" class="auth-link" type="button">${forgotText('Forgot my Quiz Code?')}</button>
      </form>
      ${/* #451: the manual is for people who have no account yet, so it
            sits on this screen, outside the login card. */ ''}
      <a id="auth-howto" class="auth-howto" href="${manualHref()}" target="_blank" rel="noopener">
        <span aria-hidden="true">?</span>
        <span><strong>${forgotText('How to play')}</strong><small>${forgotText('Sign up, play, and how to win a hat.')}</small></span>
      </a>
      <div id="auth-form" class="auth-card" hidden></div>
      <p id="auth-message" class="warn"></p>
      <p class="auth-footer"><a class="auth-footer-link" href="https://renilsonjr.pages.dev" target="_blank" rel="noopener noreferrer">${forgotText('Made by RJ. Meet the person behind the app')}</a></p>
      <p class="auth-footer auth-footer-security"><a class="security-badge-link" href="${SECURITY_REPORT_URL}" target="_blank" rel="noopener noreferrer"><img class="security-badge" src="assets/immuniweb-badge.png" width="150" height="50" alt="${forgotText('Security tested: grade A by ImmuniWeb')}"></a></p>
      <p class="auth-footer"><a id="auth-privacy" class="auth-footer-link" href="${privacyHref()}" target="_blank" rel="noopener">${forgotText('Privacy')}</a></p>
    </div>
  `;

  try {
    container.ownerDocument?.dispatchEvent(new Event('sortquiz:auth-shown'));
  } catch { /* no DOM events here: the bubble just stays hidden */ }

  const form = container.querySelector('#auth-form');
  const message = container.querySelector('#auth-message');
  const choices = container.querySelector('#auth-choices');

  function closeForm(trigger) {
    form.hidden = true;
    form.innerHTML = '';
    choices.hidden = false;
    showMessage('');
    container.querySelector(trigger)?.focus();
  }

  function showMessage(text, isError = false) {
    message.textContent = text;
    message.className = isError ? 'notice' : 'warn';
  }

  // Username + Quiz Code are entered directly on the entry card; the
  // username names the account and the code proves it (2026-11-25).
  async function doLogin() {
    const username = container.querySelector('#login-username-input').value.trim();
    const loginId = container.querySelector('#login-id-input').value;
    const result = await loginWithId(username, loginId);
    if (result.ok) {
      showMessage(`Welcome, ${result.data.username}#${result.data.tag}`);
      if (onLoggedIn) onLoggedIn(result.data);
    } else if (result.status === 0) {
      showMessage('Could not reach the server. Your Quiz Code is fine; try again in a moment.', true);
    } else if (result.status === 429 || result.status === 503) {
      // Refused before the Quiz Code was looked at: too many tries from this
      // network, or the server had too many to check at once. Saying
      // "invalid" here would send someone with the right code to recovery.
      showMessage('Too many attempts. Wait a moment and try again.', true);
    } else {
      showMessage(forgotText('Invalid username or Quiz Code. Please try again.'), true);
    }
  }
  // Show/hide the Quiz Code while typing. The field stays a password field
  // in the DOM by default, so the browser still treats it as one.
  const showCodeBtn = container.querySelector('#auth-show-code-btn');
  showCodeBtn.addEventListener('click', () => {
    const input = container.querySelector('#login-id-input');
    const showing = showCodeBtn.getAttribute('aria-pressed') !== 'true';
    input.type = showing ? 'text' : 'password';
    showCodeBtn.setAttribute('aria-pressed', String(showing));
    showCodeBtn.setAttribute('aria-label', forgotText(showing ? 'Hide Quiz Code' : 'Show Quiz Code'));
    showCodeBtn.textContent = forgotText(showing ? 'Hide' : 'Show');
  });

  // A real <form> submit (button or Enter) is what lets the browser offer to
  // save the Quiz Code. The page itself never navigates.
  choices.addEventListener('submit', (event) => {
    event.preventDefault();
    return doLogin();
  });

  container.querySelector('#auth-register-btn').addEventListener('click', () => {
    choices.hidden = true;
    showMessage('');
    form.hidden = false;
    form.innerHTML = `
      <p class="auth-eyebrow">${forgotText('New account')}</p>
      <label class="field">
        <span>${forgotText('Choose a username')}</span>
        <input id="register-username-input" type="text" autocomplete="off" placeholder="alice_1">
      </label>
      <button id="register-submit" class="primary">${forgotText('Create account')}</button>
      <button id="register-cancel" class="ghost">${forgotText('Cancel')}</button>
    `;
    form.querySelector('#register-username-input').focus();
    form.querySelector('#register-submit').addEventListener('click', async () => {
      const username = form.querySelector('#register-username-input').value;
      const result = await registerAccount(username);
      if (result.ok) {
        // This is the only time a Quiz Code is ever shown, and the screen
        // was the least finished in the app (#333): the code could only be
        // retyped by hand, 19 characters, or the account was lost; and the
        // confirmation was a raw browser checkbox with its label on the
        // next line, not tied to it and with no accessible name.
        //
        // The username and the code sit in one <form> together, so that on
        // Continue the browser can offer to save them as a pair -- phones
        // only offer that for a username + secret (owner test, 2026-11-25).
        // The username is the one the server just accepted, so it is only
        // letters, digits and underscores.
        form.innerHTML = `
          <form id="register-save-form" autocomplete="on">
          <p class="notice">${forgotText('Save this Quiz Code. It will not be shown again.')}</p>
          <div class="field">
            <span>${forgotText('Username')}</span>
            <input id="generated-username" type="text" name="username" autocomplete="username" readonly value="${username}">
          </div>
          <div class="field">
            <span>${forgotText('Your Quiz Code')}</span>
            <div class="code-row">
              <input id="generated-login-id" type="text" name="quiz-code" autocomplete="new-password" readonly value="${result.data.login_id}">
              <button id="copy-login-id" class="code-copy" type="button">${forgotText('Copy')}</button>
            </div>
          </div>
          <p class="auth-note" id="copy-status" role="status"></p>
          <label class="check-row" for="saved-check">
            <input id="saved-check" type="checkbox">
            <span class="check-box" aria-hidden="true"></span>
            <span class="check-label">${forgotText('I saved my Quiz Code')}</span>
          </label>
          <button id="register-done" class="primary" type="submit" disabled>${forgotText('Continue')}</button>
          </form>
        `;
        // The page never navigates; Continue's click does the signing in.
        form.querySelector('#register-save-form')?.addEventListener('submit', (event) => {
          event.preventDefault();
        });
        const check = form.querySelector('#saved-check');
        const done = form.querySelector('#register-done');
        check.addEventListener('change', () => { done.disabled = !check.checked; });

        // Continue used to call closeForm() and nothing else, which put the
        // new player back on the sign-in screen with the code they had just
        // been given to type in by hand (#334). Confirmed twice against the
        // local database, and in the code: closeForm only hides the form.
        //
        // It signs them in instead, with the code the server just issued.
        // If that fails for any reason the old behaviour is what is left --
        // the sign-in screen, with the account created and the code still
        // valid -- and the reason is shown rather than swallowed, because
        // the code is about to disappear from this screen for ever.
        const newLoginId = result.data.login_id;
        done.addEventListener('click', async () => {
          done.disabled = true;
          // A password field is what a password manager looks for when the
          // form is submitted; it goes back to plain text if sign-in fails,
          // because the code must stay readable on this screen.
          const codeField = form.querySelector('#generated-login-id');
          codeField.type = 'password';
          const signedIn = await loginWithId(username, newLoginId);
          if (signedIn.ok) {
            closeForm('#auth-register-btn');
            showMessage(`Welcome, ${signedIn.data.username}#${signedIn.data.tag}`);
            if (onLoggedIn) onLoggedIn(signedIn.data);
            return;
          }
          codeField.type = 'text';
          done.disabled = false;
          showMessage(forgotText('Your account was created. Sign in with your username and the Quiz Code above.'), true);
        });

        // One tap instead of 19 characters. The clipboard API needs a
        // secure context, which the app always has (https, or localhost in
        // development), but a browser can still refuse it -- so a refusal
        // selects the code and says to copy it by hand rather than failing
        // silently and leaving the player with no account.
        const copy = form.querySelector('#copy-login-id');
        const status = form.querySelector('#copy-status');
        copy.addEventListener('click', async () => {
          const field = form.querySelector('#generated-login-id');
          try {
            await navigator.clipboard.writeText(field.value);
            copy.textContent = forgotText('Copied');
            status.textContent = forgotText('Copied');
            setTimeout(() => { copy.textContent = forgotText('Copy'); }, 2000);
          } catch {
            field.select();
            status.textContent = forgotText('Could not copy. Select the code and copy it by hand.');
          }
        });
      } else if (result.status === 0) {
        showMessage('Could not reach the server. Nothing was created; try again in a moment.', true);
      } else {
        showMessage('Could not create account. Username may be taken or invalid.', true);
      }
    });
    form.querySelector('#register-cancel').addEventListener('click', () => closeForm('#auth-register-btn'));
  });

  // A locked-out player cannot sign in, so this is the one thing they can
  // do here: leave the owner a message (#251). It recovers nothing and
  // looks nothing up, so every accepted message gets the same sentence.
  container.querySelector('#auth-forgot-btn').addEventListener('click', () => {
    choices.hidden = true;
    showMessage('');
    form.hidden = false;
    form.innerHTML = `
      <p class="auth-eyebrow">${forgotText('Recover your access')}</p>
      <label class="field">
        <span>${forgotText('Message for the owner')}</span>
        <textarea id="forgot-message" class="glass-input" rows="4" maxlength="500"></textarea>
      </label>
      <p class="auth-note"><span id="forgot-count">0</span>/500</p>
      <p class="auth-note">${forgotText('Say who you are and what happened. The owner reads this and recovers your access in person. Nothing is recovered from this screen.')}</p>
      <button id="forgot-send" class="primary">${forgotText('Send message')}</button>
      <button id="forgot-cancel" class="ghost">${forgotText('Cancel')}</button>
    `;
    const box = form.querySelector('#forgot-message');
    const send = form.querySelector('#forgot-send');
    box.focus();
    box.addEventListener('input', () => {
      form.querySelector('#forgot-count').textContent = String(box.value.length);
    });
    send.addEventListener('click', async () => {
      const text = box.value.trim();
      if (!text) {
        showMessage(forgotText('Write a message first.'), true);
        return;
      }
      send.disabled = true;
      const result = await leaveRecoveryMessage(text);
      send.disabled = false;
      if (result.ok) {
        closeForm('#auth-forgot-btn');
        showMessage(forgotText('Message received. The owner recovers access in person: find them at work.'));
      } else if (result.status === 429) {
        showMessage(forgotText('Too many messages for now. Find the owner in person.'), true);
      } else if (result.status === 0) {
        showMessage(forgotText('Could not reach the server. Nothing was sent; try again in a moment.'), true);
      } else {
        showMessage(forgotText('The message could not be sent. Find the owner in person.'), true);
      }
    });
    form.querySelector('#forgot-cancel').addEventListener('click', () => closeForm('#auth-forgot-btn'));
  });

  container.querySelector('#auth-guest-btn').addEventListener('click', () => {
    if (onContinueAsGuest) onContinueAsGuest();
  });

  return {
    // `pending` lets the caller start the /auth/me request earlier (in
    // parallel with the /health probe) and hand the promise in, so the
    // session check costs no extra round-trip. Falls back to a fresh call.
    async checkSession(pending) {
      const result = await (pending ?? fetchMe());
      if (result && result.ok) {
        showMessage(`Welcome back, ${result.data.username}#${result.data.tag}`);
        if (onLoggedIn) onLoggedIn(result.data);
      }
    },
  };
}

export function initAuthPanel(doc = document) {
  const panel = doc.getElementById('auth-panel');
  const app = doc.getElementById('app');
  if (!panel) return null;
  panel.hidden = false;
  if (app) app.hidden = true;
  // app.js has already rendered the start screen inside #app; entering the
  // app (as a guest or after logging in) only swaps which one is visible.
  // The app needs to know which way in was taken: a guest gets Home and
  // Practice, a signed-in player also gets Ranked and Profile (#10).
  const enterApp = (account = null) => {
    panel.hidden = true;
    if (app) app.hidden = false;
    doc.defaultView?.setSortLabSession?.(account);
  };
  // Leaving the app is the same swap the other way round. app.js owns the
  // reasons to leave (the Log out button, and the idle timer), so it calls
  // this; the panel only knows how to show itself again, with one line
  // saying why the visitor is looking at it.
  const view = doc.defaultView;
  if (view) {
    view.showSortLabEntry = (notice = '') => {
      if (app) app.hidden = true;
      panel.hidden = false;
      const choices = panel.querySelector('#auth-choices');
      if (choices) choices.hidden = false;
      const form = panel.querySelector('#auth-form');
      if (form) {
        form.hidden = true;
        form.innerHTML = '';
      }
      const message = panel.querySelector('#auth-message');
      if (message) {
        message.textContent = notice;
        message.className = 'warn';
      }
      panel.querySelector('#auth-login-btn')?.focus();
    };
  }
  return createAuthPanel(panel, () => enterApp(null), (account) => enterApp(account));
}

// Is the FastAPI backend serving this page? On GitHub Pages /health does not
// exist, so the answer is no and the page stays exactly as it was.
export async function backendIsAvailable(fetchFn = fetch, timeoutMs = 3000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetchFn('/health', { signal: controller.signal, credentials: 'same-origin' });
    if (!response.ok) return false;
    const data = await response.json();
    return data?.status === 'ok';
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

// Show the login screen only when the backend answers. Returns true if shown.
export async function startAuthGate({ doc = document, fetchFn = fetch, timeoutMs = 3000 } = {}) {
  // Fire the availability probe and the session lookup together. On the
  // deployed backend /health always answers, so awaiting it before /auth/me
  // added a guaranteed extra round-trip before the signed-in Home could
  // appear. `fetchMe` never rejects, so starting it early is safe even when
  // the backend turns out to be absent (then we simply never read it).
  const sessionPromise = fetchMe();
  if (!(await backendIsAvailable(fetchFn, timeoutMs))) return false;
  const panel = initAuthPanel(doc);
  if (!panel) return false;
  await panel.checkSession(sessionPromise);
  return true;
}

if (typeof document !== 'undefined' && typeof fetch === 'function') {
  startAuthGate();
}
