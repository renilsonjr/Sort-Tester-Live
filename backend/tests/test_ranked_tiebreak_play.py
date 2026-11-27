"""Playing a prize tie-break round (issue #24, slice 3).

Each test is named after the settled rule it holds (Decisions 9-10, Q4,
Q8). They run over HTTP against a real database, because the promises
that matter -- nothing revealed, no seasonal points moved -- are promises
about what crosses the wire and what lands in the balance.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone
from unittest import mock

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.ranked import modes, tiebreaks
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
class TiebreakPlayTests(unittest.TestCase):
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
        self.clock = FrozenClock(datetime.now(timezone.utc).replace(microsecond=0))
        patcher = mock.patch("backend.routers.deps.CLOCK", self.clock)
        patcher.start()
        self.addCleanup(patcher.stop)

        self.season = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at, closed_at, frozen_at)"
            " VALUES ('official', 'Peak Season', %s, %s, %s, %s) RETURNING id",
            (self.clock.now() - timedelta(days=60), self.clock.now() - timedelta(minutes=10),
             self.clock.now() - timedelta(minutes=10), self.clock.now() - timedelta(minutes=4)),
        )["id"]
        self.conn.commit()
        self.alice = TestClient(create_app(), headers=BROWSER)
        self.alice_id = self._sign_in(self.alice, "tie_alice", 700)
        self.bob = TestClient(create_app(), headers=BROWSER)
        self.bob_id = self._sign_in(self.bob, "tie_bob", 700)
        self.outsider = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.outsider, "not_tied", 900)
        self.group, self.round = self._group([self.alice_id, self.bob_id], round_number=1)

    # --- helpers ---

    def _sign_in(self, client, username, points):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        client.post("/api/auth/login", json={"username": username, "login_id": reg.json()["login_id"]})
        account_id = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = %s", (username,)
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET current_points = EXCLUDED.current_points",
            (account_id, points),
        )
        self.conn.commit()
        return account_id

    def _group(self, members, *, round_number, deadline_hours=24):
        group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, %s, 700, 1, %s) RETURNING id",
            (self.season, "season_close" if round_number == 1 else "replacement", self.clock.now()),
        )["id"]
        for member in members:
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_group_members (group_id, account_id) VALUES (%s, %s)",
                (group, member),
            )
        round_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at, hats)"
            " VALUES (%s, %s, %s, %s, 1) RETURNING id",
            (group, round_number, self.clock.now(),
             self.clock.now() + timedelta(hours=deadline_hours)),
        )["id"]
        for member in members:
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_round_players (round_id, account_id) VALUES (%s, %s)",
                (round_id, member),
            )
        tiebreaks.assign_round_questions(
            self.conn, round_id, self.season, BANK, rng=random.Random(round_number)
        )
        self.conn.commit()
        return group, round_id

    def _start(self, client, round_id=None):
        response = client.post(f"/api/ranked/tiebreak/rounds/{round_id or self.round}/attempts")
        if response.status_code == 201:
            client.headers[CAPABILITY_HEADER] = response.json()["capability"]
        return response

    def _current(self, client, attempt_id):
        return client.get(f"/api/ranked/attempts/{attempt_id}/current")

    def _answer(self, client, attempt_id, seq, choice="YELLOW"):
        return client.post(
            f"/api/ranked/attempts/{attempt_id}/answer", json={"seq": seq, "choice": choice}
        )

    def _correct_choice(self, attempt_id, seq):
        key = migrate.fetch_one(
            self.conn,
            "SELECT qv.bank_key FROM attempt_answers aa"
            " JOIN question_versions qv ON qv.id = aa.question_version_id"
            " WHERE aa.attempt_id = %s AND aa.seq = %s",
            (attempt_id, seq),
        )["bank_key"]
        return next(q.correct_belt for q in BANK.questions if q.canonical_id == key)

    def _balance(self, account_id):
        return migrate.fetch_one(
            self.conn, "SELECT current_points FROM balances WHERE account_id = %s", (account_id,)
        )["current_points"]

    # --- who may play ---

    def test_a_member_starts_their_attempt_with_question_one(self):
        started = self._start(self.alice)
        self.assertEqual(started.status_code, 201, started.text)
        self.assertEqual(started.json()["mode"], "tiebreak")
        current = self._current(self.alice, started.json()["attempt_id"])
        self.assertEqual(current.status_code, 200)
        self.assertEqual(current.json()["seq"], 1)

    def test_somebody_outside_the_group_is_told_there_is_no_such_round(self):
        """Not that it is closed, or full: nothing about the round."""
        refused = self._start(self.outsider)
        self.assertEqual(refused.status_code, 404)
        self.assertEqual(refused.json()["detail"], "There is no such tie-break round.")

    def test_each_round_is_played_once(self):
        """No same-round retry after finishing, quitting or a refresh."""
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self.alice.post(f"/api/ranked/attempts/{attempt_id}/quit")
        again = self._start(self.alice)
        self.assertEqual(again.status_code, 409)
        self.assertIn("already played this round", again.json()["detail"])

    def test_after_the_deadline_nobody_starts(self):
        self.clock.advance(24 * 3600 + 1)
        refused = self._start(self.alice)
        self.assertEqual(refused.status_code, 409)
        self.assertIn("closed", refused.json()["detail"])

    # --- the shape ---

    def test_five_questions_and_the_round_clock(self):
        """Rounds 1-3 at five seconds, round 4 at four, round 5 at three."""
        self.assertEqual(modes.settings_for("tiebreak", 1).question_count, 5)
        self.assertEqual(
            [modes.settings_for("tiebreak", n).question_seconds for n in range(1, 6)],
            [5, 5, 5, 4, 3],
        )
        attempt_id = self._start(self.alice).json()["attempt_id"]
        row = migrate.fetch_one(
            self.conn,
            "SELECT first_sent_at, deadline_at FROM attempt_answers WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        self.assertEqual(row["deadline_at"] - row["first_sent_at"], timedelta(seconds=5))

    def test_round_five_gives_three_seconds(self):
        _, round_five = self._group([self.alice_id], round_number=5)
        attempt_id = self._start(self.alice, round_five).json()["attempt_id"]
        row = migrate.fetch_one(
            self.conn,
            "SELECT first_sent_at, deadline_at FROM attempt_answers WHERE attempt_id = %s AND seq = 1",
            (attempt_id,),
        )
        self.assertEqual(row["deadline_at"] - row["first_sent_at"], timedelta(seconds=3))

    def test_everybody_in_the_round_gets_the_same_five(self):
        a = self._start(self.alice).json()["attempt_id"]
        b = self._start(self.bob).json()["attempt_id"]
        def keys(attempt_id):
            return [
                row["question_version_id"]
                for row in migrate.fetch_all(
                    self.conn,
                    "SELECT aq.question_version_id FROM assignment_questions aq"
                    " JOIN attempts a ON a.assignment_id = aq.assignment_id"
                    " WHERE a.id = %s ORDER BY aq.seq",
                    (attempt_id,),
                )
            ]
        self.assertEqual(keys(a), keys(b))
        self.assertEqual(len(keys(a)), 5)

    # --- it advances by itself (Q8) ---

    def test_an_answer_opens_the_next_question_at_once(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self._answer(self.alice, attempt_id, 1)
        self.assertEqual(self._current(self.alice, attempt_id).json()["seq"], 2)

    def test_there_is_no_next_button(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self._answer(self.alice, attempt_id, 1)
        self.assertEqual(
            self.alice.post(f"/api/ranked/attempts/{attempt_id}/advance").status_code, 409
        )

    def test_a_question_that_runs_out_opens_the_next_one(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self.clock.advance(6)
        current = self._current(self.alice, attempt_id)
        self.assertEqual(current.json()["seq"], 2)

    def test_the_fifth_answer_ends_the_attempt_with_no_sixth_question(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        for seq in range(1, 6):
            last = self._answer(self.alice, attempt_id, seq)
        self.assertTrue(last.json()["finished"])
        state = migrate.fetch_one(
            self.conn, "SELECT state, final_outcome FROM attempts WHERE id = %s", (attempt_id,)
        )
        self.assertEqual((state["state"], state["final_outcome"]), ("finalized", "completed"))

    # --- nothing revealed until the deadline (Q4) ---

    def test_an_answer_says_it_was_received_and_nothing_else(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        right = self._answer(self.alice, attempt_id, 1, self._correct_choice(attempt_id, 1)).json()
        wrong_choice = "PURPLE" if self._correct_choice(attempt_id, 2) != "PURPLE" else "BLUE"
        wrong = self._answer(self.alice, attempt_id, 2, wrong_choice).json()
        for body in (right, wrong):
            self.assertIsNone(body["correct"])
            self.assertEqual(body["outcome"], "submitted")
        # a right and a wrong answer are indistinguishable on the wire
        self.assertEqual({k: v for k, v in right.items() if k != "seq"},
                         {k: v for k, v in wrong.items() if k != "seq"})

    def test_finishing_reveals_no_score(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        for seq in range(1, 6):
            last = self._answer(self.alice, attempt_id, seq, self._correct_choice(attempt_id, seq))
        body = last.json()
        self.assertNotIn("result", body)
        self.assertNotIn("raw_score", last.text)

    def test_the_result_endpoint_waits_for_the_round(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        for seq in range(1, 6):
            self._answer(self.alice, attempt_id, seq)
        result = self.alice.get(f"/api/ranked/attempts/{attempt_id}/result")
        self.assertEqual(result.status_code, 409)
        self.assertIn("when the round closes", result.json()["detail"])

    def test_quitting_reveals_nothing_either(self):
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self._answer(self.alice, attempt_id, 1, self._correct_choice(attempt_id, 1))
        response = self.alice.post(f"/api/ranked/attempts/{attempt_id}/quit")
        quit_ = response.json()
        self.assertEqual(quit_["final_outcome"], "quit")
        self.assertTrue(quit_["result"]["hidden_until_round_closes"])
        # nothing that would hint at the score, anywhere in the response
        for leak in ("raw_score", "points_after", "correct"):
            self.assertNotIn(leak, response.text)

    # --- no seasonal points move ---

    def test_a_completed_tiebreak_changes_no_points(self):
        before = self._balance(self.alice_id)
        attempt_id = self._start(self.alice).json()["attempt_id"]
        for seq in range(1, 6):
            self._answer(self.alice, attempt_id, seq, self._correct_choice(attempt_id, seq))
        self.assertEqual(self._balance(self.alice_id), before)
        self.assertIsNone(
            migrate.fetch_one(
                self.conn, "SELECT attempt_id FROM settlements WHERE attempt_id = %s", (attempt_id,)
            )
        )

    def test_quitting_a_tiebreak_costs_no_points(self):
        """No seasonal -10 for a tie-break Quit."""
        before = self._balance(self.alice_id)
        attempt_id = self._start(self.alice).json()["attempt_id"]
        self.alice.post(f"/api/ranked/attempts/{attempt_id}/quit")
        self.assertEqual(self._balance(self.alice_id), before)

    def test_the_settlement_sweep_leaves_tiebreaks_alone(self):
        from backend.ranked import settlement
        attempt_id = self._start(self.alice).json()["attempt_id"]
        migrate.execute(
            self.conn,
            "UPDATE attempts SET state = 'terminal_pending', final_outcome = 'completed'"
            " WHERE id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        self.assertEqual(settlement.settle_pending(self.conn, clock=self.clock), 0)

    def test_a_tiebreak_never_counts_towards_eligibility(self):
        """Settled Q5: tie-break attempts alone do not qualify."""
        from backend.ranked import standings
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, 'r-a')",
            (self.alice_id,),
        )
        self.conn.commit()
        attempt_id = self._start(self.alice).json()["attempt_id"]
        for seq in range(1, 6):
            self._answer(self.alice, attempt_id, seq)
        self.assertEqual(standings.standings(self.conn, self.season), [])


if __name__ == "__main__":
    unittest.main()
