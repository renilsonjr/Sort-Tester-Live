"""Thin HTTP layer over the ranked engine (issue #8, piece 4)."""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app

CAPABILITY_HEADER = "X-Attempt-Capability"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RankedRouterTests(unittest.TestCase):
    def _start_as_page(self, client):
        """Start an attempt the way the original page does: keep the returned
        capability and send it on every later request from this client."""
        start = client.post("/api/ranked/attempts")
        self.assertEqual(start.status_code, 201, start.text)
        client.headers[CAPABILITY_HEADER] = start.json()["capability"]
        return start.json()["attempt_id"]

    def _second_tab(self):
        """Another page of the same signed-in account: same session cookie,
        but none of the original page's memory."""
        tab = TestClient(create_app())
        for cookie in self.client.cookies.jar:
            tab.cookies.set(cookie.name, cookie.value)
        return tab

    def _calls(self, client, attempt_id):
        base = f"/api/ranked/attempts/{attempt_id}"
        return [
            client.get(f"{base}/current"),
            client.post(f"{base}/answer", json={"seq": 1, "choice": "YELLOW"}),
            client.post(f"{base}/advance"),
            client.post(f"{base}/heartbeat"),
            client.post(f"{base}/quit"),
        ]

    def _attempt_field(self, attempt_id, field):
        conn = migrate.connect(self.conninfo)
        try:
            row = migrate.fetch_one(
                conn, f"SELECT {field} AS v FROM attempts WHERE id = %s", (attempt_id,)
            )
        finally:
            conn.close()
        return row["v"]

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
        # the page keeps the capability in memory and sends it on every request
        self.client.headers[CAPABILITY_HEADER] = start.json()["capability"]

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
            # only the fifteenth answer finishes the attempt, with no Next
            self.assertEqual(answer.json()["finished"], seq == 15)
            advance = self.client.post(f"/api/ranked/attempts/{attempt_id}/advance")
            if seq < 15:
                self.assertEqual(advance.status_code, 200, advance.text)
                self.assertEqual(advance.json(), {"next_seq": seq + 1})
            else:
                self.assertEqual(advance.status_code, 410)

        # the attempt has ended: it is gone for further calls
        done = self.client.get(f"/api/ranked/attempts/{attempt_id}/current")
        self.assertEqual(done.status_code, 410)

    def test_answer_reports_the_outcome(self):
        self._sign_in(self.client, "outcome_player")
        attempt_id = self._start_as_page(self.client)
        answer = self.client.post(
            f"/api/ranked/attempts/{attempt_id}/answer",
            json={"seq": 1, "choice": "YELLOW"},
        )
        self.assertIn(answer.json()["outcome"], ("correct", "wrong"))

    def test_heartbeat_keeps_a_live_attempt(self):
        self._sign_in(self.client, "beating_player")
        attempt_id = self._start_as_page(self.client)
        beat = self.client.post(f"/api/ranked/attempts/{attempt_id}/heartbeat")
        self.assertEqual(beat.status_code, 204, beat.text)

    def test_heartbeat_requires_the_owner(self):
        self._sign_in(self.client, "beat_owner")
        attempt_id = self._start_as_page(self.client)
        anon = TestClient(create_app())
        self.assertEqual(
            anon.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 401
        )
        other = TestClient(create_app())
        self._sign_in(other, "beat_other")
        self.assertEqual(
            other.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 404
        )

    def test_ended_attempt_is_gone_on_every_endpoint(self):
        self._sign_in(self.client, "silent_player")
        attempt_id = self._start_as_page(self.client)
        # pretend the page was last heard from a minute ago: grace has expired
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE attempts SET last_heartbeat_at = now() - interval '60 seconds'"
            " WHERE id = %s",
            (attempt_id,),
        )
        conn.commit()
        conn.close()
        base = f"/api/ranked/attempts/{attempt_id}"
        responses = [
            self.client.post(f"{base}/heartbeat"),
            self.client.post(f"{base}/answer", json={"seq": 1, "choice": "YELLOW"}),
            self.client.post(f"{base}/advance"),
            self.client.get(f"{base}/current"),
        ]
        self.assertEqual([r.status_code for r in responses], [410, 410, 410, 410])

    def test_quit_ends_the_attempt_and_can_be_repeated(self):
        self._sign_in(self.client, "quitting_player")
        attempt_id = self._start_as_page(self.client)
        base = f"/api/ranked/attempts/{attempt_id}"
        first = self.client.post(f"{base}/quit")
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["final_outcome"], "quit")
        # a retried Quit gets the same answer, not an error
        second = self.client.post(f"{base}/quit")
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json(), first.json())
        self.assertEqual(self.client.post(f"{base}/heartbeat").status_code, 410)

    def test_quit_requires_the_owner(self):
        self._sign_in(self.client, "quit_owner")
        attempt_id = self._start_as_page(self.client)
        anon = TestClient(create_app())
        self.assertEqual(
            anon.post(f"/api/ranked/attempts/{attempt_id}/quit").status_code, 401
        )
        other = TestClient(create_app())
        self._sign_in(other, "quit_other")
        self.assertEqual(
            other.post(f"/api/ranked/attempts/{attempt_id}/quit").status_code, 404
        )

    # --- page capability (slice 4) ---

    def test_start_returns_a_capability(self):
        self._sign_in(self.client, "ticket_player")
        start = self.client.post("/api/ranked/attempts")
        self.assertGreaterEqual(len(start.json()["capability"]), 40)

    def test_second_tab_is_refused_on_every_endpoint(self):
        self._sign_in(self.client, "two_tab_player")
        attempt_id = self._start_as_page(self.client)
        tab = self._second_tab()
        statuses = [r.status_code for r in self._calls(tab, attempt_id)]
        self.assertEqual(statuses, [403, 403, 403, 403, 403])
        # the refused Quit did not end the original page's attempt
        self.assertEqual(self._attempt_field(attempt_id, "state"), "active")

    def test_wrong_capability_is_refused_on_every_endpoint(self):
        self._sign_in(self.client, "guessing_player")
        attempt_id = self._start_as_page(self.client)
        tab = self._second_tab()
        tab.headers[CAPABILITY_HEADER] = "not-the-real-capability"
        statuses = [r.status_code for r in self._calls(tab, attempt_id)]
        self.assertEqual(statuses, [403, 403, 403, 403, 403])

    def test_refused_heartbeat_does_not_keep_the_attempt_alive(self):
        self._sign_in(self.client, "refresh_player")
        attempt_id = self._start_as_page(self.client)
        before = self._attempt_field(attempt_id, "last_heartbeat_at")
        tab = self._second_tab()
        self.assertEqual(
            tab.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 403
        )
        self.assertEqual(self._attempt_field(attempt_id, "last_heartbeat_at"), before)

    def test_second_tab_cannot_start_a_replacement(self):
        self._sign_in(self.client, "replace_player")
        self._start_as_page(self.client)
        self.assertEqual(self._second_tab().post("/api/ranked/attempts").status_code, 409)

    # --- promotion entry (slice 6) ---

    def _set_points(self, username, points):
        conn = migrate.connect(self.conninfo)
        try:
            migrate.execute(
                conn,
                "INSERT INTO balances (account_id, current_points)"
                " SELECT id, %s FROM accounts WHERE username_lower = %s",
                (points, username.lower()),
            )
            conn.commit()
        finally:
            conn.close()

    def test_entry_reports_points_badge_and_mode(self):
        self._sign_in(self.client, "entry_player")
        entry = self.client.get("/api/ranked/entry")
        self.assertEqual(entry.status_code, 200, entry.text)
        self.assertEqual(entry.json(), {"points": 0, "badge": "Iron", "mode": "normal"})
        # reading the entry information starts nothing
        self.assertEqual(self.client.post("/api/ranked/attempts").status_code, 201)

    def test_entry_requires_authentication(self):
        anon = TestClient(create_app())
        self.assertEqual(anon.get("/api/ranked/entry").status_code, 401)

    def test_start_without_a_body_is_a_normal_attempt(self):
        self._sign_in(self.client, "plain_player")
        start = self.client.post("/api/ranked/attempts")
        self.assertEqual(start.status_code, 201, start.text)
        self.assertEqual(start.json()["mode"], "normal")

    def test_promotion_is_refused_below_the_cap(self):
        self._sign_in(self.client, "eager_player")
        start = self.client.post("/api/ranked/attempts", json={"mode": "promotion"})
        self.assertEqual(start.status_code, 409)
        self.assertEqual(start.json()["detail"], "Promotion not available")

    def test_at_the_cap_only_promotion_starts(self):
        self._sign_in(self.client, "capped_player")
        self._set_points("capped_player", 1000)
        entry = self.client.get("/api/ranked/entry")
        self.assertEqual(
            entry.json(), {"points": 1000, "badge": "Iron", "mode": "promotion"}
        )
        normal = self.client.post("/api/ranked/attempts")
        self.assertEqual(normal.status_code, 409)
        self.assertEqual(normal.json()["detail"], "Promotion required")
        promotion = self.client.post("/api/ranked/attempts", json={"mode": "promotion"})
        self.assertEqual(promotion.status_code, 201, promotion.text)
        self.assertEqual(promotion.json()["mode"], "promotion")
        self.assertIn("capability", promotion.json())

    def test_unknown_mode_is_a_bad_request(self):
        self._sign_in(self.client, "odd_player")
        start = self.client.post("/api/ranked/attempts", json={"mode": "tiebreak"})
        self.assertEqual(start.status_code, 422)

    # --- score at once (issue #9, slice 3) ---

    RESULT_KEYS = {
        "final_outcome", "raw_score", "adjustment", "points_before",
        "points_after", "badge_before", "badge_after",
    }

    def _entry_points(self):
        return self.client.get("/api/ranked/entry").json()["points"]

    def test_final_answer_returns_the_result_and_applies_the_points(self):
        self._sign_in(self.client, "scored_player")
        attempt_id = self._start_as_page(self.client)
        base = f"/api/ranked/attempts/{attempt_id}"
        answer = None
        for seq in range(1, 16):
            answer = self.client.post(
                f"{base}/answer", json={"seq": seq, "choice": "YELLOW"}
            )
            self.assertEqual("result" in answer.json(), seq == 15)
            if seq < 15:
                self.client.post(f"{base}/advance")
        result = answer.json()["result"]
        self.assertEqual(set(result), self.RESULT_KEYS)
        self.assertEqual(result["final_outcome"], "completed")
        self.assertEqual(result["points_before"], 0)
        self.assertEqual(
            result["points_after"], result["points_before"] + result["adjustment"]
        )
        self.assertEqual(self._entry_points(), result["points_after"])
        self.assertEqual(self._attempt_field(attempt_id, "state"), "finalized")

    def test_quit_returns_the_result_and_applies_the_penalty(self):
        self._sign_in(self.client, "penalised_player")
        attempt_id = self._start_as_page(self.client)
        quit_response = self.client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        result = quit_response.json()["result"]
        self.assertEqual(result["final_outcome"], "quit")
        self.assertEqual((result["raw_score"], result["adjustment"]), (0, -10))
        self.assertEqual(self._entry_points(), -10)
        self.assertEqual(self._attempt_field(attempt_id, "state"), "finalized")

    def test_attempt_found_ended_is_settled_with_the_gone_answer(self):
        self._sign_in(self.client, "vanished_player")
        attempt_id = self._start_as_page(self.client)
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE attempts SET last_heartbeat_at = now() - interval '60 seconds'"
            " WHERE id = %s",
            (attempt_id,),
        )
        conn.commit()
        conn.close()
        gone = self.client.post(f"/api/ranked/attempts/{attempt_id}/heartbeat")
        self.assertEqual(gone.status_code, 410)
        self.assertEqual(self._attempt_field(attempt_id, "state"), "finalized")
        self.assertEqual(self._attempt_field(attempt_id, "final_outcome"), "disconnect")
        # the one question that was on screen timed out and was deducted
        self.assertLess(self._entry_points(), 0)

    def _abandon(self, attempt_id):
        """Pretend the page was last heard from a minute ago."""
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE attempts SET last_heartbeat_at = now() - interval '60 seconds'"
            " WHERE id = %s",
            (attempt_id,),
        )
        conn.commit()
        conn.close()

    def test_start_after_an_abandoned_attempt_settles_it_and_admits(self):
        self._sign_in(self.client, "returning_player")
        old_id = self._start_as_page(self.client)
        self._abandon(old_id)
        # a fresh page of the same account: it never held the old capability
        new = self._second_tab().post("/api/ranked/attempts")
        self.assertEqual(new.status_code, 201, new.text)
        self.assertNotEqual(new.json()["attempt_id"], old_id)
        self.assertEqual(self._attempt_field(old_id, "state"), "finalized")
        self.assertEqual(self._attempt_field(old_id, "final_outcome"), "disconnect")

    def test_result_of_a_finished_attempt(self):
        self._sign_in(self.client, "curious_player")
        attempt_id = self._start_as_page(self.client)
        base = f"/api/ranked/attempts/{attempt_id}"
        quit_result = self.client.post(f"{base}/quit").json()["result"]
        # history: readable from any page of the account, without the capability
        shown = self._second_tab().get(f"{base}/result")
        self.assertEqual(shown.status_code, 200, shown.text)
        self.assertEqual(shown.json(), quit_result)

    def test_result_of_an_abandoned_attempt_settles_it_first(self):
        self._sign_in(self.client, "late_player")
        attempt_id = self._start_as_page(self.client)
        self._abandon(attempt_id)
        shown = self.client.get(f"/api/ranked/attempts/{attempt_id}/result")
        self.assertEqual(shown.status_code, 200, shown.text)
        self.assertEqual(shown.json()["final_outcome"], "disconnect")
        self.assertEqual(self._attempt_field(attempt_id, "state"), "finalized")

    def test_result_of_a_running_attempt_is_a_conflict(self):
        self._sign_in(self.client, "impatient_player")
        attempt_id = self._start_as_page(self.client)
        shown = self.client.get(f"/api/ranked/attempts/{attempt_id}/result")
        self.assertEqual(shown.status_code, 409)
        self.assertEqual(self._attempt_field(attempt_id, "state"), "active")

    def test_result_requires_the_owner(self):
        self._sign_in(self.client, "result_owner")
        attempt_id = self._start_as_page(self.client)
        self.client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        anon = TestClient(create_app())
        self.assertEqual(
            anon.get(f"/api/ranked/attempts/{attempt_id}/result").status_code, 401
        )
        other = TestClient(create_app())
        self._sign_in(other, "result_other")
        self.assertEqual(
            other.get(f"/api/ranked/attempts/{attempt_id}/result").status_code, 404
        )

    def test_requires_authentication(self):
        anon = TestClient(create_app())
        self.assertEqual(anon.post("/api/ranked/attempts").status_code, 401)

    def test_cannot_touch_another_accounts_attempt(self):
        self._sign_in(self.client, "owner_player")
        attempt_id = self._start_as_page(self.client)
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
