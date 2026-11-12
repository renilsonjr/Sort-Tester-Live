"""Thin HTTP layer over the ranked engine (issue #8, piece 4)."""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RankedRouterTests(unittest.TestCase):
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
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'test-season')"
        )
        conn.commit()
        conn.close()
        self.client = TestClient(create_app())

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login_id = reg.json()["login_id"]
        res = client.post("/api/auth/login", json={"login_id": login_id})
        self.assertEqual(res.status_code, 200, res.text)

    def test_full_attempt_round_trip_over_http(self):
        self._sign_in(self.client, "player_one")
        start = self.client.post("/api/ranked/attempts")
        self.assertEqual(start.status_code, 201, start.text)
        attempt_id = start.json()["attempt_id"]

        for seq in range(1, 16):
            current = self.client.get(f"/api/ranked/attempts/{attempt_id}/current")
            self.assertEqual(current.status_code, 200, current.text)
            self.assertEqual(current.json()["seq"], seq)
            self.assertIn("deadline_at", current.json())
            answer = self.client.post(
                f"/api/ranked/attempts/{attempt_id}/answer",
                json={"seq": seq, "choice": "YELLOW"},
            )
            self.assertEqual(answer.status_code, 200, answer.text)
            self.assertIn("correct", answer.json())
            advance = self.client.post(f"/api/ranked/attempts/{attempt_id}/advance")
            self.assertEqual(advance.status_code, 200, advance.text)
            if seq < 15:
                self.assertFalse(advance.json()["finished"])
                self.assertEqual(advance.json()["next_seq"], seq + 1)
            else:
                self.assertTrue(advance.json()["finished"])

        # no live question remains
        done = self.client.get(f"/api/ranked/attempts/{attempt_id}/current")
        self.assertEqual(done.status_code, 204)

    def test_requires_authentication(self):
        anon = TestClient(create_app())
        self.assertEqual(anon.post("/api/ranked/attempts").status_code, 401)

    def test_cannot_touch_another_accounts_attempt(self):
        self._sign_in(self.client, "owner_player")
        attempt_id = self.client.post("/api/ranked/attempts").json()["attempt_id"]
        other = TestClient(create_app())
        self._sign_in(other, "other_player")
        res = other.get(f"/api/ranked/attempts/{attempt_id}/current")
        self.assertEqual(res.status_code, 404)

    def test_second_active_attempt_conflicts(self):
        self._sign_in(self.client, "busy_player")
        self.assertEqual(self.client.post("/api/ranked/attempts").status_code, 201)
        self.assertEqual(self.client.post("/api/ranked/attempts").status_code, 409)


if __name__ == "__main__":
    unittest.main()
