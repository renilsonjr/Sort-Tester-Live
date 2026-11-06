# Development browser API bridge

## Intent and approved approach

Issue #3 proves that JavaScript in a browser can call the existing FastAPI
health endpoint. The owner selected a separate development test page, rather
than adding a development control to the employee home page. Keep this work on
`codex/ranked-mode` and explain each change before editing existing files.

The alternative home-page integration would make the request visible inside
the app, but would couple a connection exercise to the Practice interface.
Serving the test page through FastAPI itself would avoid CORS, but would not
exercise the separate frontend/API arrangement required by this issue.

## Local setup

- Serve only `dev/` at `http://127.0.0.1:8000` on Windows.
- Run FastAPI at `http://127.0.0.1:18765` in a second terminal.
- Copy a committed `dev/config.example.json` to ignored
  `dev/config.local.json`. Its sole setting is `apiBaseUrl`, initially
  `http://127.0.0.1:18765`. It contains no credentials.
- Accept only that loopback HTTP API URL for this milestone. The configuration
  file keeps machine configuration separate from the page and can be extended
  deliberately for a later LAN milestone.
- Configure backend `SORT_TEST_DEV_ORIGINS` as an explicit comma-separated
  allowlist. Unset means no cross-origin access. For this exercise set only
  `http://127.0.0.1:8000`; allow GET, no credentialed cross-origin requests.

These implementation details are proposed engineering choices following the
approved local page approach. Phone browser integration and public API hosting
are outside this milestone.

## Page and request behavior

```text
Development API check
[ Check API ]
Status: Ready / Checking… / API responded: ok / explanation of failure
```

Use a labeled button and an accessible status region. Disable the button during
each request. Only a user click starts the API check. Fetch `/health` without
credentials, enforce a five-second request deadline, and require HTTP 200 with
JSON matching the expected health contract. Render messages as text.

Distinguish missing/invalid configuration, an unexpected HTTP/body response,
and an unavailable request. A browser network failure can mean a stopped server
or a CORS block; give useful troubleshooting steps without claiming to know
which occurred. Allow retry after every settled request.

The page must refuse to request the API unless its own origin is exactly
`http://127.0.0.1:8000`. GitHub Pages serves this repository with `.nojekyll`:
the committed development resources will be publicly retrievable after merge,
but the page will be inert there. This is a usability guard, not access control.
Do not put secrets in any frontend file, including ignored local configuration.
Do not link the development page from the employee interface.

## Verification and limits

Test allowed and denied CORS origins, including default-denied configuration.
Test success, unavailable server, timeout, bad JSON, non-200 status, wrong JSON
shape, configuration errors, hosted-origin refusal, and retry behavior.
Run both existing regression suites. Verify actual browser requests with two
local servers, then stop the API and verify the failure message and that guest
Practice still works independently. Windows runtime verification happens on
the Windows machine; report Mac and hosted verification separately.

No database, authentication, Ranked rules, or production hosting are added.
