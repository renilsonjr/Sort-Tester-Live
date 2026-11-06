# Development Browser API Bridge Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Display a real FastAPI health response in an independent local browser page and handle failure clearly.

**Architecture:** Serve `dev/` separately from the existing Practice application. A small browser module validates local configuration and requests the API; FastAPI enables CORS only for explicitly configured development origins.

**Tech Stack:** Existing FastAPI/Starlette, Python unittest/TestClient, browser HTML/JavaScript, Node built-in tests; no new runtime dependencies.

**Spec:** `docs/superpowers/specs/2026-11-06-browser-api-bridge-design.md`

## Global Constraints

- Continue on `codex/ranked-mode`; preserve existing Practice behavior.
- Page origin: `http://127.0.0.1:8000`; API base URL: `http://127.0.0.1:18765`.
- `SORT_TEST_DEV_ORIGINS` unset means no cross-origin access; no wildcard or credentialed CORS.
- Five-second request deadline; no secrets or database connections in browser assets.
- Tell the owner before editing existing files; do not change main or protection rules.

## Review Focus

- Missing or malformed local configuration must offer a recoverable setup message.
- Browser network errors cannot reliably distinguish CORS denial from an offline server.
- A stalled request must time out and re-enable the button.
- Hosted origins must never trigger requests to a visitor's loopback server.
- Bad status, JSON syntax, or JSON structure must not produce success or render HTML.

## Task 1: Explicit development CORS

**Files:** Modify `backend/main.py`, `backend/tests/test_main.py`.

**Interfaces:** Produce `create_app() -> FastAPI`, reading `SORT_TEST_DEV_ORIGINS` at construction, plus the existing module-level `app = create_app()` for Uvicorn. Preserve `GET /health` exactly.

- [ ] Add tests that construct the app with the environment isolated: unset origins gives no allow-origin header; the exact configured origin gets that header; a different origin does not. Assert credentials are not enabled and allowed GET preflight succeeds while disallowed origin/method preflight fails.
- [ ] Run the tests and confirm failures are due to missing CORS behavior/factory.
- [ ] Implement `create_app()` using existing CORSMiddleware, explicit origins, GET only, and no credentials. Reject wildcard/non-origin configuration at startup rather than silently broadening access.
- [ ] Add and pass startup-validation tests for wildcard, URL paths, malformed origins, and whitespace-separated comma entries. Retain the original health/404 tests.
- [ ] Run `python -m unittest discover -s backend/tests -v` with the local virtual environment, then commit only this task's files.

## Task 2: Independent browser page

**Files:** Create `dev/index.html`, `dev/health-client.mjs`, `dev/page.mjs`, `dev/config.example.json`, and `tests/health-client.test.mjs`; modify `.gitignore` for `/dev/config.local.json`.

**Interfaces:** `checkHealth({ pageOrigin, apiBaseUrl, fetchImpl, timeoutMs = 5000 }) -> Promise<{ kind, message }>` in `dev/health-client.mjs`; kinds are `success`, `configuration`, `unavailable`, and `invalid-response`. The page owns loading/disabled state and reads `config.local.json` without caching; the client owns URL validation, fetch, deadline, and response validation. Export `readConfig(response) -> Promise<{ apiBaseUrl: string }>` for tested config parsing.

- [ ] Write failing Node tests for exact success, non-200, malformed/wrong-shape JSON, rejected fetch, deadline expiry, missing/invalid config, non-loopback API URLs, and hosted-origin refusal with zero fetch calls. Assert requests omit credentials and reject redirects.
- [ ] Implement the smallest client passing those tests; cover clearing the deadline on all outcomes and handling response-body stalls within the deadline.
- [ ] Add the static HTML/button/status region and page controller. Render via textContent; disable during checking; use try/finally to restore retry on config and request failures.
- [ ] Commit the sanitized config example and ignore the local copy. Document that the local file is configuration, never a place for secrets.
- [ ] Run `node --test tests/*.test.mjs`, including the existing three security regressions.
- [ ] Browser-check loading, success, failure, and repeat clicks using actual servers; include malformed-body/config cases via temporary fixtures. Verify the deployed-origin guard before any fetch. Commit this task.

## Task 3: Windows instructions and hosted coverage

**Files:** Modify `backend/README.md`, root `README.md`, and `.github/workflows/security-regression.yml`.

**Interfaces:** Keep job names `Security regression tests` and `Windows backend tests` unchanged. The Node job runs `node --test tests/*.test.mjs`; the Windows job continues discovering backend unittest cases.

- [ ] Add repository-root PowerShell commands: copy the config example, serve only dev with the existing venv Python (`-m http.server 8000 --bind 127.0.0.1 --directory dev`), set `$env:SORT_TEST_DEV_ORIGINS = 'http://127.0.0.1:8000'`, and start Uvicorn on 127.0.0.1:18765 in another terminal. Include stop/cleanup instructions and explain that environment settings belong to the API terminal.
- [ ] Explain exact-origin matching, public retrieval of committed dev assets, local-only operation, expected messages, and troubleshooting. Link the guide only from developer documentation.
- [ ] Extend the existing Node workflow command to include both test files, preserving permissions/pins and required job names.
- [ ] Verify actual Windows browser success with both servers, then stop the API and confirm the useful unavailable message. Serve Practice separately on loopback port 8001 and verify guest entry, quiz feedback, and local results while the API stays stopped.
- [ ] Check `git diff --check`, ignored local config, unchanged Practice source, all Node tests, all backend tests, and both hosted jobs. Record exactly which machine supplied each verification. Stop temporary servers.
- [ ] Update issue #3 with evidence and open a reviewable PR; do not merge or mark Windows checks complete based on Mac-only results.

## Plan review

All issue #3 requirements map to these tasks. The public Pages behavior is explicitly recorded rather than assuming a dev directory is private. No new dependency, production endpoint, or employee-facing control is needed.
