# Profile stats — Best Ranked and Place (#218) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose a read-only `GET /ranked/profile/stats` endpoint that gives the Profile its real **Best Ranked** (best correct-out-of-15) and **Place** values, replacing two of the three `—` placeholders in the redesigned stats grid.

**Architecture:** One new pure-data module (`backend/ranked/profile_stats.py`) with two functions — a SQL aggregate for best correct-answer count and a thin reuse of the existing leaderboard standings for place — plus one new route in `backend/routers/ranked.py` that reads the signed-in account and returns both. No schema, no changes to existing endpoints, no Azure.

**Tech Stack:** Python, FastAPI, psycopg (via `backend.db.migrate`), unittest against a scratch PostgreSQL database.

## Global Constraints

- **Base and target branch: `codex/ranked-mode`** (the active trunk and deployed app). Not `main`, which is a stale baseline with no ranked router. Spec: `docs/superpowers/specs/2026-11-18-profile-stats-design.md`.
- **Backend only.** No frontend/`src` changes; the `fillOverview`/`pf-stats` wiring and the `localStorage` Practices counter are the owner's redesign work, handed a fixed contract in the spec.
- **No schema or migration.** Reuse existing tables (`attempts`, `attempt_answers`, `settlements`) and existing functions (`seasons.official_launch`, `standings.standings`, `standings.place_of`).
- **No change to any existing endpoint** (`/ranked/entry`, `/ranked/leaderboard`, `/ranked/history`).
- **Read-only, private to the caller.** Requires `_current_account`; uses `get_readonly_db`; reads only `account["id"]`, with no owner exception.
- **Best Ranked scope:** settled attempts, `mode IN ('normal','promotion')`, `final_outcome IN ('completed','quit','disconnect','season_close')`; excludes voids (`launch_reset`, `outage_void`) and tie-breaks. `total` is the fixed quiz length `15`.
- **Response contract:** `{ "best_ranked": {"correct": <0–15>, "total": 15} | null, "place": <int> | null }`.
- Run the backend suite with `python -m backend.ci_tests` (or the targeted test module) against the scratch database; these DB tests skip when `SORT_TESTER_TEST_DATABASE_URL` is unset.

---

## File Structure

- **Create** `backend/ranked/profile_stats.py` — the two data functions. One responsibility: read a single account's profile stats. No HTTP, no clock.
- **Create** `backend/tests/test_profile_stats.py` — unit tests for both functions against hand-inserted rows.
- **Modify** `backend/routers/ranked.py` — add the import and the `GET /profile/stats` route (placed near `/entry`, after the existing imports block).
- **Create** `backend/tests/test_ranked_profile_stats_router.py` — endpoint tests (auth required, shape, privacy), mirroring `test_ranked_leaderboard_router.py`.

---

### Task 1: Profile-stats data module

**Files:**
- Create: `backend/ranked/profile_stats.py`
- Test: `backend/tests/test_profile_stats.py`

**Interfaces:**
- Consumes: `backend.db.migrate` (`fetch_one`, `execute`), `backend.ranked.seasons.official_launch`, `backend.ranked.standings.standings` + `standings.place_of`.
- Produces:
  - `best_ranked_correct(conn, account_id) -> int | None`
  - `leaderboard_place(conn, account_id) -> int | None`

- [ ] **Step 1: Write the failing test file**

Create `backend/tests/test_profile_stats.py`. Reuse the scratch-DB setup pattern from `backend/tests/test_ranked_leaderboard_router.py` (same `setUpClass`/`setUp`: `recreate_scratch_database`, `upgrade_to_head`, `migrate.connect`). Add a local helper that inserts a settled attempt with a chosen correct-answer count, then the tests.

