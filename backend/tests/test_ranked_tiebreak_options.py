"""The four belts a tie-break question offers (issue #24, slice 7).

Owner decision 2026-11-15: four belts, the right one and three others, the
same four for everyone in the round, drawn and stored rather than derived.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.ranked import engine, tiebreaks
from backend.ranked_bank.catalog import load_reviewed_bank
from backend.tests.browser import BROWSER

BANK = load_reviewed_bank()
CAP = "X-Attempt-Capability"


class Clock:
    def __init__(self, m):
        self.m = m

    def now(self):
        return self.m


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OptionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.t0 = datetime(2027, 1, 1, tzinfo=timezone.utc)
        self.clock = Clock(self.t0)
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'S', %s, %s, %s, %s) RETURNING id",
            (self.t0 - timedelta(days=60), self.t0, self.t0, self.t0),
        )["id"]
        self.group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'season_close', 700, 1, %s) RETURNING id",
            (self.season, self.t0),
        )["id"]
        self.rng = random.Random(5)

    def _round(self, players):
        rid = tiebreaks._open_round(
            self.conn, self.group, self.season, 1, players, 1,
            opened_at=self.t0, deadline_at=self.t0 + timedelta(hours=24), bank=BANK, rng=self.rng,
        )
        self.conn.commit()
        return rid

    def _player(self, name):
        client = TestClient(create_app(), headers=BROWSER)
        reg = client.post("/api/auth/register", json={"username": name})
        self.assertEqual(reg.status_code, 200, reg.text)
        client.post("/api/auth/login", json={"login_id": reg.json()["login_id"]})
        cid = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = %s", (name,)
        )["id"]
        return client, cid

    def test_each_question_stores_four_options_including_the_right_belt(self):
        a, aid = self._player("gull")
        rid = self._round([aid])
        rows = migrate.fetch_all(
            self.conn,
            "SELECT q.options, qv.bank_key FROM tiebreak_round_questions q"
            " JOIN question_versions qv ON qv.id = q.question_version_id"
            " WHERE q.round_id = %s ORDER BY q.seq",
            (rid,),
        )
        self.assertEqual(len(rows), 5)
        for row in rows:
            self.assertEqual(len(row["options"]), 4)
            self.assertEqual(len(set(row["options"])), 4)
            correct = next(q.correct_belt for q in BANK.questions if q.canonical_id == row["bank_key"])
            self.assertIn(correct, row["options"])

    def test_everyone_in_the_round_sees_the_same_four(self):
        a, aid = self._player("gull")
        b, bid = self._player("hare")
        rid = self._round([aid, bid])
        starts = []
        for client in (a, b):
            r = client.post(f"/api/ranked/tiebreak/rounds/{rid}/attempts")
            client.headers[CAP] = r.json()["capability"]
            starts.append((client, r.json()["attempt_id"]))
        opts = []
        for client, attempt in starts:
            q = client.get(f"/api/ranked/attempts/{attempt}/current").json()
            opts.append(q["options"])
        self.assertEqual(opts[0], opts[1])
        self.assertEqual(len(opts[0]), 4)

    def test_the_question_carries_where_it_goes_but_not_the_answer(self):
        a, aid = self._player("gull")
        rid = self._round([aid])
        r = a.post(f"/api/ranked/tiebreak/rounds/{rid}/attempts")
        a.headers[CAP] = r.json()["capability"]
        q = a.get(f"/api/ranked/attempts/{r.json()['attempt_id']}/current").json()
        self.assertIn("service", q)
        self.assertIn("routing_code", q)
        self.assertIn("options", q)
        self.assertNotIn("correct", q)
        self.assertNotIn("correct_belt", q)


if __name__ == "__main__":
    unittest.main()
