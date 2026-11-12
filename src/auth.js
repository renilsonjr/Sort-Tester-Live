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

export function createAuthPanel(container, onContinueAsGuest) {
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
      if (result.ok) {
        showMessage(`Welcome back, ${result.data.username}#${result.data.tag}`);
      }
    },
  };
}

function initAuthPanel() {
  if (typeof document === 'undefined') return;
  const panel = document.getElementById('auth-panel');
  const app = document.getElementById('app');
  if (!panel) return;
  panel.hidden = false;
  if (app) app.hidden = true;
  createAuthPanel(panel, () => {
    panel.hidden = true;
    if (app) app.hidden = false;
    // Trigger the existing app start if it has not already.
    if (typeof window !== 'undefined' && typeof window.showStart === 'function') {
      window.showStart();
    }
  });
}

// The auth gate is intentionally not auto-initialized: GitHub Pages serves
// this frontend without a backend, so showing the login screen would dead-end
// every visitor. Wire it up (with a reachable API base) when the backend is
// hosted — call initAuthPanel() from the entry point at that point.
