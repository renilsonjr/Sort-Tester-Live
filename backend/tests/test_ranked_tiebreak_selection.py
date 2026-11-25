"""The owner's prize selection (issue #24, slice 6).

Where every "wait for the owner" lands. The owner decided on 2026-11-15
to see each player's tie-break history, and that the choice is final.
"""
import unittest
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.ranked import tiebreaks
from backend.tests.browser import BROWSER

T0 = datetime(2027, 1, 1, tzinfo=timezone.utc)


class Clock:
    def now(self):
        return T0 + timedelta(days=2)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SelectionTests(unittest.TestCase):
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
        self.owner_client = TestClient(create_app(), headers=BROWSER)
        reg = self.owner_client.post("/api/auth/register", json={"username": "the_owner"})
        self.owner_login = reg.json()["login_id"]
        self.owner_client.post("/api/auth/login", json={"username": "the_owner", "login_id": self.owner_login})
        migrate.execute(
            self.conn, "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'"
        )
        self.owner = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = 'the_owner'"
        )["id"]
        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'Peak Season', %s, %s, %s, %s) RETURNING id",
            (T0 - timedelta(days=60), T0, T0, T0),
        )["id"]
        self.a, self.b, self.c = (self._account(n) for n in ("gull", "hare", "owl"))
        self.group = self._waiting_group([self.a, self.b, self.c], hats=1)
        self.conn.commit()

    # --- helpers ---

    def _account(self, name):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag) VALUES (%s, %s, %s) RETURNING id",
            (name, name, f"{name[:3].upper()}001"),
        )["id"]

    def _waiting_group(self, players, *, hats):
        """A tie the rules already sent to the owner, after one closed round."""
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available,"
            " opened_at, status) VALUES (%s, 'season_close', 700, %s, %s, 'owner_selection')"
            " RETURNING id",
            (self.season, hats, T0),
        )["id"]
        round_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at, status, hats)"
            " VALUES (%s, 5, %s, %s, 'closed', %s) RETURNING id",
            (group, T0, T0 + timedelta(hours=24), hats),
        )["id"]
        for p in players:
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
                (group, p),
            )
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_round_results (round_id, account_id, outcome, score)"
                " VALUES (%s, %s, 'completed', 3)",
                (round_id, p),
            )
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_placements (group_id, account_id, status, decided_in_round)"
                " VALUES (%s, %s, 'owner_selection', 5)",
                (group, p),
            )
        return group

    def _placements(self):
        return {
            r["account_id"]: r["status"]
            for r in migrate.fetch_all(
                self.conn, "SELECT account_id, status FROM tiebreak_placements WHERE group_id = %s",
                (self.group,),
            )
        }

    def _select(self, chosen, owner=None):
        tiebreaks.record_selection(
            self.conn, owner or self.owner, self.group, chosen, clock=Clock()
        )

    # --- the rule ---

    def test_the_owner_sees_the_waiting_tie_with_each_players_history(self):
        cases = tiebreaks.selection_cases(self.conn, self.owner)
        self.assertEqual(len(cases), 1)
        self.assertEqual(cases[0]["hats"], 1)
        history = cases[0]["players"][0]["history"]
        self.assertEqual(
            [(h["round_number"], h["outcome"], h["score"]) for h in history],
            [(5, "completed", 3)],
        )

    def test_the_case_carries_no_points_beyond_the_tied_score(self):
        case = tiebreaks.selection_cases(self.conn, self.owner)[0]
        self.assertEqual(set(case["players"][0]), {"id", "username", "tag", "history"})

    def test_choosing_gives_the_hat_and_the_others_take_none(self):
        self._select([self.b])
        self.assertEqual(
            self._placements(), {self.a: "no_hat", self.b: "hat", self.c: "no_hat"}
        )
        group = migrate.fetch_one(
            self.conn, "SELECT status, selected_by, selected_at FROM tiebreak_groups WHERE id = %s",
            (self.group,),
        )
        self.assertEqual(group["status"], "resolved")
        self.assertEqual(group["selected_by"], self.owner)
        self.assertIsNotNone(group["selected_at"])

    def test_the_choice_is_final(self):
        self._select([self.b])
        with self.assertRaises(tiebreaks.SelectionError) as caught:
            self._select([self.a])
        self.assertIn("final", caught.exception.reason)
        self.assertEqual(self._placements()[self.b], "hat")

    def test_exactly_as_many_as_there_are_hats(self):
        for chosen in ([], [self.a, self.b]):
            with self.subTest(chosen=chosen):
                with self.assertRaises(tiebreaks.SelectionError) as caught:
                    self._select(chosen)
                self.assertIn("exactly 1", caught.exception.reason)

    def test_only_players_waiting_in_this_tie_can_be_chosen(self):
        outsider = self._account("crow")
        self.conn.commit()
        with self.assertRaises(tiebreaks.SelectionError):
            self._select([outsider])

    def test_only_the_owner_may_select(self):
        with self.assertRaises(tiebreaks.SelectionError):
            self._select([self.a], owner=self.a)
        with self.assertRaises(tiebreaks.SelectionError):
            tiebreaks.selection_cases(self.conn, self.a)

    def test_selecting_changes_no_points(self):
        migrate.execute(
            self.conn, "INSERT INTO balances (account_id, current_points) VALUES (%s, 700)", (self.a,)
        )
        self.conn.commit()
        self._select([self.a])
        self.assertEqual(
            migrate.fetch_one(
                self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (self.a,)
            )["current_points"],
            700,
        )

    def test_a_settled_tie_leaves_the_list(self):
        self._select([self.c])
        self.assertEqual(tiebreaks.selection_cases(self.conn, self.owner), [])

    # --- over HTTP ---

    def test_recording_needs_a_fresh_login_id(self):
        """A prize action, so the five-minute reauthentication applies."""
        url = f"/api/ranked/owner/selections/{self.group}"
        refused = self.owner_client.post(url, json={"account_ids": [str(self.a)]})
        self.assertEqual(refused.status_code, 428)
        self.owner_client.post("/api/auth/reauthenticate", json={"login_id": self.owner_login})
        done = self.owner_client.post(url, json={"account_ids": [str(self.a)]})
        self.assertEqual(done.status_code, 200, done.text)
        self.assertEqual(self._placements()[self.a], "hat")

    def test_a_player_cannot_see_or_record_selections(self):
        player = TestClient(create_app(), headers=BROWSER)
        reg = player.post("/api/auth/register", json={"username": "nosy_player"})
        player.post("/api/auth/login", json={"username": "nosy_player", "login_id": reg.json()["login_id"]})
        self.assertEqual(player.get("/api/ranked/owner/selections").status_code, 403)
        self.assertEqual(
            player.post(
                f"/api/ranked/owner/selections/{self.group}", json={"account_ids": []}
            ).status_code,
            403,
        )

    def test_the_listing_over_http_shows_the_history(self):
        body = self.owner_client.get("/api/ranked/owner/selections").json()
        player = body["cases"][0]["players"][0]
        self.assertEqual(player["history"], [{"round": 5, "outcome": "completed", "score": 3}])


if __name__ == "__main__":
    unittest.main()
