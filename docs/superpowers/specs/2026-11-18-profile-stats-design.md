# Profile stats — Best Ranked and Place (#218) — design

Design for [issue #218](https://github.com/renilsonjr/Sort-Tester-Live/issues/218):
give the redesigned Profile real numbers for the stats grid that currently
shows `—` placeholders.

## Scope

The redesigned Profile (branch `redesign/ranked-glass`, `fillOverview` in
`src/app.js`) draws a `.pf-stats` grid: **Points** (already real, from
`/ranked/entry`), **Best Ranked**, **Practices**, and **Place** — the last
three are hard-coded `—` (the `DASH` constant) because no backend provides
them.

**This work ships the backend only:** one read-only endpoint plus its
module and tests. It changes no existing endpoint, no schema, and no Azure
resource.

**Base branch — `codex/ranked-mode`.** That is the project's active trunk:
the ranked backend, the #84 managed-identity path and the glass redesign
(merged as #219, the deployed app) all live there, and `main` is a stale
baseline 347 commits behind with no ranked router at all. This work
branches from `codex/ranked-mode` and targets it, not `main`. The
`.pf-stats` grid and its three `DASH` placeholders are already on
`codex/ranked-mode` (via #219); the frontend wiring of that grid in
`fillOverview` is the owner's redesign work and is handed a fixed contract
(below) rather than built here.

### Decisions locked during brainstorming (2026-11-18)

- **Best Ranked = best correct-out-of-15.** The highest count of correct
  answers in a single settled Ranked attempt, 0–15. Not `raw_score`
  (which is a difficulty-weighted point sum, −150…+300, and can be
  negative — unfit for a profile tile).
- **Practices = client-local (`localStorage`).** Practice is entirely
  client-side today (`src/decks.js`, `src/levels.js`); there is no server
  record of a completed practice run and this work does **not** add one.
  The count is a per-account `localStorage` counter maintained by the
  frontend. Out of backend scope; specified only as a contract note.
- **Place = `your_place`.** The same current-leaderboard position the
  official standings already compute.
- **Best Ranked scope:** all of the account's settled Ranked attempts
  (Pre-Season and official), modes `normal` and `promotion`, with a real
  final outcome (`completed`, `quit`, `disconnect`, `season_close`).
  Excludes voids (`launch_reset`, `outage_void`) and tie-breaks (mode
  `tiebreak`, whose scores stay hidden until a round closes).

## What exists already

- `attempts` (migration 0006): `account_id`, `mode IN
  ('normal','promotion','tiebreak')`, `final_outcome IN ('completed',
  'quit','disconnect','season_close','launch_reset','outage_void')`,
  `state`, `settled_at`.
- `attempt_answers` (migration 0006): one row per `(attempt_id, seq)`,
  `seq BETWEEN 1 AND 15`, `outcome IN ('correct','wrong','timeout',
  'unsent')`. The number of correct answers in an attempt is
  `COUNT(*) FILTER (WHERE outcome = 'correct')`.
- `settlements` (migration 0007): one row per settled attempt; used here
  only as the "this attempt is settled" join, mirroring
  `backend/ranked/history.py`.
- `GET /ranked/leaderboard` (`backend/routers/ranked.py`) already computes
  `your_place` via `seasons.official_launch(conn)` →
  `standings.standings(conn, season_id)` → `standings.place_of(rows,
  account_id)`. In Pre-Season `official_launch` is `None`, so there is no
  place (null).
- Auth: `_current_account` dependency; `get_readonly_db` for read-only
  routes (e.g. `season_notice`). The app already maps pool/DB
  unavailability to a clean 503 (audit #84).

## Architecture

Two seams.

### 1. Stats module (`backend/ranked/profile_stats.py`, new)

Pure data access, no HTTP. One function:

```python
def best_ranked_correct(conn, account_id) -> int | None:
    """Highest correct-answer count in one settled Ranked attempt, or None.

    Counts correct answers per attempt among the account's settled attempts
    in modes 'normal'/'promotion' with a real final outcome; excludes voids
    and tie-breaks. Returns None when the account has no such attempt.
    """
```

SQL:

```sql
SELECT MAX(c.correct) AS best
FROM (
    SELECT aa.attempt_id,
           COUNT(*) FILTER (WHERE aa.outcome = 'correct') AS correct
    FROM attempt_answers aa
    JOIN attempts a   ON a.id = aa.attempt_id
    JOIN settlements s ON s.attempt_id = a.id
    WHERE a.account_id = %s
      AND a.mode IN ('normal', 'promotion')
      AND a.final_outcome IN ('completed', 'quit', 'disconnect', 'season_close')
    GROUP BY aa.attempt_id
) c
```

`MAX` over no rows is SQL `NULL`, which the function returns as `None`.

Place reuses the existing functions directly; no new query:

```python
def leaderboard_place(conn, account_id) -> int | None:
    launch = seasons.official_launch(conn)
    if launch is None:
        return None
    return standings.place_of(standings.standings(conn, launch.season_id), account_id)
```

(`leaderboard_place` may live in this module or be read inline in the
router; the plan picks one. It must give the same answer as
`/ranked/leaderboard`'s `your_place` for the same account, computed over
the full, uncapped standings.)

### 2. Endpoint (`GET /ranked/profile/stats`, in `backend/routers/ranked.py`)

```python
@router.get("/profile/stats")
def profile_stats(account: dict = Depends(_current_account), conn=Depends(get_readonly_db)):
    correct = profile_stats_module.best_ranked_correct(conn, account["id"])
    place = profile_stats_module.leaderboard_place(conn, account["id"])
    return {
        "best_ranked": None if correct is None else {"correct": correct, "total": 15},
        "place": place,
    }
```

- **Auth:** requires a signed-in account (`_current_account`), exactly like
  `/ranked/entry`. Private to the caller: it reads only `account["id"]`;
  the request cannot name another account and the owner gets no exception
  (same rule as `/ranked/history`).
- **Read-only:** `get_readonly_db`; opening it starts no attempt and no
  timer.
- `total` is the fixed Ranked quiz length (15). It is a constant in the
  payload so the frontend renders `correct/total` without hard-coding 15.

### Response contract

```json
{ "best_ranked": { "correct": 13, "total": 15 }, "place": 7 }
```

- `best_ranked`: object, or `null` when the account has no settled Ranked
  attempt.
- `place`: integer (1-based), or `null` in Pre-Season or when the account
  is not in the official standings.

## Frontend contract (redesign branch — not built here)

In `fillOverview` (on `codex/ranked-mode`, the owner's redesign work),
after fetching `/ranked/profile/stats`, replace the three `DASH` values:

- **Best Ranked:** `s.best_ranked ? \`${s.best_ranked.correct}/${s.best_ranked.total}\` : DASH`
- **Place:** `s.place != null ? \`#${s.place}\` : DASH`
- **Practices:** a per-account `localStorage` counter, e.g. key
  `stl.practices.<accountId>`, incremented when a practice run completes
  (in the practice-finish path of `src/levels.js`/`src/app.js`); render the
  number, or `DASH` when absent/zero. No backend call.

A failed `/ranked/profile/stats` fetch leaves all three as `DASH` (the
grid already tolerates placeholders); it must not break the Points tile,
which comes from the separate `/ranked/entry` call.

## Testing

Backend only; all against the scratch database, no Azure.

1. **Best Ranked — max across attempts.** Two settled `normal` attempts
   for one account with different correct counts; the endpoint/module
   returns the higher count.
2. **Best Ranked — null when none.** An account with no settled Ranked
   attempt returns `best_ranked = null`.
3. **Best Ranked — excludes voids and tie-breaks.** An attempt with
   `final_outcome='launch_reset'` and a `mode='tiebreak'` attempt (even one
   with many correct answers) do not count; only eligible attempts do.
4. **Best Ranked — includes promotion and partial (quit) attempts.** A
   `promotion` attempt counts; a `quit` attempt with N correct answers
   counts as N.
5. **Place — null in Pre-Season, number when eligible.** With no official
   launch, `place = null`; after an official launch with the account in the
   standings, `place` matches `/ranked/leaderboard`'s `your_place`.
6. **Endpoint — auth and privacy.** Unauthenticated request is rejected
   (401); the response reflects only the caller's own account.

## Out of scope

- Any `localStorage`/practice-counter frontend work and the `fillOverview`
  wiring (owner's redesign branch).
- Server-side tracking of practice sessions (explicitly declined: Practices
  stays client-local).
- Changes to `/ranked/entry`, `/ranked/leaderboard`, `/ranked/history`, or
  any schema/migration.
- Any Azure or deployment change.

## Dependencies

- None new. Reuses `seasons.official_launch`, `standings.standings`,
  `standings.place_of`, `_current_account`, `get_readonly_db`.
- Parent roadmap: #1.
