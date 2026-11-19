"""Profile stats over HTTP (#218).

The data rules are tested in test_profile_stats.py. What matters here is
what the endpoint lets out: it needs a session, it carries the account's
own Best Ranked and Place in the agreed shape, and nothing about anyone
else.
"""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ProfileStatsRouterTests(unittest.TestCase):
    _digest_counter = iter(f"{index:064x}" for index in range(1, 100000))

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
        self.client = TestClient(create_app(), headers=BROWSER)

    # --- helpers ---

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login = client.post("/api/auth/login", json={"login_id": reg.json()["login_id"]})
        self.assertEqual(login.status_code, 200, login.text)
        return migrate.fetch_one(
            self.conn,
            "SELECT id FROM accounts WHERE username_lower = %s",
            (username.lower(),),
        )["id"]

    def _season(self, phase="pre_season"):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES (%s, %s, now())"
            " RETURNING id",
            (phase, phase),
        )["id"]

    def _question_version(self):
        digest = next(self._digest_counter)
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
            " VALUES ('sort.basic', 'easy', %s) RETURNING id",
            (digest,),
        )["id"]

    def _settled_attempt(self, account_id, season_id, *, correct):
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, season_id),
        )["id"]
        attempt_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', now())"
            " RETURNING id",
            (account_id, assignment_id, season_id),
        )["id"]
        for seq in range(1, 16):
            outcome = "correct" if seq <= correct else "wrong"
            migrate.execute(
                self.conn,
                "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
                " first_sent_at, deadline_at, outcome)"
                " VALUES (%s, %s, %s, '2026-01-01T00:00:00Z',"
                " '2026-01-01T00:00:10Z', %s)",
                (attempt_id, seq, self._question_version(), outcome),
            )
        self.conn.commit()

    # --- tests ---

    def test_requires_a_session(self):
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 401, response.text)

    def test_null_stats_for_a_new_player(self):
        self._sign_in(self.client, "fresh")
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json(), {"best_ranked": None, "place": None})

    def test_best_ranked_shape_after_a_settled_attempt(self):
        account_id = self._sign_in(self.client, "sorter")
        self._settled_attempt(account_id, self._season(), correct=11)
        response = self.client.get("/api/ranked/profile/stats")
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["best_ranked"], {"correct": 11, "total": 15})
        self.assertIsNone(body["place"])

    def test_carries_only_the_callers_own_best(self):
        season = self._season()
        other = self._sign_in(TestClient(create_app(), headers=BROWSER), "other")
        self._settled_attempt(other, season, correct=15)
        mine = self._sign_in(self.client, "mine")
        self._settled_attempt(mine, season, correct=7)
        body = self.client.get("/api/ranked/profile/stats").json()
        self.assertEqual(body["best_ranked"], {"correct": 7, "total": 15})


if __name__ == "__main__":
    unittest.main()