```python
import unittest

from backend.db import migrate, settings
from backend.ranked import profile_stats


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class BestRankedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(self.conninfo)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self._n = 0

    def _account(self, username="player"):
        self._n += 1
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES"
            " (%s, %s, %s) RETURNING id",
            (f"{username}{self._n}", f"{username}{self._n}".lower(), f"T{self._n:05d}"),
        )["id"]

    def _season(self, phase="pre_season"):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES"
            " (%s, 'S', now()) RETURNING id",
            (phase,),
        )["id"]

    def _settled_attempt(self, account_id, season_id, *, correct, mode="normal",
                         final_outcome="completed", settle=True):
        """Insert a finalized attempt with `correct` correct answers (rest wrong)."""
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, season_id) VALUES (%s, %s)"
            " RETURNING id",
            (account_id, season_id),
        )["id"]  # confirm `assignments` columns during Step 3; adjust if the
                 # minimal insert needs more NOT NULL fields.
        attempt_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at) VALUES"
            " (%s, %s, %s, %s, 'finalized', %s, now()) RETURNING id",
            (account_id, assignment_id, mode, season_id, final_outcome),
        )["id"]
        for seq in range(1, 16):
            outcome = "correct" if seq <= correct else "wrong"
            migrate.execute(
                self.conn,
                "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
                " first_sent_at, deadline_at, answer, outcome, accepted_at) VALUES"
                " (%s, %s, %s, now(), now() + interval '30 s', %s, %s, now())",
                (attempt_id, seq, self._question_version(), outcome, outcome),
            )
        if settle:
            migrate.execute(
                self.conn,
                "INSERT INTO settlements (attempt_id, account_id, season_id,"
                " raw_score, adjustment, phase) VALUES (%s, %s, %s, 0, 0, %s)",
                (attempt_id, account_id, season_id,
                 "pre_season" if mode != "tiebreak" else "pre_season"),
            )  # confirm settlements columns during Step 3; match history.py's joins.
        self.conn.commit()
        return attempt_id

    def test_returns_best_correct_count_across_attempts(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=8)
        self._settled_attempt(acc, season, correct=13)
        result = profile_stats.best_ranked_correct(self.conn, acc)
        self.assertEqual(result, 13)
```

> **Note for the implementer:** the exact minimal `INSERT`s for `assignments`, `attempts` and `settlements` must match the live schema on `codex/ranked-mode`. Before writing the implementation, run `\d assignments`, `\d attempts`, `\d settlements` (or read migrations 0006/0007 and any later ones) against the scratch DB and fill every NOT-NULL column. `backend/tests/ranked_helpers.py` and `test_ranked_standings.py` show the project's own way of building settled attempts — prefer a helper there if one already creates a settled attempt with answers, rather than hand-rolling these inserts.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python -m unittest backend.tests.test_profile_stats -v`
Expected: FAIL with `ModuleNotFoundError: backend.ranked.profile_stats` (module not yet created).

- [ ] **Step 3: Confirm the minimal insert columns**

Inspect the live schema so the test fixtures insert valid rows:

Run: `python -c "from backend.db import migrate, settings; c=migrate.connect(settings.test_database_url()); print([r['column_name'] for r in migrate.fetch_all(c, \"SELECT column_name FROM information_schema.columns WHERE table_name='assignments' AND is_nullable='NO'\")])"`
Repeat for `attempts` and `settlements`. Adjust the Step 1 helper inserts to satisfy every NOT-NULL column (or switch to an existing helper in `ranked_helpers.py`). Re-run Step 2 and keep it failing only on the missing module, not on SQL errors.

- [ ] **Step 4: Write the module with `best_ranked_correct`**

Create `backend/ranked/profile_stats.py`:

```python
"""Account-private profile stats (issue #218).

Read-only reads for the Profile stats grid: the best correct-answer count
in one settled Ranked attempt, and the account's current leaderboard place.
Pure data access — no HTTP, no clock. One account id in, never another.
"""
from backend.db import migrate
from backend.ranked import seasons
from backend.ranked import standings as ranked_standings

# A Ranked quiz is fifteen questions; the profile tile shows correct/15.
RANKED_QUIZ_LENGTH = 15

# Settled, score-bearing attempts only: ordinary and promotion quizzes that
# reached a real outcome. Voids (launch_reset, outage_void) and tie-breaks
# (mode 'tiebreak', hidden until a round closes) never count.
_BEST_RANKED_SQL = """
    SELECT MAX(c.correct) AS best
    FROM (
        SELECT aa.attempt_id,
               COUNT(*) FILTER (WHERE aa.outcome = 'correct') AS correct
        FROM attempt_answers aa
        JOIN attempts a    ON a.id = aa.attempt_id
        JOIN settlements s  ON s.attempt_id = a.id
        WHERE a.account_id = %s
          AND a.mode IN ('normal', 'promotion')
          AND a.final_outcome IN ('completed', 'quit', 'disconnect', 'season_close')
        GROUP BY aa.attempt_id
    ) c
"""


def best_ranked_correct(conn, account_id) -> int | None:
    """Highest correct-answer count in one settled Ranked attempt, or None.

    None when the account has no settled Ranked attempt. The denominator is
    always RANKED_QUIZ_LENGTH; the caller pairs this count with it.
    """
    row = migrate.fetch_one(conn, _BEST_RANKED_SQL, (account_id,))
    return None if row is None or row["best"] is None else int(row["best"])
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m unittest backend.tests.test_profile_stats -v`
Expected: PASS for `test_returns_best_correct_count_across_attempts`.

