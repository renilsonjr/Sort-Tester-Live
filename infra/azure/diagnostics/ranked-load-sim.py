"""Ranked load simulation: N players for D seconds (issue #13, load item).

Four steps, one subcommand each:

    create     sign up throwaway accounts through the public sign-up route
    run        play Ranked quizzes as those accounts and measure
    reconcile  check each account's balance against its own history
    cleanup    delete the accounts through the app's own deletion route

`run`: each simulated player logs in and plays Ranked quizzes back to back
the way the page does: start, read the current question, think, answer,
press Next, with a heartbeat every second, reading balance, leaderboard,
profile stats and history between quizzes. Along the way it checks what
the load item names: another player's attempt must not be readable, a
question's deadline must not move when it is read again, and a repeated
answer must not count twice. It stops by itself (see STOP RULE below).
It needs `httpx`, which the backend virtualenv already has.

THIS PLAYS REAL ATTEMPTS AND CHANGES BALANCES. Every subcommand refuses a
target that is not this machine unless --allow-remote is given, and the
hosted app holds real employee accounts: running it there is an owner
decision, taken for each step. Two guards do not depend on that decision:

- An account is used only if the app says its username starts with the
  prefix (default `loadtest_`). A file holding a real player's Quiz Code
  by mistake is therefore never played and never deleted.
- A Quiz Code is never printed and never written to a report. The accounts
  file is created readable by its owner only. Keep it out of the
  repository and delete it when the accounts are gone.

STOP RULE. `run` stops starting and playing quizzes, and says why, when:

- 10 or more requests in the last 30 seconds failed in the server or in
  the network (HTTP 5xx or no response); or
- after the first minute, the slowest 5% of the requests of the last 60
  seconds took more than 3 seconds; or
- the file named by --stop-file exists (create it to stop by hand); or
- Ctrl-C.

A stopped run still writes its report. Attempts left open end by the
app's own rules when their account is next heard from, so wait a minute
before `reconcile`.

Local rehearsal, from the repository root (database name is an example):

    createdb sort_tester_load
    export SORT_TESTER_DATABASE_URL=postgresql://localhost:5432/sort_tester_load
    backend/.venv/bin/python -m backend.db.upgrade_app --confirm sort_tester_load@localhost:5432
    backend/.venv/bin/python - <<'PY'
    from backend.db import migrate, settings
    from backend.ranked import seasons
    conn = migrate.connect(settings.app_database_url())
    seasons.ensure_pre_season(conn)   # a fresh database has no season
    conn.commit()
    PY
    backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8094 --no-access-log &
    SIM="backend/.venv/bin/python infra/azure/diagnostics/ranked-load-sim.py"
    $SIM create    --base http://127.0.0.1:8094 --accounts accounts.json --count 31
    $SIM run       --base http://127.0.0.1:8094 --accounts accounts.json --players 30 \
                   --seconds 900 --out report.json
    $SIM reconcile --base http://127.0.0.1:8094 --accounts accounts.json --report report.json
    $SIM cleanup   --base http://127.0.0.1:8094 --accounts accounts.json

Sign-up allows 30 accounts an hour from one address, so `create` stops at
the limit and can be run again later: it continues the same file. The
31st account does not play; `cleanup` uses it to read the leaderboard after
the others are deleted, then deletes it too.
"""
import argparse
import asyncio
import json
import os
import random
import signal
import sys
import time
from collections import deque
from urllib.parse import urlsplit

import httpx

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
CAP = "X-Attempt-Capability"

ERROR_WINDOW_SECONDS = 30.0
ERROR_LIMIT = 10
SLOW_WINDOW_SECONDS = 60.0
SLOW_P95_SECONDS = 3.0
SLOW_MIN_SAMPLES = 30


# ---------------------------------------------------------------- pure parts

def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


def stop_reason(now, started, events):
    """Why a run should stop now, or None. ``events`` is an iterable of
    (finished_at, seconds, failed) for the requests made so far."""
    events = list(events)
    failures = sum(1 for at, _, failed in events if failed and now - at <= ERROR_WINDOW_SECONDS)
    if failures >= ERROR_LIMIT:
        return f"{failures} failed requests in the last {ERROR_WINDOW_SECONDS:.0f} seconds"
    if now - started >= SLOW_WINDOW_SECONDS:
        recent = [seconds for at, seconds, failed in events
                  if not failed and now - at <= SLOW_WINDOW_SECONDS]
        if len(recent) >= SLOW_MIN_SAMPLES and pct(recent, .95) > SLOW_P95_SECONDS:
            return (f"slowest 5% of the last {SLOW_WINDOW_SECONDS:.0f} seconds took more than "
                    f"{SLOW_P95_SECONDS:.0f} seconds ({pct(recent, .95):.1f} s)")
    return None


