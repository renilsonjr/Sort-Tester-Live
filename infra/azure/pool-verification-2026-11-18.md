# Request-path pool verification — 2026-11-18

Operational evidence for audit M-5 / Task 14 and
[issue #196](https://github.com/renilsonjr/Sort-Tester-Live/issues/196).
The owner ran Azure commands in Cloud Shell and supplied the outputs;
the assistant did not independently access Azure. Fictional data only.
The issue holds the detailed timeline; this file preserves the conclusions,
measurements and repeatable method in git.

## Result and remaining work

- The deployed request path was observed holding **at most eight other
  same-role client connections**, excluding the observer's own backend PID.
- The external burst returned **260/260 HTTP 200**; its observer collected
  **408 samples** at 100 ms intervals, with a maximum of **8** connections.
- Response times rose with concurrency. The original Task 14 requirement
  that they stay flat is **not satisfied**. On 2026-11-18 the owner explicitly
  separated pool protection acceptance in #196 from mandatory pilot
  performance validation in #13; this revises the original criterion.
- CPU-quota throttling overlapped the test traffic. A temporary capacity
  increase improved measured latency; it was **reverted and verified**.
- No application code, pool size, database schema or permanent allocation
  changed. This is not the 30-player, 15-minute mixed-traffic pilot in #13.

Sampling is not exhaustive connection accounting. Counts cover client
backends in the same database and role, not every PostgreSQL connection.
The pool cap is per application process, not a database-wide maximum.

## Original allocation: 0.25 CPU / 0.5 GiB

Single revision mode, min/max replicas 1. The initial in-container burst
returned 170/170 HTTP 200; 103 samples observed a maximum of eight other
`sort_app` connections. Its generator shared the app's CPU and used
loopback, so its latency was not treated as an external measurement.

The external generator used public HTTPS ingress while the observer
connected from inside the app over its existing private database path:

| Concurrency | Requests / HTTP 200 | p50 ms | p95 ms | Max ms | Requests/s |
| --- | --- | --- | --- | --- | --- |
| 1 | 20 / 20 | 96.6 | 123.4 | 126.3 | 10.2 |
| 10 | 50 / 50 | 192.2 | 308.2 | 346.1 | 47.7 |
| 30 | 90 / 90 | 673.0 | 846.5 | 868.8 | 41.5 |
| 50 | 100 / 100 | 973.4 | 1374.0 | 1516.3 | 42.6 |

An external health/notice/health control at concurrency 30 returned 90/90
HTTP 200 per phase. Health p95 was **557.2 / 237.3 ms**; notice p95 was
**798.4 ms** at **45.0 requests/s**. This directed investigation toward
additional work in the database-backed path, not proof of a slow query.

Direct serial reads from inside the app, 20 samples per phase:

| Measurement | p50 ms | p95 ms | Max ms |
| --- | --- | --- | --- |
| `SELECT 1` | 1.66 | 4.84 | 6.19 |
| Notice helper, transaction left open across iterations | 5.20 | 11.76 | 13.53 |
| Connection check + notice helper + rollback per cycle | 12.67 | 15.73 | 19.90 |

The first diagnostic script failed before the third phase with
`ProgrammingError`: `migrate.execute` explicitly opens a transaction and
uses a savepoint even on an autocommit connection. Changing autocommit
while that transaction remained open failed with INTRANS. The assistant
reproduced this locally and corrected the diagnostic to use a fresh
connection and roll back each cycle. It was not an application failure.
These serial timings exclude HTTP, pool wait and concurrent database load.

## Synchronized CPU experiment

Cgroup v1 reported quota **25,000 us** per **100,000 us** period: 0.25 CPU.
Both visible controller paths had the same counters; they were not summed.
One-minute Azure `UsageNanoCores` aggregates did not show sustained quota
use, but could not exclude short throttling during the bursts.

All measured phases below used 90 requests at concurrency 30, all HTTP 200.
Times are UTC on 2026-11-18. The higher allocation included an explicit
50-request warm-up at concurrency 10, also all HTTP 200.

| Allocation / phase | UTC start–end | p50 ms | p95 ms | Requests/s |
| --- | --- | --- | --- | --- |
| 0.25 CPU, health 1 | 08:29:50.625–51.486 | 200.9 | 530.9 | 104.6 |
| 0.25 CPU, notice | 08:29:53.486–55.761 | 695.1 | 1019.4 | 39.6 |
| 0.25 CPU, health 2 | 08:29:57.761–58.411 | 199.3 | 269.6 | 138.6 |
| 0.5 CPU / 1 GiB, health 1 | 08:41:44.927–45.224 | 87.0 | 109.3 | 302.8 |
| 0.5 CPU / 1 GiB, notice | 08:41:47.225–48.225 | 299.5 | 402.9 | 90.0 |
| 0.5 CPU / 1 GiB, health 2 | 08:41:50.225–50.555 | 94.8 | 119.1 | 272.9 |

The original observation window recorded **313 enforcement periods, 32
throttled periods, 2110.78 ms accumulated throttled time**. Samples ending
08:29:54.038, 54.540, 55.041 and 55.542 UTC showed throttling increments
during notice traffic. The higher-capacity window recorded **196 periods,
20 throttled periods, 877.90 ms throttled time**, including warm-up and
idle time; throttling still overlapped notice traffic.

The windows differ in length and workload, so their accumulated totals
are not directly comparable. Cgroup throttled time is not a per-request
delay to add to HTTP latency. The observer itself shares the container's
quota. See [Linux CFS bandwidth accounting](https://www.kernel.org/doc/html/latest/scheduler/sched-bwc.html).

Notice p95 fell from **1019.4 to 402.9 ms**, approximately **60.5%**, and
throughput rose from **39.6 to 90.0 requests/s**. This supports resource
allocation as a performance contributor, not an isolated CPU-only causal
estimate: memory also doubled, the app/pool restarted, and warm-up differed.
No permanent capacity increase was authorised.

## Return verified

After explicit owner approval, the temporary revision used 0.5 CPU / 1 GiB,
one replica and 100% traffic. The owner then restored 0.25 CPU / 0.5 GiB.
The update's first response still named the old ready revision, so it was
not treated as proof of a completed return.

The subsequent revision query reported **active, Healthy, Provisioned,
RunningAtMaxScale, one replica, traffic weight 100**. A final active-revision
listing showed **only the returned revision**, with CPU **0.25**, memory
**0.5Gi**, replicas **1**, traffic **100**. The experiment revision was no
longer active. Final HTTP smoke:

- `/health`: **200**, `{"status":"ok"}`.
- `/api/ranked/season/notice`: **200**,
  `{"started":false,"label":null,"started_at":null,"closes_at":null}`.

The temporary experiment and its return are complete. On 2026-11-18 the
owner accepted the observed pool protection for #196 and kept performance
validation mandatory in #13. This explicitly replaces the original combined
flat-latency/pool criterion; it does not assert that latency stayed flat.
The proposed pilot workload remains 30 simultaneous players for 15 minutes,
with p95 control/quiz <= 1 s; the target still requires its own owner review
and actual mixed-traffic measurement. No pilot or permanent capacity increase
is approved. Resource-lock configuration acceptance is recorded separately in
[[shared-resource-locks#Acceptance boundary]]; final audit verification
remains open in #196, and restore and other pilot gates remain open in #13.

## Repeat the method

See [[container-apps-app#10. Observe the pool and compare request paths]]
for the two-terminal procedure. The saved helpers are reproducible
versions of the ad hoc scripts used in the session, not a claim that
these exact files were already deployed or rerun against Azure:

- [http-burst.py](diagnostics/http-burst.py): external GET-only generator;
  `pool` profile for concurrency 1/10/30/50, `control` profile for
  health/notice/health at concurrency 30; optional 50-request warm-up.
- [observe-runtime.py](diagnostics/observe-runtime.py): same-role database
  connection sampling or cgroup v1 throttling observation; Ctrl+C ends it
  and prints the summary. Run only one observer at a time for comparisons.