- [ ] **Step 6: Add the remaining `best_ranked_correct` tests**

Append these tests to `backend/tests/test_profile_stats.py`, then run and make them pass (the implementation from Step 4 should already satisfy them — if one fails, fix the SQL, not the test):

```python
    def test_none_when_no_settled_attempt(self):
        acc = self._account()
        self.assertIsNone(profile_stats.best_ranked_correct(self.conn, acc))

    def test_excludes_voids_and_tiebreaks(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=15, final_outcome="launch_reset")
        self._settled_attempt(acc, season, correct=14, mode="tiebreak")
        self.assertIsNone(profile_stats.best_ranked_correct(self.conn, acc))

    def test_includes_promotion_and_quit(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=15, mode="promotion")
        self._settled_attempt(acc, season, correct=6, final_outcome="quit")
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, acc), 15)

    def test_private_to_the_account(self):
        mine = self._account("mine")
        other = self._account("other")
        season = self._season()
        self._settled_attempt(other, season, correct=15)
        self._settled_attempt(mine, season, correct=9)
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, mine), 9)
```

> If `mode='tiebreak'` requires `tiebreak_round` and/or a different `final_outcome` set (see migration 0006/0031), set those in the helper so the insert is valid; the test's point is only that a tie-break attempt does not count toward Best Ranked.

Run: `python -m unittest backend.tests.test_profile_stats -v`
Expected: all BestRanked tests PASS.

- [ ] **Step 7: Write the failing test for `leaderboard_place`**

Add a second test class to `backend/tests/test_profile_stats.py`. It needs an official season with standings; reuse the eligibility/points pattern from `test_ranked_leaderboard_router.py` (`participant_links` + a settlement/balance that gives the account points) so `standings.standings` returns the account. Keep it minimal:

```python
class LeaderboardPlaceTests(unittest.TestCase):
    # same setUpClass / setUp as above (factor a shared base class or repeat)

    def test_none_before_official_launch(self):
        acc = self._account()
        self.assertIsNone(profile_stats.leaderboard_place(self.conn, acc))

    def test_matches_standings_place_after_launch(self):
        # Build an official, launched season with two eligible accounts at
        # different points; assert leaderboard_place equals standings.place_of
        # for each. Mirror the helpers in test_ranked_leaderboard_router.py.
        ...
```

Run: `python -m unittest backend.tests.test_profile_stats -v`
Expected: FAIL (`leaderboard_place` not defined).

> **Implementer:** read `test_ranked_leaderboard_router.py`'s `_official_season`, `_make_eligible` and launch helpers and copy the minimal sequence that makes `standings.standings` non-empty (official season + launch fact + participant link + points). Do not invent columns.

- [ ] **Step 8: Implement `leaderboard_place`**

Append to `backend/ranked/profile_stats.py`:

```python
def leaderboard_place(conn, account_id) -> int | None:
    """The account's current official-standings place, or None.

    None in Pre-Season (no official launch) or when the account is not in
    the standings. Identical to /ranked/leaderboard's your_place: computed
    over the full, uncapped standings.
    """
    launch = seasons.official_launch(conn)
    if launch is None:
        return None
    rows = ranked_standings.standings(conn, launch.season_id)
    return ranked_standings.place_of(rows, account_id)
```

- [ ] **Step 9: Run the test to verify it passes**

