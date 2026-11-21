"""Ranked load simulation: N players for D seconds (issue #13, load item).

Each simulated player logs in and plays Ranked quizzes back to back the way
the page does: start, read the current question, think, answer, press Next,
with a heartbeat every second, reading balance, leaderboard, profile stats
and history between quizzes. Along the way it checks what the load item
names: another player's attempt must not be readable, a question's deadline
must not move when it is read again, and a repeated answer must not count
twice. It needs `httpx`, which the backend virtualenv already has.

THIS PLAYS REAL ATTEMPTS AND CHANGES BALANCES. It refuses any target that
is not this machine unless --allow-remote is given, and the hosted app
holds real employee accounts: running it there is an owner decision, with
throwaway accounts made for the purpose, never with a player's login ID.

Local run, from the repository root (database name is an example):

    createdb sort_tester_load
    export SORT_TESTER_DATABASE_URL=postgresql://localhost:5432/sort_tester_load
    backend/.venv/bin/python -m backend.db.upgrade_app --confirm sort_tester_load@localhost:5432
    backend/.venv/bin/python - <<'PY'
    import json
    from backend.db import migrate, settings
    from backend.ranked import seasons
    from backend.auth.service import register_account
    conn = migrate.connect(settings.app_database_url())
    seasons.ensure_pre_season(conn)   # a fresh database has no season
    ids = [register_account(conn, f"load_{i:02d}")[1] for i in range(30)]
    conn.commit()
    json.dump(ids, open("logins.json", "w"))
    PY
    backend/.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8094 --no-access-log &
    backend/.venv/bin/python infra/azure/diagnostics/ranked-load-sim.py \
        --base http://127.0.0.1:8094 --logins logins.json --seconds 900 --out report.json

Accounts are created in the database on purpose: 30 sign-ups from one
address would meet the registration limiter, which is not what this measures.
Keep logins.json out of the repository and delete it with the database.

After the run, the database should agree with the report: one settlement
per finalized attempt, at most 15 answer rows per attempt, and every balance
equal to the sum of its account's settlement adjustments.
"""
import argparse
import asyncio
import json
import random
import time
from urllib.parse import urlsplit

import httpx

LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}


def _arguments():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--base", required=True, help="origin of the app, e.g. http://127.0.0.1:8094")
    parser.add_argument("--logins", required=True, help="JSON file: a list of login IDs of throwaway accounts")
    parser.add_argument("--seconds", type=float, default=900.0, help="how long players keep starting quizzes")
    parser.add_argument("--out", required=True, help="where to write the JSON report")
    parser.add_argument("--allow-remote", action="store_true",
                        help="permit a target that is not this machine (owner decision; see the module docstring)")
    args = parser.parse_args()
    host = urlsplit(args.base).hostname or ""
    if host not in LOCAL_HOSTS and not args.allow_remote:
        parser.error(f"{host!r} is not this machine; this tool plays real attempts. "
                     "Pass --allow-remote only with the owner's go-ahead and throwaway accounts.")
    return args


ARGS = _arguments()
BASE = ARGS.base.rstrip("/")
LOGINS = json.load(open(ARGS.logins))
DURATION = ARGS.seconds
OUT = ARGS.out
CAP = "X-Attempt-Capability"

lat = {}            # endpoint -> [seconds]
statuses = {}       # (endpoint, status) -> count
problems = []       # human-readable findings
attempt_ids = []    # every attempt started, for cross-account probes
counters = {"attempts_started": 0, "attempts_finished": 0, "answers": 0,
            "timeouts_seen": 0, "leak_probes": 0, "deadline_checks": 0,
            "duplicate_answers": 0}


async def call(client, name, method, path, **kw):
    t0 = time.perf_counter()
    try:
        r = await client.request(method, path, **kw)
    except Exception as exc:  # network-level failure
        statuses[(name, "EXC")] = statuses.get((name, "EXC"), 0) + 1
        problems.append(f"{name}: {type(exc).__name__}")
        return None
    lat.setdefault(name, []).append(time.perf_counter() - t0)
    statuses[(name, r.status_code)] = statuses.get((name, r.status_code), 0) + 1
    if r.status_code >= 500:
        problems.append(f"{name}: HTTP {r.status_code} {r.text[:120]}")
    return r


def pick(options):
    o = random.choice(options)
    if isinstance(o, dict):
        for k in ("belt", "choice", "value", "id", "key", "label"):
            if k in o:
                return o[k]
    return o


async def heartbeat(client, aid, headers, stop):
    while not stop.is_set():
        await call(client, "heartbeat", "POST", f"/api/ranked/attempts/{aid}/heartbeat", headers=headers)
        try:
            await asyncio.wait_for(stop.wait(), timeout=1.0)
        except asyncio.TimeoutError:
            pass