def history_problems(history, points_now, finished_ids=()):
    """What is wrong with one account's history (newest first), given the
    balance the app reports now and the attempts the run saw finish.
    An empty list means the account reconciles."""
    found = []
    ids = [entry["attempt_id"] for entry in history]
    if len(set(ids)) != len(ids):
        found.append("an attempt appears twice in the history")
    for newer, older in zip(history, history[1:]):
        if older["points_after"] != newer["points_before"]:
            found.append(f"balance jumps between attempts {older['attempt_id']} and {newer['attempt_id']}")
    for entry in history:
        if entry["points_after"] - entry["points_before"] != entry["adjustment"]:
            found.append(f"attempt {entry['attempt_id']} moved the balance by something other than its adjustment")
    if history and history[-1]["points_before"] != 0:
        found.append("the first attempt did not start from zero")
    expected = history[0]["points_after"] if history else 0
    if points_now != expected:
        found.append(f"balance is {points_now} but the history ends at {expected}")
    for attempt_id in finished_ids:
        if ids.count(attempt_id) != 1:
            found.append(f"finished attempt {attempt_id} is in the history {ids.count(attempt_id)} times")
    return found


def read_accounts(path):
    """The accounts file: a list of {"username", "login_id"}."""
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return json.load(handle)


def write_accounts(path, accounts):
    # owner-only from the first byte: the file holds Quiz Codes
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as handle:
        json.dump(accounts, handle)
    os.chmod(path, 0o600)


# ------------------------------------------------------------------ plumbing

class Run:
    """What one invocation measures."""

    def __init__(self, base, prefix):
        self.base = base.rstrip("/")
        self.prefix = prefix
        self.lat = {}            # endpoint -> [seconds]
        self.statuses = {}       # (endpoint, status) -> count
        self.problems = []       # human-readable findings
        self.events = deque()    # (finished_at, seconds, failed), for the stop rule
        self.attempt_ids = []    # (player, attempt) started, for cross-account probes
        self.finished = {}       # username -> [attempt ids whose result was read]
        self.counters = {"attempts_started": 0, "attempts_finished": 0, "answers": 0,
                         "timeouts_seen": 0, "leak_probes": 0, "deadline_checks": 0,
                         "duplicate_answers": 0}
        self.stop = asyncio.Event()
        self.stopped_because = None

    def client(self):
        return httpx.AsyncClient(base_url=self.base, headers={"Origin": self.base}, timeout=30)

    def halt(self, reason):
        if not self.stop.is_set():
            self.stopped_because = reason
            self.stop.set()

    async def call(self, client, name, method, path, **kw):
        t0 = time.perf_counter()
        try:
            r = await client.request(method, path, **kw)
        except Exception as exc:  # network-level failure
            self.statuses[(name, "EXC")] = self.statuses.get((name, "EXC"), 0) + 1
            self.problems.append(f"{name}: {type(exc).__name__}")
            self.events.append((time.time(), time.perf_counter() - t0, True))
            return None
        seconds = time.perf_counter() - t0
        self.lat.setdefault(name, []).append(seconds)
        self.statuses[(name, r.status_code)] = self.statuses.get((name, r.status_code), 0) + 1
        self.events.append((time.time(), seconds, r.status_code >= 500))
        if r.status_code >= 500:
            self.problems.append(f"{name}: HTTP {r.status_code} {r.text[:120]}")
        return r

    async def login(self, client, account):
        """Sign in and return the username, or None. An account whose
        username lacks the prefix is signed out again and refused: it is
        not one of ours, whatever the file says."""
        r = await self.call(client, "login", "POST", "/api/auth/login",
                            json={"login_id": account["login_id"]})
        if r is None or r.status_code != 200:
            self.problems.append(f"{account.get('username', 'an account')} could not log in")
            return None
        username = r.json()["username"]
        if not username.startswith(self.prefix):
            await self.call(client, "logout", "POST", "/api/auth/logout")
            self.problems.append(f"REFUSED: an account in the file is not a {self.prefix} account")
            return None
        return username

    def summary(self):
        return {
            "latency_ms": {k: {"n": len(v), "p50": round(pct(v, .5) * 1000, 1),
                               "p95": round(pct(v, .95) * 1000, 1), "max": round(max(v) * 1000, 1)}
                           for k, v in sorted(self.lat.items())},
            "statuses": {f"{k[0]} {k[1]}": n
                         for k, n in sorted(self.statuses.items(), key=lambda x: (x[0][0], str(x[0][1])))},
            "problems": self.problems[:50], "problem_count": len(self.problems),
        }


