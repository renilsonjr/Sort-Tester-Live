"""Bounded GET-only staging diagnostics; no account or quiz traffic."""

import argparse
import json
import math
import os
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import urlopen


def utc():
    return datetime.now(timezone.utc).isoformat()


def request(base, path):
    started = time.perf_counter()
    try:
        with urlopen(base + path, timeout=15) as response:
            data = json.loads(response.read())
            valid = isinstance(data, dict) and (
                data == {"status": "ok"} if path == "/health"
                else isinstance(data.get("started"), bool)
            )
            status = str(response.status) if valid else "UnexpectedBody"
    except HTTPError as exc:
        status = str(exc.code)
        exc.close()
    except Exception as exc:
        status = type(exc).__name__
    return status, (time.perf_counter() - started) * 1000


def run(base, path, concurrency, total):
    started = time.perf_counter()
    cpu_started = time.process_time()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        results = list(executor.map(lambda _: request(base, path), range(total)))
    elapsed = time.perf_counter() - started
    times = sorted(ms for _, ms in results)
    return {
        "path": path,
        "concurrency": concurrency,
        "requests": total,
        "statuses": dict(Counter(status for status, _ in results)),
        "p50_ms": round(times[math.ceil(total * 0.50) - 1], 1),
        "p95_ms": round(times[math.ceil(total * 0.95) - 1], 1),
        "max_ms": round(times[-1], 1),
        "requests_per_second": round(total / elapsed, 1),
        "generator_cpu_seconds": round(time.process_time() - cpu_started, 2),
        "elapsed_seconds": round(elapsed, 2),
        "finished_utc": utc(),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.environ.get("SORT_TESTER_URL", ""))
    parser.add_argument("--profile", choices=("pool", "control"), default="control")
    parser.add_argument("--warmup", type=int, choices=(0, 50), default=0)
    args = parser.parse_args()
    base = args.url.rstrip("/")
    try:
        parsed = urlsplit(base)
        parsed.port
        valid = (
            parsed.scheme in ("http", "https")
            and parsed.hostname
            and not parsed.username
            and not parsed.password
            and not parsed.path
            and not parsed.query
            and not parsed.fragment
            and (parsed.scheme == "https" or parsed.hostname in ("localhost", "127.0.0.1", "::1"))
        )
    except ValueError:
        valid = False
    if not valid:
        parser.error("Set SORT_TESTER_URL or --url to an HTTPS origin; HTTP is allowed only on loopback.")

    if args.warmup:
        print(json.dumps({"warmup_started_utc": utc()}), flush=True)
        warmup = run(base, "/api/ranked/season/notice", 10, args.warmup)
        print(json.dumps({"warmup": warmup}), flush=True)
        if warmup["statuses"] != {"200": args.warmup}:
            return 1
        time.sleep(3)

    notice = "/api/ranked/season/notice"
    phases = (
        [(notice, 1, 20), (notice, 10, 50), (notice, 30, 90), (notice, 50, 100)]
        if args.profile == "pool"
        else [("/health", 30, 90), (notice, 30, 90), ("/health", 30, 90)]
    )
    for number, (path, concurrency, total) in enumerate(phases, 1):
        print(json.dumps({"starting_round": number, "path": path, "utc": utc()}), flush=True)
        result = run(base, path, concurrency, total)
        print(json.dumps({"round": number, **result}), flush=True)
        if result["statuses"] != {"200": total}:
            return 1
        time.sleep(2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
