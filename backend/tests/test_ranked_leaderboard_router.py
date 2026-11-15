"""The leaderboard over HTTP (issue #12, slice 2).

The rule itself is tested in test_ranked_standings.py. What matters here is
what the endpoint lets out: it needs a session, it says whether the caller
has a position, and it carries nothing private about anybody.
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
class LeaderboardRouterTests(unittest.TestCase):
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
        self.client = TestClient(create_app(), headers=BROWSER)
        self._accounts = 0

    # --- helpers ---

    def _official_season(self):
        season_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES"
            " ('official', 'Peak Season', now()) RETURNING id",
        )["id"]
        self.conn.commit()
        return season_id

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login = client.post(
            "/api/auth/login", json={"login_id": reg.json()["login_id"]}
        )
        self.assertEqual(login.status_code, 200, login.text)
        return migrate.fetch_one(
            self.conn,
            "SELECT id FROM accounts WHERE username_lower = %s",
            (username.lower(),),
        )["id"]

    def _make_eligible(self, account_id, season_id, points):
        self._accounts += 1
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference)"
            " VALUES (%s, %s)",
            (account_id, f"twilight-{self._accounts}"),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET current_points = EXCLUDED.current_points",
            (account_id, points),
        )
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, season_id),
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', now())",
            (account_id, assignment_id, season_id),
        )
        self.conn.commit()

    def _other_player(self, username, season_id, points):
        other = TestClient(create_app(), headers=BROWSER)
        account_id = self._sign_in(other, username)
        self._make_eligible(account_id, season_id, points)
        return account_id

    # --- tests ---

    def test_a_signed_out_visitor_gets_nothing(self):
        """Login is required to view the leaderboard (settled Q5)."""
        self._official_season()
        self.assertEqual(self.client.get("/api/ranked/leaderboard").status_code, 401)

    def test_a_signed_in_player_sees_the_standings(self):
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 1420)
        self._other_player("belt_runner", season_id, 910)

        body = self.client.get("/api/ranked/leaderboard").json()
        self.assertEqual(
            [(row["place"], row["username"], row["points"]) for row in body["rows"]],
            [(1, "dock_owl", 1420), (2, "belt_runner", 910)],
        )
        self.assertEqual(body["your_place"], 1)
        self.assertTrue(body["eligible"])
        self.assertEqual(body["season_label"], "Peak Season")

    def test_your_own_row_is_marked(self):
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 500)
        self._other_player("belt_runner", season_id, 900)
        rows = self.client.get("/api/ranked/leaderboard").json()["rows"]
        self.assertEqual([row["you"] for row in rows], [False, True])

    def test_an_ineligible_player_sees_the_board_without_a_position(self):
        """They may play and keep their points; they have no position."""
        season_id = self._official_season()
        self._sign_in(self.client, "guest_sorter")
        self._other_player("dock_owl", season_id, 1420)

        body = self.client.get("/api/ranked/leaderboard").json()
        self.assertIsNone(body["your_place"])
        self.assertFalse(body["eligible"])
        self.assertEqual(len(body["rows"]), 1)
        self.assertFalse(body["rows"][0]["you"])

    def test_before_the_official_launch_the_board_is_empty(self):
        """Pre-Season ranks nobody, and no season is invented."""
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'Pre-Season')",
        )
        self.conn.commit()
        self._sign_in(self.client, "dock_owl")
        body = self.client.get("/api/ranked/leaderboard").json()
        self.assertEqual(body["rows"], [])
        self.assertIsNone(body["season_label"])
        self.assertFalse(body["points_final"])

    def test_a_tied_pair_shares_a_place_over_http(self):
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 900)
        self._other_player("belt_runner", season_id, 900)
        self._other_player("tape_gull", season_id, 800)

        rows = self.client.get("/api/ranked/leaderboard").json()["rows"]
        self.assertEqual([row["place"] for row in rows], [1, 1, 3])
        self.assertEqual([row["tied"] for row in rows], [True, True, False])

    def test_a_row_carries_no_private_field(self):
        """No account id, no ticket, no flag, no timestamp of any kind."""
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 900)
        row = self.client.get("/api/ranked/leaderboard").json()["rows"][0]
        self.assertEqual(
            set(row), {"place", "username", "tag", "points", "badge", "tied", "you"}
        )

    def test_the_board_says_nothing_about_a_deleted_player(self):
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 900)
        gone = self._other_player("belt_runner", season_id, 5000)
        migrate.execute(
            self.conn, "UPDATE accounts SET deleted_at = now() WHERE id = %s", (gone,)
        )
        self.conn.commit()
        body = self.client.get("/api/ranked/leaderboard").json()
        self.assertEqual([row["username"] for row in body["rows"]], ["dock_owl"])
        self.assertEqual(body["your_place"], 1)

    def test_reading_the_board_starts_nothing(self):
        season_id = self._official_season()
        me = self._sign_in(self.client, "dock_owl")
        self._make_eligible(me, season_id, 900)
        before = migrate.fetch_one(self.conn, "SELECT count(*) AS n FROM attempts")["n"]
        self.client.get("/api/ranked/leaderboard")
        self.conn.commit()
        after = migrate.fetch_one(self.conn, "SELECT count(*) AS n FROM attempts")["n"]
        self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
