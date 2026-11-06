import { checkHealth, isDevelopmentOrigin, readConfig } from './health-client.mjs';

const button = document.getElementById('check-api');
const status = document.getElementById('status');
const show = (kind, message) => {
  status.dataset.kind = kind;
  status.textContent = message;
};

if (!isDevelopmentOrigin(window.location.origin)) {
  show('configuration', 'This check runs only at http://127.0.0.1:8000. Serve the dev folder locally; no API request was made.');
} else {
  button.disabled = false;
  show('ready', 'Ready. Start the API, then select Check API.');
  button.addEventListener('click', async () => {
    if (button.disabled) return;
    button.disabled = true;
    show('loading', 'Checking…');
    try {
      const response = await fetch('./config.local.json', {
        cache: 'no-store', credentials: 'omit', redirect: 'error', signal: AbortSignal.timeout(5000),
      });
      const config = await readConfig(response);
      const result = await checkHealth({ pageOrigin: window.location.origin, apiBaseUrl: config.apiBaseUrl });
      show(result.kind, result.message);
    } catch {
      show('configuration', 'Could not load local configuration. Copy config.example.json to config.local.json with only apiBaseUrl set to http://127.0.0.1:18765. Check that the page server is running. Never add secrets.');
    } finally {
      button.disabled = false;
    }
  });
}
