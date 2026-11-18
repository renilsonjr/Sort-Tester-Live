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

export async function loginWithId(loginId) {
  return api('POST', '/auth/login', { login_id: loginId });
}

export async function logout() {
  return api('POST', '/auth/logout');
}

export async function fetchMe() {
  return api('GET', '/auth/me');
}

export function createAuthPanel(container, onContinueAsGuest, onLoggedIn) {
  // Keep entry choices compact; a form replaces them while it is open.
  container.innerHTML = `
    <div class="auth-screen">
      <div class="brandmark" aria-hidden="true">RJ</div>
      <div class="auth-head">
        <h1 class="auth-title">Sort Lab</h1>
        <p class="auth-sub">Learn the chart. Play Ranked. Climb the leaderboard.</p>
      </div>
      <div id="auth-choices" class="auth-card">
        <p class="auth-eyebrow">Log in</p>
        <label class="sr-only" for="login-id-input">Login ID</label>
        <input id="login-id-input" class="glass-input" type="text" autocomplete="off" placeholder="Your login ID">
        <button id="auth-login-btn" class="primary">Log in with ID</button>
        <button id="auth-guest-btn" class="ghost">Continue as guest</button>
        <p class="auth-note">Ranked needs a login. Guests get Practice only.</p>
        <button id="auth-register-btn" class="auth-link" type="button">Need an ID? Create an account</button>
      </div>
      <div id="auth-form" class="auth-card" hidden></div>
      <p id="auth-message" class="warn"></p>
    </div>
  `;

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

  // The login ID is entered directly on the entry card (mock's single-card
  // entry); "Log in with ID" (or Enter) submits it.
  async function doLogin() {
    const loginId = container.querySelector('#login-id-input').value;
    const result = await loginWithId(loginId);
    if (result.ok) {
      showMessage(`Welcome, ${result.data.username}#${result.data.tag}`);
      if (onLoggedIn) onLoggedIn(result.data);
    } else if (result.status === 0) {
      showMessage('Could not reach the server. Your login ID is fine; try again in a moment.', true);
    } else {
      showMessage('Invalid login ID. Please try again.', true);
    }
  }
  container.querySelector('#auth-login-btn').addEventListener('click', doLogin);
  container.querySelector('#login-id-input').addEventListener('keydown', (event) => {
    if (event.key === 'Enter') { event.preventDefault(); doLogin(); }
  });

  container.querySelector('#auth-register-btn').addEventListener('click', () => {
    choices.hidden = true;
    showMessage('');
    form.hidden = false;
    form.innerHTML = `
      <label class="field">
        <span>Choose a username</span>
        <input id="register-username-input" type="text" autocomplete="off" placeholder="alice_1">
      </label>
      <button id="register-submit" class="primary">Create account</button>
      <button id="register-cancel" class="ghost">Cancel</button>
    `;
    form.querySelector('#register-username-input').focus();
    form.querySelector('#register-submit').addEventListener('click', async () => {
      const username = form.querySelector('#register-username-input').value;
      const result = await registerAccount(username);
      if (result.ok) {
        form.innerHTML = `
          <p class="notice">Save this login ID. It will not be shown again.</p>
          <div class="field">
            <span>Your login ID</span>
            <input id="generated-login-id" type="text" readonly value="${result.data.login_id}">
          </div>
          <label class="field">
            <input id="saved-check" type="checkbox"> I saved my login ID
          </label>
          <button id="register-done" class="primary" disabled>Continue</button>
        `;
        const check = form.querySelector('#saved-check');
        const done = form.querySelector('#register-done');
        check.addEventListener('change', () => { done.disabled = !check.checked; });
        done.addEventListener('click', () => closeForm('#auth-register-btn'));
      } else if (result.status === 0) {
        showMessage('Could not reach the server. Nothing was created; try again in a moment.', true);
      } else {
        showMessage('Could not create account. Username may be taken or invalid.', true);
      }
    });
    form.querySelector('#register-cancel').addEventListener('click', () => closeForm('#auth-register-btn'));
  });

  container.querySelector('#auth-guest-btn').addEventListener('click', () => {
    if (onContinueAsGuest) onContinueAsGuest();
  });

  return {
    async checkSession() {
      const result = await fetchMe();
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
  if (!(await backendIsAvailable(fetchFn, timeoutMs))) return false;
  const panel = initAuthPanel(doc);
  if (!panel) return false;
  await panel.checkSession();
  return true;
}

if (typeof document !== 'undefined' && typeof fetch === 'function') {
  startAuthGate();
}
