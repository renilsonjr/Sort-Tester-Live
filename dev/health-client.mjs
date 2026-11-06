const PAGE_ORIGIN = 'http://127.0.0.1:8000';
const API_BASE_URL = 'http://127.0.0.1:18765';
const CONFIG_HELP = 'Copy config.example.json to config.local.json with only the apiBaseUrl setting. Never add secrets.';

export const isDevelopmentOrigin = origin => origin === PAGE_ORIGIN;

export async function readConfig(response) {
  try {
    if (response.status !== 200) throw new Error();
    const config = await response.json();
    if (!config || Object.keys(config).length !== 1 || config.apiBaseUrl !== API_BASE_URL) {
      throw new Error();
    }
    return { apiBaseUrl: config.apiBaseUrl };
  } catch {
    throw new Error(CONFIG_HELP);
  }
}

export async function checkHealth({ pageOrigin, apiBaseUrl, fetchImpl = globalThis.fetch, timeoutMs = 5000 }) {
  if (!isDevelopmentOrigin(pageOrigin) || apiBaseUrl !== API_BASE_URL) {
    return { kind: 'configuration', message: `Use the local page at ${PAGE_ORIGIN} and API at ${API_BASE_URL}.` };
  }

  const controller = new AbortController();
  let timer;
  const deadline = new Promise(resolve => {
    timer = setTimeout(() => {
      resolve({ kind: 'unavailable', message: 'Request timed out. Check that the API server is running and its CORS origin matches this page.' });
      controller.abort();
    }, timeoutMs);
  });

  const request = async () => {
    let response;
    try {
      response = await fetchImpl(`${apiBaseUrl}/health`, {
        method: 'GET', credentials: 'omit', redirect: 'error', cache: 'no-store',
        signal: controller.signal,
      });
    } catch {
      return { kind: 'unavailable', message: 'Could not reach the API. Check the server, its address, and CORS settings; the browser cannot tell us which failed.' };
    }
    if (response.status !== 200) {
      return { kind: 'invalid-response', message: `Unexpected API response: HTTP ${response.status}. Expected HTTP 200.` };
    }
    try {
      const contentType = response.headers.get('content-type')?.split(';')[0].trim().toLowerCase();
      if (contentType !== 'application/json') throw new Error();
      const body = await response.json();
      if (!body || Object.keys(body).length !== 1 || body.status !== 'ok') throw new Error();
      return { kind: 'success', message: 'API responded: ok (HTTP 200).' };
    } catch {
      return { kind: 'invalid-response', message: 'Unexpected API response. Expected JSON containing only {"status":"ok"}.' };
    }
  };

  try {
    return await Promise.race([deadline, request()]);
  } finally {
    clearTimeout(timer);
  }
}