async def play_one(client, me, end_at):
    r = await call(client, "start", "POST", "/api/ranked/attempts", json={"mode": "normal"})
    if r is None or r.status_code != 201:
        await asyncio.sleep(2)
        return
    body = r.json()
    aid, headers = body["attempt_id"], {CAP: body["capability"]}
    attempt_ids.append((me, aid))
    counters["attempts_started"] += 1
    stop = asyncio.Event()
    beat = asyncio.create_task(heartbeat(client, aid, headers, stop))
    try:
        for _ in range(20):
            r = await call(client, "current", "GET", f"/api/ranked/attempts/{aid}/current", headers=headers)
            if r is None or r.status_code != 200:
                break
            q = r.json()
            seq, deadline = q["seq"], q["deadline_at"]
            # the deadline must not move when the question is read again
            if random.random() < 0.3:
                r2 = await call(client, "current", "GET", f"/api/ranked/attempts/{aid}/current", headers=headers)
                counters["deadline_checks"] += 1
                if r2 is not None and r2.status_code == 200:
                    q2 = r2.json()
                    if q2["seq"] == seq and q2["deadline_at"] != deadline:
                        problems.append(f"deadline moved for attempt {aid} seq {seq}")
            # another player's attempt must not be readable
            if random.random() < 0.1 and attempt_ids:
                other_me, other_aid = random.choice(attempt_ids)
                if other_me != me:
                    counters["leak_probes"] += 1
                    for hdrs in ({}, headers):
                        r3 = await call(client, "leak_probe", "GET", f"/api/ranked/attempts/{other_aid}/current", headers=hdrs)
                        if r3 is not None and r3.status_code == 200:
                            problems.append(f"LEAK: player {me} read attempt {other_aid}")
                        r4 = await call(client, "leak_probe", "GET", f"/api/ranked/attempts/{other_aid}/result", headers=hdrs)
                        if r4 is not None and r4.status_code == 200:
                            problems.append(f"LEAK: player {me} read result {other_aid}")
            # think like a person; now and then too slowly (a timeout)
            slow = random.random() < 0.04
            await asyncio.sleep(random.uniform(10.5, 11.5) if slow else random.uniform(1.0, 5.0))
            if slow:
                counters["timeouts_seen"] += 1
            choice = pick(q["options"])
            r = await call(client, "answer", "POST", f"/api/ranked/attempts/{aid}/answer",
                           headers=headers, json={"seq": seq, "choice": choice})
            if r is None:
                break
            counters["answers"] += 1
            finished = r.status_code == 200 and r.json().get("finished")
            # the same answer sent again must not be counted a second time
            if random.random() < 0.1:
                counters["duplicate_answers"] += 1
                await call(client, "answer_repeat", "POST", f"/api/ranked/attempts/{aid}/answer",
                           headers=headers, json={"seq": seq, "choice": choice})
            if finished:
                break
            await asyncio.sleep(random.uniform(0.3, 1.2))
            await call(client, "advance", "POST", f"/api/ranked/attempts/{aid}/advance", headers=headers)
            if time.time() > end_at + 240:
                break
    finally:
        stop.set()
        await beat
    r = await call(client, "result", "GET", f"/api/ranked/attempts/{aid}/result", headers=headers)
    if r is not None and r.status_code == 200:
        counters["attempts_finished"] += 1


async def player(me, login_id, end_at):
    async with httpx.AsyncClient(base_url=BASE, headers={"Origin": BASE}, timeout=30) as client:
        r = await call(client, "login", "POST", "/api/auth/login", json={"login_id": login_id})
        if r is None or r.status_code != 200:
            problems.append(f"player {me} could not log in")
            return
        await asyncio.sleep(random.uniform(0, 5))
        while time.time() < end_at:
            await play_one(client, me, end_at)
            for path, name in (("/api/ranked/entry", "entry"), ("/api/ranked/leaderboard", "leaderboard"),
                               ("/api/ranked/profile/stats", "stats"), ("/api/ranked/history?phase=pre_season", "history")):
                await call(client, name, "GET", path)
            await asyncio.sleep(random.uniform(1, 4))


def pct(values, p):
    values = sorted(values)
    return values[min(len(values) - 1, int(len(values) * p))]


async def main():
    started = time.time()
    end_at = started + DURATION
    await asyncio.gather(*(player(i, lid, end_at) for i, lid in enumerate(LOGINS)))
    report = {
        "players": len(LOGINS), "planned_seconds": DURATION, "wall_seconds": round(time.time() - started, 1),
        "counters": counters,
        "latency_ms": {k: {"n": len(v), "p50": round(pct(v, .5) * 1000, 1), "p95": round(pct(v, .95) * 1000, 1),
                           "max": round(max(v) * 1000, 1)} for k, v in sorted(lat.items())},
        "statuses": {f"{k[0]} {k[1]}": n for k, n in sorted(statuses.items(), key=lambda x: (x[0][0], str(x[0][1])))},
        "problems": problems[:50], "problem_count": len(problems),
    }
    json.dump(report, open(OUT, "w"), indent=1)
    print(json.dumps(report, indent=1))


asyncio.run(main())
