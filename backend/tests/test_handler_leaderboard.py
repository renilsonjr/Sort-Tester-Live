"""The Handler leaderboard (#417): one board per mode, per season.

These hold the owner's decisions of 2026-11-26 as much as the feature: who
appears, what a row may say about a person, and that it never touches Ranked.
"""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.handler import leaderboard
from backend.main import create_app
from backend.tests.browser import BROWSER

BOARD = "/api/handler/leaderboard"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class HandlerLeaderboardTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.login_ids = {}
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        self._sql("INSERT INTO seasons (phase, label) VALUES ('pre_season', 'Pre-Season')")

    def _sql(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            migrate.execute(conn, sql, params)
            conn.commit()
        finally:
            conn.close()

    def _one(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, sql, params)
        finally:
            conn.close()

    def _player(self, username, **scores):
        client = TestClient(create_app(), headers=BROWSER)
        registration = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(registration.status_code, 200, registration.text)
        login_id = registration.json()["login_id"]
        self.login_ids[username] = login_id
        self.assertEqual(
            client.post("/api/auth/login", json={"username": username, "login_id": login_id}).status_code,
            200,
        )
        for mode, score in scores.items():
            saved = client.put("/api/handler/best", json={"mode": mode, "score": score})
            self.assertEqual(saved.status_code, 200, saved.text)
        return client

    def _board(self, client, mode):
        answer = client.get(BOARD, params={"mode": mode})
        self.assertEqual(answer.status_code, 200, answer.text)
        return answer.json()

    # -- who appears, and in what order -----------------------------------

    def test_an_empty_board_is_an_answer_not_an_error(self):
        reader = self._player("reader")
        board = self._board(reader, "easy")
        self.assertEqual(board["rows"], [])
        self.assertEqual(board["players"], 0)
        self.assertIsNone(board["you"])
        self.assertEqual(board["season_label"], "Pre-Season")
        self.assertTrue(board["open"])

    def test_highest_first_and_the_reader_s_own_row_is_marked(self):
        self._player("anna", easy=12)
        self._player("bruno", easy=40)
        carla = self._player("carla", easy=25)
        board = self._board(carla, "easy")
        self.assertEqual([(r["place"], r["username"], r["score"]) for r in board["rows"]],
                         [(1, "bruno", 40), (2, "carla", 25), (3, "anna", 12)])
        self.assertEqual([r["you"] for r in board["rows"]], [False, True, False])
        self.assertEqual(board["you"], {"place": 2, "score": 25, "tied": False})
        self.assertEqual(board["players"], 3)

    def test_equal_scores_share_a_place_and_the_next_place_skips(self):
        self._player("anna", hard=30)
        self._player("bruno", hard=30)
        carla = self._player("carla", hard=10)
        rows = self._board(carla, "hard")["rows"]
        self.assertEqual([(r["place"], r["tied"]) for r in rows], [(1, True), (1, True), (3, False)])

    def test_modes_are_never_mixed(self):
        anna = self._player("anna", easy=50, expert=3)
        self._player("bruno", expert=9)
        self.assertEqual([r["username"] for r in self._board(anna, "easy")["rows"]], ["anna"])
        self.assertEqual([r["username"] for r in self._board(anna, "expert")["rows"]], ["bruno", "anna"])
        self.assertEqual(self._board(anna, "medium")["rows"], [])

    def test_a_zero_is_not_on_the_board(self):
        anna = self._player("anna", easy=0)
        board = self._board(anna, "easy")
        self.assertEqual(board["rows"], [])
        self.assertIsNone(board["you"])

    def test_the_reader_s_place_survives_the_row_cap(self):
        from backend.routers import handler as handler_router

        self._player("anna", easy=30)
        self._player("bruno", easy=20)
        carla = self._player("carla", easy=10)
        original = handler_router.BOARD_ROWS_SHOWN
        handler_router.BOARD_ROWS_SHOWN = 2
        self.addCleanup(setattr, handler_router, "BOARD_ROWS_SHOWN", original)
        board = self._board(carla, "easy")
        self.assertEqual(len(board["rows"]), 2)
        self.assertEqual(board["you"]["place"], 3)
        self.assertEqual(board["players"], 3)

    # -- what a row may say about a person --------------------------------

    def test_a_row_carries_only_what_the_screen_shows(self):
        anna = self._player("anna", easy=5)
        row = self._board(anna, "easy")["rows"][0]
        self.assertEqual(set(row), {"place", "username", "tag", "avatar", "score", "tied", "you"})
        text = anna.get(BOARD, params={"mode": "easy"}).text
        account_id = str(self._one("SELECT id FROM accounts WHERE username = 'anna'")["id"])
        self.assertNotIn(account_id, text)
        self.assertNotIn(self.login_ids["anna"], text)

    def test_a_guest_cannot_read_the_board(self):
        self._player("anna", easy=5)
        guest = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(guest.get(BOARD, params={"mode": "easy"}).status_code, 401)

    def test_an_unknown_mode_is_refused(self):
        anna = self._player("anna")
        self.assertEqual(anna.get(BOARD, params={"mode": "overall"}).status_code, 400)
        self.assertEqual(anna.get(BOARD).status_code, 422)

    def test_a_deleted_account_leaves_the_board(self):
        anna = self._player("anna", easy=40)
        bruno = self._player("bruno", easy=10)
        gone = anna.post(
            "/api/auth/account/delete",
            json={"login_id": self.login_ids["anna"], "acknowledge": True},
        )
        self.assertEqual(gone.status_code, 202, gone.text)
        rows = self._board(bruno, "easy")["rows"]
        self.assertEqual([(r["place"], r["username"]) for r in rows], [(1, "bruno")])

    def test_a_deletion_mark_alone_already_hides_the_row(self):
        # The filter is a second lock: even if the rows were still there, a
        # deleted account must not be listed.
        self._player("anna", easy=40)
        bruno = self._player("bruno", easy=10)
        self._sql("UPDATE accounts SET deleted_at = now() WHERE username = 'anna'")
        self.assertEqual([r["username"] for r in self._board(bruno, "easy")["rows"]], ["bruno"])

    # -- the board belongs to a season ------------------------------------

    def test_a_new_season_opens_with_an_empty_board(self):
        anna = self._player("anna", easy=40)
        self._sql("UPDATE seasons SET closed_at = now()")
        self._sql("INSERT INTO seasons (phase, label) VALUES ('official', 'Season 1')")
        board = self._board(anna, "easy")
        self.assertEqual((board["season_label"], board["rows"], board["open"]), ("Season 1", [], True))
        anna.put("/api/handler/best", json={"mode": "easy", "score": 3})
        self.assertEqual(self._board(anna, "easy")["you"], {"place": 1, "score": 3, "tied": False})

    def test_an_ended_season_shows_its_board_as_it_finished(self):
        anna = self._player("anna", easy=40)
        self._sql("UPDATE seasons SET closed_at = now()")
        board = self._board(anna, "easy")
        self.assertFalse(board["open"])
        self.assertEqual([(r["username"], r["score"]) for r in board["rows"]], [("anna", 40)])
        # and a round played now changes nothing on it
        anna.put("/api/handler/best", json={"mode": "easy", "score": 99})
        self.assertEqual(self._board(anna, "easy")["rows"][0]["score"], 40)

    # -- it is not Ranked -------------------------------------------------

    def test_reading_the_board_writes_nothing_and_ranked_is_untouched(self):
        anna = self._player("anna", easy=40)
        before = self._one(
            "SELECT (SELECT count(*) FROM attempts) AS attempts,"
            " (SELECT count(*) FROM balances) AS balances,"
            " (SELECT count(*) FROM handler_best_scores) AS scores"
        )
        ranked_before = anna.get("/api/ranked/leaderboard").json()
        for mode in ("easy", "medium", "hard", "expert"):
            self._board(anna, mode)
        after = self._one(
            "SELECT (SELECT count(*) FROM attempts) AS attempts,"
            " (SELECT count(*) FROM balances) AS balances,"
            " (SELECT count(*) FROM handler_best_scores) AS scores"
        )
        self.assertEqual(before, after)
        self.assertEqual(anna.get("/api/ranked/leaderboard").json(), ranked_before)
        # a Handler score puts nobody on the Ranked board
        self.assertEqual(ranked_before["rows"], [])


class HandlerLeaderboardRulesTestCase(unittest.TestCase):
    """The rules that need no database."""

    def test_places_with_ties(self):
        listing = [
            {"id": 1, "username": "a", "tag": "0001", "score": 9},
            {"id": 2, "username": "b", "tag": "0002", "score": 9},
            {"id": 3, "username": "c", "tag": "0003", "score": 9},
            {"id": 4, "username": "d", "tag": "0004", "score": 2},
        ]
        rows = leaderboard.place_rows(listing)
        self.assertEqual([(row.place, row.tied) for row in rows],
                         [(1, True), (1, True), (1, True), (4, False)])
        self.assertEqual(leaderboard.place_rows([]), [])

    def test_there_is_no_combined_board(self):
        # Rule 16: a two-minute round in Easy is not one in Hard. The read
        # is always for one named mode.
        from pathlib import Path

        source = (Path(__file__).resolve().parents[1] / "handler" / "leaderboard.py").read_text(encoding="utf-8")
        self.assertIn("h.mode = %s", source)
        self.assertNotIn("SUM(", source.upper().replace("SUM(H", "SUM("))
