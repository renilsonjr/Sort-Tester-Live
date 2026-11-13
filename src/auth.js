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
  const response = await fetch(`${API_BASE}${path}`, options);
  if (response.status === 204) {
    return null;
  }
  const data = response.headers.get('content-type')?.includes('application/json')
    ? await response.json()
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
  container.innerHTML = `
    <div class="auth-screen">
      <h1>Sort Lab</h1>
      <div class="auth-buttons">
        <button id="auth-login-btn" class="primary">Log in</button>
        <button id="auth-register-btn" class="ghost">Create account</button>
        <button id="auth-guest-btn" class="ghost">Continue as guest</button>
      </div>
      <div id="auth-form" hidden></div>
      <p id="auth-message" class="warn"></p>
    </div>
  `;

  const form = container.querySelector('#auth-form');
  const message = container.querySelector('#auth-message');

  function showMessage(text, isError = false) {
    message.textContent = text;
    message.className = isError ? 'notice' : 'warn';
  }

  container.querySelector('#auth-login-btn').addEventListener('click', () => {
    form.hidden = false;
    form.innerHTML = `
      <div class="field">
        <span>Login ID</span>
        <input id="login-id-input" type="text" autocomplete="off" placeholder="ABCD-EFGH-JKLM-NPQR">
      </div>
      <button id="login-submit" class="primary">Log in</button>
      <button id="login-cancel" class="ghost">Cancel</button>
    `;
    form.querySelector('#login-submit').addEventListener('click', async () => {
      const loginId = form.querySelector('#login-id-input').value;
      const result = await loginWithId(loginId);
      if (result.ok) {
        showMessage(`Welcome, ${result.data.username}#${result.data.tag}`);
        form.hidden = true;
        if (onLoggedIn) onLoggedIn(result.data);
      } else {
        showMessage('Invalid login ID. Please try again.', true);
      }
    });
    form.querySelector('#login-cancel').addEventListener('click', () => { form.hidden = true; });
  });

  container.querySelector('#auth-register-btn').addEventListener('click', () => {
    form.hidden = false;
    form.innerHTML = `
      <div class="field">
        <span>Choose a username</span>
        <input id="register-username-input" type="text" autocomplete="off" placeholder="alice_1">
      </div>
      <button id="register-submit" class="primary">Create account</button>
      <button id="register-cancel" class="ghost">Cancel</button>
    `;
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
        done.addEventListener('click', () => { form.hidden = true; });
      } else {
        showMessage('Could not create account. Username may be taken or invalid.', true);
      }
    });
    form.querySelector('#register-cancel').addEventListener('click', () => { form.hidden = true; });
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
  const enterApp = () => {
    panel.hidden = true;
    if (app) app.hidden = false;
  };
  return createAuthPanel(panel, enterApp, enterApp);
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
