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
node --test tests\security.test.mjs
```

The first command checks the health response and an unknown route. The second
rechecks the existing browser security regressions.
