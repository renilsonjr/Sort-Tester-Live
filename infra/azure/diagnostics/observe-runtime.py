"""Read-only observations inside the deployed app: pool or cgroup v1 CPU."""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def emit(value):
    print(json.dumps(value), flush=True)


def observe_pool():
    # Imported only in pool mode; CPU observation needs no database access.
    import psycopg
    from backend.db.settings import app_database_url

    count = 0
    peak = None
    with psycopg.connect(
        app_database_url(),
        autocommit=True,
        connect_timeout=10,
        application_name="pool-check-observer",
        options="-c default_transaction_read_only=on -c statement_timeout=5000",
    ) as conn:
        role = conn.execute("SELECT current_user").fetchone()[0]
        emit({"observing_role": role, "utc": datetime.now(timezone.utc).isoformat()})
        try:
            while True:
                current = conn.execute("""
                    SELECT count(*)
                    FROM pg_stat_activity
                    WHERE datname = current_database()
                      AND usename = current_user
                      AND backend_type = 'client backend'
                      AND pid <> pg_backend_pid()
                """).fetchone()[0]
                count += 1
                if peak is None or current > peak:
                    peak = current
                    emit({"peak_other_role_connections": peak})
                time.sleep(0.1)
        except KeyboardInterrupt:
            emit({
                "connection_samples": count,
                "max_other_role_connections": peak,
                "stopped_by_operator": True,
            })


def observe_cpu():
    # The staging environment used this cgroup v1 controller. Fail visibly
    # on a different layout instead of interpreting v2 microseconds as ns.
    root = Path("/sys/fs/cgroup/cpu")

    def read():
        return {
            key: int(value)
            for key, value in (
                line.split() for line in (root / "cpu.stat").read_text().splitlines()
            )
        }

    emit({
        "quota_us": int((root / "cpu.cfs_quota_us").read_text()),
        "period_us": int((root / "cpu.cfs_period_us").read_text()),
        "utc": datetime.now(timezone.utc).isoformat(),
    })
    start = previous = read()
    try:
        while True:
            time.sleep(0.5)
            current = read()
            throttled = current["nr_throttled"] - previous["nr_throttled"]
            if throttled:
                emit({
                    "utc": datetime.now(timezone.utc).isoformat(),
                    "new_throttled_periods": throttled,
                    "throttled_ms": round(
                        (current["throttled_time"] - previous["throttled_time"]) / 1_000_000, 2
                    ),
                })
            previous = current
    except KeyboardInterrupt:
        end = read()
        emit({
            "summary": True,
            "periods": end["nr_periods"] - start["nr_periods"],
            "throttled_periods": end["nr_throttled"] - start["nr_throttled"],
            "throttled_ms": round(
                (end["throttled_time"] - start["throttled_time"]) / 1_000_000, 2
            ),
        })


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("pool", "cpu"))
    args = parser.parse_args()
    # A source paste through `python -` has /app on sys.path already; this
    # also lets a saved /tmp copy import the existing app without an install.
    if Path("/app/backend").is_dir():
        sys.path.insert(0, "/app")
    try:
        if args.mode == "pool":
            observe_pool()
        else:
            observe_cpu()
    except Exception as exc:
        # Connection exceptions can contain infrastructure details. Keep
        # credentials/DSNs out of terminal output and shared evidence.
        emit({"observation_failed": type(exc).__name__})
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
