"""Four belts and real feedback for ordinary and promotion questions
(issue #95's prerequisite: wiring Ranked play).

Owner decision 2026-11-15: Ranked questions show four belts like a
tie-break round's, drawn and stored rather than derived. Answering one
now also returns what a feedback screen needs: the right belt, its
difficulty, the ordinary worth of that one question, and the bilingual
explanation -- never for a tie-break, which stays hidden until its round
closes.
"""
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.ranked_bank.catalog import load_reviewed_bank
from backend.tests.browser import BROWSER

CAPABILITY_HEADER = "X-Attempt-Capability"
BANK = load_reviewed_bank()


class FrozenClock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment

    def advance(self, seconds):
        self.moment += timedelta(seconds=seconds)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class AnswerFeedbackTests(unittest.TestCase):
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
        migrate.execute(
            self.conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'test-season')"
        )
        self.conn.commit()
        self.client = TestClient(create_app(), headers=BROWSER)
        reg = self.client.post("/api/auth/register", json={"username": "feedback_player"})
        self.client.post("/api/auth/login", json={"username": "feedback_player", "login_id": reg.json()["login_id"]})

    def _start(self):
        r = self.client.post("/api/ranked/attempts")
        self.assertEqual(r.status_code, 201, r.text)
        self.client.headers[CAPABILITY_HEADER] = r.json()["capability"]
        return r.json()["attempt_id"]

    def _current(self, attempt_id):
        return self.client.get(f"/api/ranked/attempts/{attempt_id}/current").json()

    def _correct_belt(self, bank_key):
        return next(q.correct_belt for q in BANK.questions if q.canonical_id == bank_key)

    def _bank_key_for(self, attempt_id, seq):
        return migrate.fetch_one(
            self.conn,
            "SELECT qv.bank_key FROM assignment_questions aq"
            " JOIN attempts a ON a.assignment_id = aq.assignment_id"
            " JOIN question_versions qv ON qv.id = aq.question_version_id"
            " WHERE a.id = %s AND aq.seq = %s",
            (attempt_id, seq),
        )["bank_key"]

    # --- the four options ---

    def test_an_ordinary_question_offers_four_belts_including_the_right_one(self):
        attempt_id = self._start()
        q = self._current(attempt_id)
        self.assertEqual(len(q["options"]), 4)
        self.assertEqual(len(set(q["options"])), 4)
        correct = self._correct_belt(self._bank_key_for(attempt_id, 1))
        self.assertIn(correct, q["options"])

    def test_the_options_are_stable_across_repeated_reads(self):
        attempt_id = self._start()
        first = self._current(attempt_id)["options"]
        second = self._current(attempt_id)["options"]
        self.assertEqual(first, second)

    def test_different_attempts_can_draw_different_options(self):
        """Personal to the attempt, not shared like a tie-break round's."""
        seen = set()
        for _ in range(5):
            other = TestClient(create_app(), headers=BROWSER)
            name = f"opt_{len(seen)}_{_}"
            reg = other.post("/api/auth/register", json={"username": name})
            other.post("/api/auth/login", json={"username": name, "login_id": reg.json()["login_id"]})
            r = other.post("/api/ranked/attempts")
            other.headers[CAPABILITY_HEADER] = r.json()["capability"]
            q = other.get(f"/api/ranked/attempts/{r.json()['attempt_id']}/current").json()
            seen.add(tuple(q["options"]))
        # not guaranteed different every time, but across 5 draws from a
        # 9-belt pool it would be suspicious if they were all identical
        self.assertGreater(len(seen), 1)

    # --- feedback on an ordinary answer ---

    def test_a_correct_answer_carries_full_feedback(self):
        attempt_id = self._start()
        correct = self._correct_belt(self._bank_key_for(attempt_id, 1))
        r = self.client.post(
            f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": 1, "choice": correct}
        )
        body = r.json()
        self.assertTrue(body["correct"])
        self.assertEqual(body["correct_belt"], correct)
        self.assertIn(body["difficulty"], ("easy", "medium", "hard"))
        self.assertGreater(body["worth"], 0)
        self.assertTrue(body["explanation_en"])
        self.assertTrue(body["explanation_es"])

    def test_a_wrong_answer_still_carries_the_right_belt_and_explanation(self):
        attempt_id = self._start()
        correct = self._correct_belt(self._bank_key_for(attempt_id, 1))
        wrong = next(b for b in ("PURPLE", "ORANGE", "GREEN", "YELLOW") if b != correct)
        r = self.client.post(
            f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": 1, "choice": wrong}
        )
        body = r.json()
        self.assertFalse(body["correct"])
        self.assertEqual(body["correct_belt"], correct)
        self.assertLess(body["worth"], 0)

    def test_an_idempotent_second_submit_returns_the_same_feedback(self):
        attempt_id = self._start()
        correct = self._correct_belt(self._bank_key_for(attempt_id, 1))
        first = self.client.post(
            f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": 1, "choice": correct}
        ).json()
        second = self.client.post(
            f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": 1, "choice": "PURPLE"}
        ).json()
        self.assertEqual(first["correct_belt"], second["correct_belt"])
        self.assertEqual(first["worth"], second["worth"])
        self.assertTrue(second["correct"])  # the stored result, not this call's choice

    def test_a_timed_out_answer_still_names_the_correct_belt(self):
        clock = FrozenClock(datetime.now(timezone.utc))
        with mock.patch("backend.routers.deps.CLOCK", clock):
            attempt_id = self._start()
            correct = self._correct_belt(self._bank_key_for(attempt_id, 1))
            clock.advance(11)  # past the ordinary ten-second deadline
            body = self.client.post(
                f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": 1, "choice": correct}
            ).json()
        self.assertEqual(body["outcome"], "timeout")
        self.assertEqual(body["correct_belt"], correct)
        self.assertLess(body["worth"], 0)


if __name__ == "__main__":
    unittest.main()
