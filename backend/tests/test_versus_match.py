"""The Versus duel: shared draw, two scoreboards, one lazy clock.

These tests play whole duels through the HTTP routes, the way two phones
would, and reach into the database only to move clocks and to learn a
question's right answer. The boundary test is here too: a finished duel
has written nothing to attempts, balances or settlements.
"""
import unittest
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.ranked_bank.catalog import load_reviewed_bank
from backend.tests.browser import BROWSER
from backend.versus import match as versus_match


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class VersusMatchTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        cls.bank = load_reviewed_bank()

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)

    def _player(self, username):
        client = TestClient(create_app(), headers=BROWSER)
        registration = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(registration.status_code, 200, registration.text)
        self.assertEqual(
            client.post(
                "/api/auth/login",
                json={"username": username, "login_id": registration.json()["login_id"]},
            ).status_code,
            200,
        )
        return client

    def _pair(self, game):
        """A full room: host, guest, room id and code."""
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": game}).json()
        guest = self._player("beaguest")
        joined = guest.post("/api/versus/rooms/join", json={"code": room["code"]})
        self.assertEqual(joined.status_code, 200, joined.text)
        return host, guest, room

    def _started(self, game):
        host, guest, room = self._pair(game)
        answer = host.post(f"/api/versus/rooms/{room['id']}/start")
        self.assertEqual(answer.status_code, 200, answer.text)
        return host, guest, answer.json()

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

    def _right_answer(self, match_id, seq):
        """The stored question's right belt, read the engine's own way."""
        conn = migrate.connect(self.conninfo)
        try:
            stored = migrate.fetch_one(
                conn,
                "SELECT question_version_id FROM versus_match_questions"
                " WHERE match_id = %s AND seq = %s",
                (match_id, seq),
            )
            question = versus_match._question_for_version(
                conn, self.bank, stored["question_version_id"]
            )
            return question.correct_belt
        finally:
            conn.close()

    # -- starting ----------------------------------------------------------

    def test_the_host_starts_a_full_room_and_both_see_the_duel(self):
        host, guest, state = self._started("quiz")
        self.assertEqual(state["state"], "playing")
        self.assertEqual(state["question_count"], versus_match.QUIZ_QUESTIONS)
        self.assertEqual(state["you"]["score"], 0)
        self.assertEqual(state["opponent"]["username"], "beaguest")
        theirs = guest.get(f"/api/versus/matches/{state['id']}")
        self.assertEqual(theirs.status_code, 200, theirs.text)
        self.assertEqual(theirs.json()["opponent"]["username"], "anahost")
        stored = self._one(
            "SELECT COUNT(*) AS n FROM versus_match_questions WHERE match_id = %s",
            (state["id"],),
        )
        self.assertEqual(stored["n"], versus_match.QUIZ_QUESTIONS)

    def test_the_room_poll_carries_the_match_id(self):
        host, guest, room = self._pair("quiz")
        started = host.post(f"/api/versus/rooms/{room['id']}/start").json()
        polled = guest.get(f"/api/versus/rooms/{room['id']}").json()
        self.assertEqual(polled["match_id"], started["id"])

    def test_only_the_host_starts_and_only_a_full_room(self):
        host, guest, room = self._pair("quiz")
        self.assertEqual(guest.post(f"/api/versus/rooms/{room['id']}/start").status_code, 409)
        lonely = self._player("carloslone")
        solo = lonely.post("/api/versus/rooms", json={"game": "quiz"}).json()
        self.assertEqual(lonely.post(f"/api/versus/rooms/{solo['id']}/start").status_code, 409)

    def test_starting_twice_answers_the_same_duel(self):
        host, guest, room = self._pair("quiz")
        first = host.post(f"/api/versus/rooms/{room['id']}/start").json()
        second = host.post(f"/api/versus/rooms/{room['id']}/start").json()
        self.assertEqual(first["id"], second["id"])

    # -- the quiz duel -----------------------------------------------------

    def test_both_players_meet_the_same_first_question(self):
        host, guest, state = self._started("quiz")
        mine = host.get(f"/api/versus/matches/{state['id']}/question").json()
        theirs = guest.get(f"/api/versus/matches/{state['id']}/question").json()
        self.assertEqual(mine["prompt_en"], theirs["prompt_en"])
        self.assertEqual(mine["options"], theirs["options"])
        self.assertEqual(mine["of"], versus_match.QUIZ_QUESTIONS)

    def test_a_right_answer_scores_and_a_wrong_one_advances_for_nothing(self):
        host, guest, state = self._started("quiz")
        right = self._right_answer(state["id"], 1)
        mine = host.post(
            f"/api/versus/matches/{state['id']}/answer", json={"seq": 1, "choice": right}
        ).json()
        self.assertTrue(mine["correct"])
        self.assertGreaterEqual(mine["gained"], versus_match.CORRECT_POINTS)
        theirs = guest.post(
            f"/api/versus/matches/{state['id']}/answer",
            json={"seq": 1, "choice": "NOT-A-BELT"},
        ).json()
        self.assertFalse(theirs["correct"])
        self.assertEqual(theirs["gained"], 0)
        self.assertEqual(theirs["correct_belt"], right)
        polled = host.get(f"/api/versus/matches/{state['id']}").json()
        self.assertGreaterEqual(polled["you"]["score"], versus_match.CORRECT_POINTS)
        self.assertEqual(polled["opponent"]["score"], 0)
        self.assertEqual(polled["you"]["seq"], 2)

    def test_an_answer_out_of_sequence_is_refused(self):
        host, _, state = self._started("quiz")
        answer = host.post(
            f"/api/versus/matches/{state['id']}/answer", json={"seq": 2, "choice": "X"}
        )
        self.assertEqual(answer.status_code, 409)

    def test_a_late_answer_is_accepted_but_scores_nothing(self):
        host, _, state = self._started("quiz")
        right = self._right_answer(state["id"], 1)
        shove = versus_match.LATE_GRACE + timedelta(seconds=versus_match.QUESTION_SECONDS + 1)
        self._sql(
            "UPDATE versus_match_players SET question_sent_at = question_sent_at - %s"
            " WHERE match_id = %s",
            (shove, state["id"]),
        )
        answer = host.post(
            f"/api/versus/matches/{state['id']}/answer", json={"seq": 1, "choice": right}
        ).json()
        self.assertFalse(answer["correct"])
        self.assertEqual(answer["gained"], 0)

    def test_the_whole_duel_plays_to_a_winner(self):
        host, guest, state = self._started("quiz")
        for seq in range(1, versus_match.QUIZ_QUESTIONS + 1):
            right = self._right_answer(state["id"], seq)
            host.post(f"/api/versus/matches/{state['id']}/answer", json={"seq": seq, "choice": right})
            guest.post(
                f"/api/versus/matches/{state['id']}/answer", json={"seq": seq, "choice": "NOT-A-BELT"}
            )
        mine = host.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(mine["state"], "finished")
        self.assertEqual(mine["outcome"], "you")
        self.assertEqual(mine["you"]["correct"], versus_match.QUIZ_QUESTIONS)
        theirs = guest.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(theirs["outcome"], "opponent")

    def test_the_deadline_finishes_an_abandoned_duel(self):
        host, guest, state = self._started("quiz")
        right = self._right_answer(state["id"], 1)
        host.post(f"/api/versus/matches/{state['id']}/answer", json={"seq": 1, "choice": right})
        self._sql(
            "UPDATE versus_matches SET ends_at = started_at - interval '1 second' WHERE id = %s",
            (state["id"],),
        )
        polled = host.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(polled["state"], "finished")
        self.assertEqual(polled["outcome"], "you")

    def test_a_forfeit_hands_the_duel_to_the_one_who_stayed(self):
        host, guest, state = self._started("quiz")
        right = self._right_answer(state["id"], 1)
        guest.post(f"/api/versus/matches/{state['id']}/answer", json={"seq": 1, "choice": right})
        host.post(f"/api/versus/matches/{state['id']}/forfeit")
        self._sql(
            "UPDATE versus_matches SET ends_at = started_at - interval '1 second' WHERE id = %s",
            (state["id"],),
        )
        self.assertEqual(guest.get(f"/api/versus/matches/{state['id']}").json()["outcome"], "you")

    # -- the handler duel --------------------------------------------------

    def test_a_handler_duel_shares_a_seed_and_stores_no_questions(self):
        host, guest, state = self._started("handler")
        self.assertIsNotNone(state["seed"])
        theirs = guest.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(theirs["seed"], state["seed"])
        stored = self._one(
            "SELECT COUNT(*) AS n FROM versus_match_questions WHERE match_id = %s",
            (state["id"],),
        )
        self.assertEqual(stored["n"], 0)
        self.assertEqual(
            host.get(f"/api/versus/matches/{state['id']}/question").status_code, 404
        )

    def test_a_handler_score_only_ever_goes_up_and_final_ends_it(self):
        host, guest, state = self._started("handler")
        host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 40})
        host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 25})
        polled = host.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(polled["you"]["score"], 40)
        host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 61, "final": True})
        guest.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 33, "final": True})
        ended = guest.get(f"/api/versus/matches/{state['id']}").json()
        self.assertEqual(ended["state"], "finished")
        self.assertEqual(ended["outcome"], "opponent")

    def test_equal_scores_are_a_tie(self):
        host, guest, state = self._started("handler")
        host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 30, "final": True})
        guest.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 30, "final": True})
        self.assertEqual(host.get(f"/api/versus/matches/{state['id']}").json()["outcome"], "tie")

    # -- edges and the boundary --------------------------------------------

    def test_an_outsider_sees_no_duel(self):
        host, guest, state = self._started("quiz")
        outsider = self._player("carloslone")
        self.assertEqual(outsider.get(f"/api/versus/matches/{state['id']}").status_code, 404)

    def test_a_finished_duel_takes_no_more_answers(self):
        host, guest, state = self._started("handler")
        host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 10, "final": True})
        guest.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 5, "final": True})
        refused = host.post(f"/api/versus/matches/{state['id']}/progress", json={"score": 99})
        self.assertEqual(refused.status_code, 409)

    def test_a_duel_touches_nothing_of_ranked(self):
        host, guest, state = self._started("quiz")
        right = self._right_answer(state["id"], 1)
        host.post(f"/api/versus/matches/{state['id']}/answer", json={"seq": 1, "choice": right})
        for table in ("attempts", "balances", "settlements"):
            self.assertEqual(self._one(f"SELECT COUNT(*) AS n FROM {table}")["n"], 0)


if __name__ == "__main__":
    unittest.main()