def pick(options):
    o = random.choice(options)
    if isinstance(o, dict):
        for k in ("belt", "choice", "value", "id", "key", "label"):
            if k in o:
                return o[k]
    return o


async def pause(run, seconds):
    """Sleep, but wake at once when the run is stopped."""
    try:
        await asyncio.wait_for(run.stop.wait(), timeout=seconds)
    except asyncio.TimeoutError:
        pass


# ----------------------------------------------------------------------- run

async def heartbeat(run, client, aid, headers, done):
    while not done.is_set() and not run.stop.is_set():
        await run.call(client, "heartbeat", "POST", f"/api/ranked/attempts/{aid}/heartbeat", headers=headers)
        try:
            await asyncio.wait_for(done.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass


async def play_one(run, client, me, username, end_at):
    r = await run.call(client, "start", "POST", "/api/ranked/attempts", json={"mode": "normal"})
    if r is None or r.status_code != 201:
        await pause(run, 2)
        return
    body = r.json()
    aid, headers = body["attempt_id"], {CAP: body["capability"]}
    run.attempt_ids.append((me, aid))
    run.counters["attempts_started"] += 1
    done = asyncio.Event()
    beat = asyncio.create_task(heartbeat(run, client, aid, headers, done))
    try:
        for _ in range(20):
            if run.stop.is_set():
                return
            r = await run.call(client, "current", "GET", f"/api/ranked/attempts/{aid}/current", headers=headers)
            if r is None or r.status_code != 200:
                break
            q = r.json()
            seq, deadline = q["seq"], q["deadline_at"]
            # the deadline must not move when the question is read again
            if random.random() < 0.3:
                r2 = await run.call(client, "current", "GET", f"/api/ranked/attempts/{aid}/current", headers=headers)
                run.counters["deadline_checks"] += 1
                if r2 is not None and r2.status_code == 200:
                    q2 = r2.json()
                    if q2["seq"] == seq and q2["deadline_at"] != deadline:
                        run.problems.append(f"deadline moved for attempt {aid} seq {seq}")
            # another player's attempt must not be readable
            if random.random() < 0.1 and run.attempt_ids:
                other_me, other_aid = random.choice(run.attempt_ids)
                if other_me != me:
                    run.counters["leak_probes"] += 1
                    for hdrs in ({}, headers):
                        r3 = await run.call(client, "leak_probe", "GET", f"/api/ranked/attempts/{other_aid}/current", headers=hdrs)
                        if r3 is not None and r3.status_code == 200:
                            run.problems.append(f"LEAK: player {me} read attempt {other_aid}")
                        r4 = await run.call(client, "leak_probe", "GET", f"/api/ranked/attempts/{other_aid}/result", headers=hdrs)
                        if r4 is not None and r4.status_code == 200:
                            run.problems.append(f"LEAK: player {me} read result {other_aid}")
            # think like a person; now and then too slowly (a timeout)
            slow = random.random() < 0.04
            await pause(run, random.uniform(10.5, 11.5) if slow else random.uniform(1.0, 5.0))
            if run.stop.is_set():
                return
            if slow:
                run.counters["timeouts_seen"] += 1
            choice = pick(q["options"])
            r = await run.call(client, "answer", "POST", f"/api/ranked/attempts/{aid}/answer",
                               headers=headers, json={"seq": seq, "choice": choice})
            if r is None:
                break
            run.counters["answers"] += 1
            finished = r.status_code == 200 and r.json().get("finished")
            # the same answer sent again must not be counted a second time
            if random.random() < 0.1:
                run.counters["duplicate_answers"] += 1
                await run.call(client, "answer_repeat", "POST", f"/api/ranked/attempts/{aid}/answer",
                               headers=headers, json={"seq": seq, "choice": choice})
            if finished:
                break
            await pause(run, random.uniform(0.3, 1.2))
            await run.call(client, "advance", "POST", f"/api/ranked/attempts/{aid}/advance", headers=headers)
            if time.time() > end_at + 240:
                break
    finally:
        done.set()
        await beat
    r = await run.call(client, "result", "GET", f"/api/ranked/attempts/{aid}/result", headers=headers)
    if r is not None and r.status_code == 200:
        run.counters["attempts_finished"] += 1
        run.finished.setdefault(username, []).append(aid)


async def player(run, me, account, end_at):
    async with run.client() as client:
        username = await run.login(client, account)
        if username is None:
            return
        await pause(run, random.uniform(0, 5))
        while time.time() < end_at and not run.stop.is_set():
            await play_one(run, client, me, username, end_at)
            if run.stop.is_set():
                break
            for path, name in (("/api/ranked/entry", "entry"), ("/api/ranked/leaderboard", "leaderboard"),
                               ("/api/ranked/profile/stats", "stats"), ("/api/ranked/history?phase=pre_season", "history")):
                await run.call(client, name, "GET", path)
            await pause(run, random.uniform(1, 4))


async def watchdog(run, started, stop_file):
    while not run.stop.is_set():
        now = time.time()
        while run.events and now - run.events[0][0] > SLOW_WINDOW_SECONDS:
            run.events.popleft()
        reason = stop_reason(now, started, run.events)
        if reason is None and stop_file and os.path.exists(stop_file):
            reason = "stop file found"
        if reason:
            run.halt(reason)
            return
        await pause(run, 2)


async def do_run(args):
    accounts = read_accounts(args.accounts)
    if args.players:
        accounts = accounts[:args.players]
    if not accounts:
        sys.exit("no accounts in the file; run `create` first")
    run = Run(args.base, args.prefix)
    asyncio.get_running_loop().add_signal_handler(signal.SIGINT, run.halt, "interrupted by hand")
    started = time.time()
    end_at = started + args.seconds
    guard = asyncio.create_task(watchdog(run, started, args.stop_file))
    await asyncio.gather(*(player(run, i, account, end_at) for i, account in enumerate(accounts)))
    reason = run.stopped_because
    run.stop.set()
    await guard
    report = {
        "players": len(accounts), "planned_seconds": args.seconds,
        "wall_seconds": round(time.time() - started, 1),
        "stopped_early": reason, "counters": run.counters,
        **run.summary(), "finished_attempts": run.finished,
    }
    with open(args.out, "w") as handle:
        json.dump(report, handle, indent=1)
    shown = dict(report)
    shown["finished_attempts"] = {name: len(ids) for name, ids in run.finished.items()}
    print(json.dumps(shown, indent=1))
    return 1 if reason or run.problems else 0


# -------------------------------------------------------------------- create

async def do_create(args):
    accounts = read_accounts(args.accounts)
    have = {account["username"] for account in accounts}
    run = Run(args.base, args.prefix)
    made, limited, taken = 0, False, []
    async with run.client() as client:
        for number in range(1, args.count + 1):
            username = f"{args.prefix}{number:02d}"
            if username in have:
                continue
            r = await run.call(client, "register", "POST", "/api/auth/register", json={"username": username})
            if r is None:
                break
            if r.status_code == 429:
                limited = True
                break
            if r.status_code == 409:
                # somebody holds the name and this file has no code for it
                taken.append(username)
                continue
            if r.status_code != 200:
                run.problems.append(f"register {username}: HTTP {r.status_code}")
                break
            accounts.append({"username": username, "login_id": r.json()["login_id"]})
            write_accounts(args.accounts, accounts)   # after each one: nothing is lost if this stops
            made += 1
            await asyncio.sleep(0.5)
    print(json.dumps({
        "created_now": made, "in_file": len(accounts), "wanted": args.count,
        "sign_up_limit_reached": limited, "names_already_taken": taken,
        "problems": run.problems,
    }, indent=1))
    if limited:
        print("The sign-up limit was reached. Run the same command again in an hour.")
    return 0 if len(accounts) >= args.count else 1


# ----------------------------------------------------------------- reconcile

async def do_reconcile(args):
    accounts = read_accounts(args.accounts)
    finished = {}
    if args.report:
        with open(args.report) as handle:
            finished = json.load(handle).get("finished_attempts", {})
    run = Run(args.base, args.prefix)
    checked, wrong, attempts = 0, {}, 0
    for account in accounts:
        async with run.client() as client:
            username = await run.login(client, account)
            if username is None:
                wrong[account.get("username", "?")] = ["could not be checked"]
                continue
            found = None
            for _ in range(2):   # an open attempt may settle between the two reads
                h = await run.call(client, "history", "GET", "/api/ranked/history")
                e = await run.call(client, "entry", "GET", "/api/ranked/entry")
                if h is None or e is None or h.status_code != 200 or e.status_code != 200:
                    found = ["history or balance could not be read"]
                    break
                history = h.json()
                found = history_problems(history, e.json()["points"], finished.get(username, ()))
                if not found:
                    break
                await asyncio.sleep(2)
            checked += 1
            attempts += len(history) if not found else 0
            if found:
                wrong[username] = found
            await run.call(client, "logout", "POST", "/api/auth/logout")
    print(json.dumps({
        "accounts_checked": checked, "accounts_in_file": len(accounts),
        "attempts_in_histories": attempts, "accounts_that_do_not_reconcile": wrong,
        "problems": run.problems,
    }, indent=1))
    return 1 if wrong or run.problems else 0


# ------------------------------------------------------------------- cleanup

async def delete_account(run, client, account):
    r = await run.call(client, "delete", "POST", "/api/auth/account/delete",
                       json={"login_id": account["login_id"], "acknowledge": True})
    return r is not None and r.status_code == 202


async def do_cleanup(args):
    accounts = read_accounts(args.accounts)
    if not accounts:
        sys.exit("no accounts in the file")
    run = Run(args.base, args.prefix)
    *others, witness = accounts
    deleted, kept = [], []
    for account in others:
        async with run.client() as client:
            username = await run.login(client, account)
            if username is None:
                kept.append(account)
                continue
            if await delete_account(run, client, account):
                deleted.append(username)
            else:
                run.problems.append(f"{username} was not deleted")
                kept.append(account)
    # the last account looks at the leaderboard, then goes too
    left_on_board = None
    async with run.client() as client:
        username = await run.login(client, witness)
        if username is None:
            kept.append(witness)
        else:
            r = await run.call(client, "leaderboard", "GET", "/api/ranked/leaderboard")
            if r is not None and r.status_code == 200:
                left_on_board = [row["username"] for row in r.json()["rows"]
                                 if row["username"].startswith(args.prefix) and row["username"] != username]
                if left_on_board:
                    run.problems.append(f"{len(left_on_board)} test accounts are still on the leaderboard")
            if await delete_account(run, client, witness):
                deleted.append(username)
            else:
                run.problems.append(f"{username} was not deleted")
                kept.append(witness)
    # a deleted account's code must no longer open anything
    still_open = 0
    for account in accounts:
        if account in kept:
            continue
        async with run.client() as client:
            r = await client.post("/api/auth/login", json={"login_id": account["login_id"]})
            if r.status_code != 401:
                still_open += 1
    if still_open:
        run.problems.append(f"{still_open} deleted accounts could still log in")
    write_accounts(args.accounts, kept)   # only what could not be deleted stays
    print(json.dumps({
        "deleted": len(deleted), "not_deleted": len(kept),
        "test_accounts_left_on_leaderboard": left_on_board,
        "deleted_accounts_that_still_log_in": still_open,
        "problems": run.problems,
    }, indent=1))
    if not kept:
        print("Every account is gone. The accounts file is now empty and can be deleted.")
    return 1 if kept or run.problems else 0


# ---------------------------------------------------------------------- main

def _arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    steps = parser.add_subparsers(dest="step", required=True)

    def step(name, text):
        sub = steps.add_parser(name, help=text)
        sub.add_argument("--base", required=True, help="origin of the app, e.g. http://127.0.0.1:8094")
        sub.add_argument("--accounts", required=True, help="JSON file of the throwaway accounts (holds Quiz Codes)")
        sub.add_argument("--prefix", default="loadtest_", help="usernames this tool may touch start with this")
        sub.add_argument("--allow-remote", action="store_true",
                         help="permit a target that is not this machine (owner decision; see the module docstring)")
        return sub

    create = step("create", "sign up the throwaway accounts")
    create.add_argument("--count", type=int, default=31)
    run = step("run", "play Ranked quizzes and measure")
    run.add_argument("--players", type=int, default=0, help="use only the first N accounts (0: all)")
    run.add_argument("--seconds", type=float, default=900.0, help="how long players keep starting quizzes")
    run.add_argument("--out", required=True, help="where to write the JSON report")
    run.add_argument("--stop-file", default="", help="the run stops when this file exists")
    reconcile = step("reconcile", "check balances against histories")
    reconcile.add_argument("--report", default="", help="the report of the run, to look for each finished attempt")
    step("cleanup", "delete the accounts")

    args = parser.parse_args(argv)
    host = urlsplit(args.base).hostname or ""
    if host not in LOCAL_HOSTS and not args.allow_remote:
        parser.error(f"{host!r} is not this machine; this tool plays real attempts. "
                     "Pass --allow-remote only with the owner's go-ahead for this step.")
    if not args.prefix or not args.prefix.replace("_", "").isalnum() or len(args.prefix) > 20:
        parser.error("the prefix must be 1-20 letters, digits or underscores")
    return args


STEPS = {"create": do_create, "run": do_run, "reconcile": do_reconcile, "cleanup": do_cleanup}

if __name__ == "__main__":
    ARGS = _arguments()
    sys.exit(asyncio.run(STEPS[ARGS.step](ARGS)))