Run: `python -m unittest backend.tests.test_profile_stats -v`
Expected: all tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/ranked/profile_stats.py backend/tests/test_profile_stats.py
git commit -m "feat(ranked): profile-stats data module — best correct count and place (#218)"
```

---

### Task 2: `GET /ranked/profile/stats` endpoint

**Files:**
- Modify: `backend/routers/ranked.py` (import near line 21–24; route near the `/entry` route ~line 203)
- Test: `backend/tests/test_ranked_profile_stats_router.py`

**Interfaces:**
- Consumes: `profile_stats.best_ranked_correct`, `profile_stats.leaderboard_place` (Task 1); existing `_current_account`, `get_readonly_db`.
- Produces: `GET /api/ranked/profile/stats` → `{ "best_ranked": {"correct", "total"} | null, "place": int | null }`.

- [ ] **Step 1: Write the failing router test**

Create `backend/tests/test_ranked_profile_stats_router.py`, mirroring `test_ranked_leaderboard_router.py` (same skip guard, `setUp`, `_sign_in`, `BROWSER` headers, `TestClient(create_app())`).

```python
    def test_requires_a_session(self):
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 401, response.text)

    def test_null_stats_for_new_player(self):
        self._sign_in(self.client, "fresh")
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertIsNone(body["best_ranked"])
        self.assertIsNone(body["place"])

    def test_best_ranked_shape_after_a_settled_attempt(self):
        # sign in, insert one settled normal attempt with 11 correct for this
        # account (reuse the Task 1 helper or ranked_helpers), then:
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["best_ranked"], {"correct": 11, "total": 15})
```

Run: `python -m unittest backend.tests.test_ranked_profile_stats_router -v`
Expected: FAIL (route 404, so `test_requires_a_session` gets 404 not 401, and the others 404).

- [ ] **Step 2: Add the import**

In `backend/routers/ranked.py`, extend the ranked imports (near lines 22–24):

```python
from backend.ranked import profile_stats as ranked_profile_stats
```

- [ ] **Step 3: Add the route**

Place it just after the `/entry` route (~line 212), so related read-only profile reads sit together:

```python
@router.get("/profile/stats")
def profile_stats(account: dict = Depends(_current_account), conn=Depends(get_readonly_db)):
    """The signed-in account's Profile stats: best Ranked correct-count and
    current leaderboard place. Read-only and private to the account; opening
    it starts no attempt and reveals nothing about anyone else."""
    correct = ranked_profile_stats.best_ranked_correct(conn, account["id"])
    place = ranked_profile_stats.leaderboard_place(conn, account["id"])
    return {
        "best_ranked": None if correct is None
        else {"correct": correct, "total": ranked_profile_stats.RANKED_QUIZ_LENGTH},
        "place": place,
    }
```

> The route function is named `profile_stats`; the module is imported as `ranked_profile_stats` to avoid a name clash. Keep both names as written.

- [ ] **Step 4: Run the router test to verify it passes**

Run: `python -m unittest backend.tests.test_ranked_profile_stats_router -v`
Expected: all PASS.

- [ ] **Step 5: Run the whole backend suite**

Run: `python -m backend.ci_tests`
Expected: the full suite is green (no regressions; new tests included). If the DB tests skip, ensure `SORT_TESTER_TEST_DATABASE_URL` is set to the scratch DB first.

- [ ] **Step 6: Commit**

```bash
git add backend/routers/ranked.py backend/tests/test_ranked_profile_stats_router.py
git commit -m "feat(ranked): GET /ranked/profile/stats endpoint (#218)"
```

---

## Finishing

After both tasks are green:
- **REQUIRED SUB-SKILL:** Use superpowers:finishing-a-development-branch.
- Verify the full suite (`python -m backend.ci_tests`) on the merged result, confirm the base branch is **`codex/ranked-mode`**, then present the integration options. The frontend wiring and the Practices `localStorage` counter are intentionally not in this branch; the spec's frontend contract is the hand-off.

## Self-Review

- **Spec coverage:** Best Ranked (Task 1 `best_ranked_correct` + Task 2 shape) ✓; Place (Task 1 `leaderboard_place` + Task 2) ✓; endpoint auth/privacy/read-only (Task 2 Steps 1,3) ✓; null states (Task 1 Steps 6, Task 2 Step 1) ✓; exclude void/tiebreak, include promotion/quit (Task 1 Step 6) ✓; no schema/endpoint changes (constraints) ✓. Practices/frontend intentionally out of scope ✓.
- **Placeholder scan:** the only deliberately-deferred specifics are the exact minimal column lists for `assignments`/`attempts`/`settlements` inserts and the official-launch/standings helper sequence — both are flagged as "confirm against the live schema / copy from the named existing test" steps (Task 1 Step 3, Step 7), not silent TODOs, because hand-copying every NOT-NULL column here risks drifting from the real schema on `codex/ranked-mode`.
- **Type consistency:** `best_ranked_correct -> int | None` and `leaderboard_place -> int | None` are used identically in Task 2; `RANKED_QUIZ_LENGTH` (15) is defined in the module and referenced in the route; route name `profile_stats` vs import alias `ranked_profile_stats` noted to avoid clash.
