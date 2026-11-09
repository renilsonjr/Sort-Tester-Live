# Backend development on Windows

Run these commands from the repository root in PowerShell. Use the virtual
environment's Python directly; PowerShell activation is not required.

## Set up a fresh environment

Use an installed Python 3.14 interpreter and confirm its version first. The
hosted Windows check used Python 3.14.10. From a fresh clone, run:

```powershell
python --version
python -m venv backend\.venv
& backend\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
& backend\.venv\Scripts\python.exe -m pip check
```

Continue only when each command succeeds and the dependency check reports no
broken requirements. These are the same environment-creation and installation
steps exercised by the Windows CI job. An existing working environment can be
used directly; recreating it is not necessary for every server start. Each
computer needs its own virtual environment.

## Start the API on this computer only

```powershell
& backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 18765
```

Open `http://127.0.0.1:18765/health`. A successful response is HTTP 200 with
`{"status":"ok"}`. This checks that the API responds; it does not check a
database.

## Test from a phone on the same trusted home network

Find this computer's current Wi-Fi IPv4 address:

```powershell
Get-NetIPAddress -InterfaceAlias 'Wi-Fi' -AddressFamily IPv4
```

Start the API bound to that specific address, replacing the example address if
it has changed:

```powershell
& backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 192.168.1.197 --port 18765
```

On the computer, open `http://192.168.1.197:18765/health`, then open the same
URL on the phone while it is connected to the same Wi-Fi. The address can
change when the computer reconnects. Keep this development server on a trusted
local network; do not forward the port on the router.

Stop the server with **Ctrl+C** in the PowerShell window running it.

## Run tests

```powershell
& backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
node --test tests/security.test.mjs tests/health-client.test.mjs
```

The first command checks health, unknown routes, and development CORS settings.
The second checks browser request handling and existing security regressions.

## Check the API from a development browser page

This exercise uses two PowerShell windows, both at the repository root.
It runs locally on this computer; it is not the phone/LAN exercise above.

In **window 1**, allow the exact development page origin and start FastAPI:

```powershell
$env:SORT_TEST_DEV_ORIGINS = 'http://127.0.0.1:8000'
& backend\.venv\Scripts\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 18765
```

The environment variable belongs in the same window that starts the API.
Unset or blank means no cross-origin reading is authorized. Wildcards and
malformed origins stop startup with an error. Multiple explicit origins may
be comma-separated, but this exercise needs only the one above. This follows
[FastAPI's CORS setup](https://fastapi.tiangolo.com/tutorial/cors/).

In **window 2**, create local configuration if it does not already exist,
then serve only the development folder:

```powershell
if (-not (Test-Path dev\config.local.json)) {
    Copy-Item dev\config.example.json dev\config.local.json
}
& backend\.venv\Scripts\python.exe -m http.server 8000 --bind 127.0.0.1 --directory dev
```

The local JSON file must contain only:

```json
{"apiBaseUrl":"http://127.0.0.1:18765"}
```

Git ignores `dev/config.local.json`; each computer creates its own copy.
It is browser-readable configuration, **never a place for passwords, tokens,
employee data, or database connection strings**. This milestone accepts only
the loopback API URL shown above.

Open **http://127.0.0.1:8000** and select **Check API**:

- During the request: Checking… and a disabled button.
- Working API: API responded: ok (HTTP 200).
- Stopped API or blocked request: a message asking you to check the server,
  address, and CORS settings. Browsers cannot reliably distinguish those causes.
- Unexpected HTTP status or JSON: an unexpected-response message.
- Missing/invalid local file: instructions to copy the config example.
- No response within five seconds: timeout, followed by an enabled retry button.

Use `127.0.0.1` exactly. `localhost`, a different port, and HTTPS are different
origins. CORS lets the browser read a cross-origin response; it is not a login,
firewall, or general access-control mechanism. No credentials are sent.

Only clicking the button starts the config/API check. The page refuses to run
outside `http://127.0.0.1:8000`. Because GitHub Pages publishes the repository
root with `.nojekyll`, committed development files are publicly retrievable
after merging, but this check is disabled there. There is no link to it from
the employee interface. No public backend is configured.

### Verify failure and independent Practice

1. Confirm success with both servers running.
2. In window 1, stop the API with **Ctrl+C**. Click Check API again; confirm the
   useful unavailable message and that you can retry.
3. In a third repository-root PowerShell window, serve the existing Practice app:

   ```powershell
   & backend\.venv\Scripts\python.exe -m http.server 8001 --bind 127.0.0.1
   ```

4. Open http://127.0.0.1:8001 with the API still stopped. Enter as a guest,
   complete a Practice quiz, check feedback/results, then reload and check the
   local shift log. Use fictional data. Results are stored separately for each
   browser origin, so port 8001 does not share port 8000's saved results.
5. Stop both page servers with **Ctrl+C** in their windows. In the API window,
   clear the development setting after stopping the API:

   ```powershell
   Remove-Item Env:SORT_TEST_DEV_ORIGINS -ErrorAction SilentlyContinue
   ```

If a port is already occupied, stop the earlier test server you started before
retrying. Do not kill unfamiliar processes or change firewall/router settings
for this loopback exercise.

## Verify the reviewed Ranked bank

From the repository root, this command loads the pinned reviewed bank and
prepares one compatible assignment. It prints the revision, digest, counts and
ordered review references, without an answer key. It needs no server or database:

```powershell
& backend\.venv\Scripts\python.exe -m backend.ranked_bank.check --revision ranked-routes-v1 --seed 42
```

Expect 15 questions: five Easy, five Medium and five Hard. Repeat seed 42 on
Python 3.14 to compare the same ordered references across Windows and macOS.
Omit `--seed` to use operating-system randomness. Invalid or unavailable banks
produce an error on stderr and a nonzero exit, with no partial assignment.

Run all backend tests, then the existing JavaScript regression tests:

```powershell
& backend\.venv\Scripts\python.exe -m unittest discover -s backend\tests -v
node --test tests/*.test.mjs
```

On macOS, use `backend/.venv/bin/python` in place of the Windows Python command.
The selector returns immutable internal snapshots preserving reviewed examples
and bilingual feedback; serialization includes answers and is for internal use.
Later attempt code must call selection before starting an attempt. These checks
do not verify a browser, deployment, persistence, API or game scoring.
