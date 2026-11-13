"""Thin HTTP layer over the ranked engine (issue #8, piece 4)."""
import unittest

from fastapi.testclient import TestClient

from backend.tests.browser import BROWSER

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
        tab = TestClient(create_app(), headers=BROWSER)
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
        self.client = TestClient(create_app(), headers=BROWSER)

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
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(
            anon.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 401
        )
        other = TestClient(create_app(), headers=BROWSER)
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
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(
            anon.post(f"/api/ranked/attempts/{attempt_id}/quit").status_code, 401
        )
        other = TestClient(create_app(), headers=BROWSER)
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
        anon = TestClient(create_app(), headers=BROWSER)
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
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(
            anon.get(f"/api/ranked/attempts/{attempt_id}/result").status_code, 401
        )
        other = TestClient(create_app(), headers=BROWSER)
        self._sign_in(other, "result_other")
        self.assertEqual(
            other.get(f"/api/ranked/attempts/{attempt_id}/result").status_code, 404
        )

    # --- official season launch (issue #23, slice 2) ---

    LAUNCH_URL = "/api/ranked/season/launch"
    LAUNCH_BODY = {
        "label": "Peak Season 2026",
        "confirm": "LAUNCH",
        "closes_at": "2099-12-31T23:59:00-05:00",
    }

    def _sign_in_owner(self, client, username):
        self._sign_in(client, username)
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = %s",
            (username.lower(),),
        )
        conn.commit()
        conn.close()

    def _official_seasons(self):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(
                conn, "SELECT COUNT(*) AS n FROM seasons WHERE phase = 'official'"
            )["n"]
        finally:
            conn.close()

    def test_launch_requires_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.post(self.LAUNCH_URL, json=self.LAUNCH_BODY).status_code, 401)
        self.assertEqual(self._official_seasons(), 0)

    def test_launch_requires_the_owner(self):
        self._sign_in(self.client, "ordinary_player")
        res = self.client.post(self.LAUNCH_URL, json=self.LAUNCH_BODY)
        self.assertEqual(res.status_code, 403)
        self.assertEqual(self._official_seasons(), 0)

    def test_launch_requires_the_exact_typed_confirmation(self):
        self._sign_in_owner(self.client, "careful_owner")
        for confirm in ("launch", "LAUNCH ", "yes", ""):
            with self.subTest(confirm=confirm):
                body = dict(self.LAUNCH_BODY, confirm=confirm)
                self.assertEqual(self.client.post(self.LAUNCH_URL, json=body).status_code, 422)
        no_confirm = {k: v for k, v in self.LAUNCH_BODY.items() if k != "confirm"}
        self.assertEqual(self.client.post(self.LAUNCH_URL, json=no_confirm).status_code, 422)
        self.assertEqual(self._official_seasons(), 0)

    def test_launch_refuses_a_bad_name_or_end_time(self):
        self._sign_in_owner(self.client, "strict_owner")
        bad_bodies = [
            dict(self.LAUNCH_BODY, label="   "),
            dict(self.LAUNCH_BODY, closes_at="2020-01-01T00:00:00-05:00"),  # in the past
            dict(self.LAUNCH_BODY, closes_at="2099-12-31T23:59:00"),        # no time zone
        ]
        for body in bad_bodies:
            with self.subTest(body=body):
                self.assertEqual(self.client.post(self.LAUNCH_URL, json=body).status_code, 422)
        self.assertEqual(self._official_seasons(), 0)

    def test_owner_launches_once(self):
        self._sign_in_owner(self.client, "launching_owner")
        self._set_points("launching_owner", 500)
        player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(player, "mid_quiz_player")
        attempt_id = self._start_as_page(player)

        res = self.client.post(self.LAUNCH_URL, json=self.LAUNCH_BODY)
        self.assertEqual(res.status_code, 201, res.text)
        body = res.json()
        self.assertEqual(body["label"], "Peak Season 2026")
        self.assertIn("season_id", body)
        self.assertTrue(body["closes_at"].startswith("2100-01-01T04:59:00"))  # stored in UTC
        self.assertEqual(self._official_seasons(), 1)
        # everyone is back at zero, and the quiz in progress is over
        self.assertEqual(self.client.get("/api/ranked/entry").json()["points"], 0)
        self.assertEqual(
            player.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 410
        )
        self.assertEqual(self._attempt_field(attempt_id, "final_outcome"), "launch_reset")

        again = self.client.post(self.LAUNCH_URL, json=self.LAUNCH_BODY)
        self.assertEqual(again.status_code, 409)
        self.assertEqual(self._official_seasons(), 1)

    # --- season close runs by itself (issue #23, slice 3) ---

    def _end_season(self, minutes_ago):
        """Make the test season's scheduled end ``minutes_ago`` minutes back."""
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE seasons SET opened_at = now() - interval '1 day',"
            " closes_at = now() - make_interval(mins => %s)",
            (minutes_ago,),
        )
        conn.commit()
        conn.close()

    def _season_frozen(self):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(
                conn, "SELECT frozen_at FROM seasons LIMIT 1"
            )["frozen_at"] is not None
        finally:
            conn.close()

    def test_request_after_the_window_finds_the_attempt_ended_and_scored(self):
        self._sign_in(self.client, "last_minute_player")
        attempt_id = self._start_as_page(self.client)
        self._end_season(minutes_ago=6)  # the five-minute window is over
        beat = self.client.post(f"/api/ranked/attempts/{attempt_id}/heartbeat")
        self.assertEqual(beat.status_code, 410)
        self.assertEqual(self._attempt_field(attempt_id, "state"), "finalized")
        self.assertEqual(self._attempt_field(attempt_id, "final_outcome"), "season_close")
        self.assertTrue(self._season_frozen())

    def test_any_ranked_request_after_the_window_freezes_the_season(self):
        self._sign_in(self.client, "morning_visitor")
        self._end_season(minutes_ago=6)
        self.assertFalse(self._season_frozen())
        self.assertEqual(self.client.get("/api/ranked/entry").status_code, 200)
        self.assertTrue(self._season_frozen())
        start = self.client.post("/api/ranked/attempts")
        self.assertEqual(start.status_code, 409)
        self.assertEqual(start.json()["detail"], "No open season")

    def test_inside_the_window_running_attempts_continue_and_starts_are_refused(self):
        self._sign_in(self.client, "finishing_player")
        attempt_id = self._start_as_page(self.client)
        self._end_season(minutes_ago=1)  # ended, but inside the five minutes
        beat = self.client.post(f"/api/ranked/attempts/{attempt_id}/heartbeat")
        self.assertEqual(beat.status_code, 204)
        self.assertFalse(self._season_frozen())
        late = TestClient(create_app(), headers=BROWSER)
        self._sign_in(late, "too_late_player")
        self.assertEqual(late.post("/api/ranked/attempts").status_code, 409)

    # --- account-private history (issue #23, slice 4) ---

    HISTORY_URL = "/api/ranked/history"

    def _quit_a_quiz(self, client):
        attempt_id = self._start_as_page(client)
        client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        return attempt_id

    def test_history_requires_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get(self.HISTORY_URL).status_code, 401)

    def test_history_lists_the_players_own_scored_quizzes(self):
        self._sign_in(self.client, "history_player")
        attempt_id = self._quit_a_quiz(self.client)
        other = TestClient(create_app(), headers=BROWSER)
        self._sign_in(other, "history_other")
        self._quit_a_quiz(other)

        entries = self.client.get(self.HISTORY_URL).json()
        self.assertEqual(len(entries), 1)  # never the other player's quiz
        entry = entries[0]
        self.assertEqual(entry["attempt_id"], attempt_id)
        self.assertEqual(
            (entry["phase"], entry["label"], entry["mode"], entry["final_outcome"]),
            ("pre_season", "test-season", "normal", "quit"),
        )
        self.assertEqual(
            (entry["raw_score"], entry["adjustment"], entry["points_before"],
             entry["points_after"], entry["badge_before"], entry["badge_after"]),
            (0, -10, 0, -10, "Iron", "Iron"),
        )
        self.assertIn("settled_at", entry)

    def test_history_keeps_pre_season_apart_and_marks_launch_ended_quizzes(self):
        self._sign_in(self.client, "veteran_player")
        self._quit_a_quiz(self.client)                 # a scored Pre-Season quiz
        mid = TestClient(create_app(), headers=BROWSER)
        self._sign_in(mid, "interrupted_player")
        self._start_as_page(mid)                       # still running at launch
        owner = TestClient(create_app(), headers=BROWSER)
        self._sign_in_owner(owner, "history_owner")
        self.assertEqual(owner.post(self.LAUNCH_URL, json=self.LAUNCH_BODY).status_code, 201)
        self._quit_a_quiz(self.client)                 # an official quiz

        everything = self.client.get(self.HISTORY_URL).json()
        self.assertEqual([e["phase"] for e in everything], ["official", "pre_season"])
        pre = self.client.get(self.HISTORY_URL, params={"phase": "pre_season"}).json()
        self.assertEqual([e["final_outcome"] for e in pre], ["quit"])
        official = self.client.get(self.HISTORY_URL, params={"phase": "official"}).json()
        self.assertEqual([e["label"] for e in official], ["Peak Season 2026"])

        ended_at_launch = mid.get(self.HISTORY_URL, params={"phase": "pre_season"}).json()
        self.assertEqual(len(ended_at_launch), 1)
        self.assertEqual(ended_at_launch[0]["final_outcome"], "launch_reset")
        self.assertEqual(ended_at_launch[0]["adjustment"], 0)

    def test_owner_has_no_exception_to_private_history(self):
        self._sign_in(self.client, "private_player")
        self._quit_a_quiz(self.client)
        player_id = self.client.get("/api/auth/me").json()["account_id"]
        owner = TestClient(create_app(), headers=BROWSER)
        self._sign_in_owner(owner, "nosy_owner")
        # naming another account changes nothing: history is the session's own
        seen = owner.get(self.HISTORY_URL, params={"account_id": player_id})
        self.assertEqual(seen.status_code, 200)
        self.assertEqual(seen.json(), [])

    def test_history_refuses_an_unknown_phase(self):
        self._sign_in(self.client, "typo_player")
        res = self.client.get(self.HISTORY_URL, params={"phase": "post_season"})
        self.assertEqual(res.status_code, 422)

    # --- season status (issue #23, slice 4) ---

    SEASON_URL = "/api/ranked/season"

    def test_season_status_requires_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get(self.SEASON_URL).status_code, 401)

    def test_season_status_of_the_pre_season(self):
        self._sign_in(self.client, "status_player")
        body = self.client.get(self.SEASON_URL).json()
        self.assertIn("season_id", body)
        self.assertEqual(
            {k: body[k] for k in ("phase", "label", "status", "closes_at", "points_final",
                                  "approvals_open")},
            {"phase": "pre_season", "label": "test-season", "status": "open",
             "closes_at": None, "points_final": False, "approvals_open": True},
        )

    def test_season_status_follows_launch_and_the_clock(self):
        self._sign_in_owner(self.client, "status_owner")
        self.assertEqual(
            self.client.post(self.LAUNCH_URL, json=self.LAUNCH_BODY).status_code, 201
        )
        body = self.client.get(self.SEASON_URL).json()
        self.assertEqual(
            (body["phase"], body["label"], body["status"], body["points_final"]),
            ("official", "Peak Season 2026", "open", False),
        )
        self.assertTrue(body["closes_at"].startswith("2100-01-01T04:59:00"))

    def _end_official_season(self, minutes_ago):
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE seasons SET opened_at = now() - interval '1 day',"
            " closes_at = now() - make_interval(mins => %s) WHERE frozen_at IS NULL",
            (minutes_ago,),
        )
        conn.commit()
        conn.close()

    def test_season_status_through_the_finishing_window_and_freeze(self):
        self._sign_in(self.client, "closing_player")
        self._end_official_season(minutes_ago=1)
        finishing = self.client.get(self.SEASON_URL).json()
        self.assertEqual((finishing["status"], finishing["points_final"]), ("finishing", False))
        self.assertFalse(finishing["approvals_open"])  # no new approvals in the window
        self._end_official_season(minutes_ago=6)
        frozen = self.client.get(self.SEASON_URL).json()
        self.assertEqual((frozen["status"], frozen["points_final"]), ("frozen", True))

    def test_season_status_with_no_season_is_not_found(self):
        self._sign_in(self.client, "early_player")
        conn = migrate.connect(self.conninfo)
        migrate.execute(conn, "DELETE FROM seasons")
        conn.commit()
        conn.close()
        self.assertEqual(self.client.get(self.SEASON_URL).status_code, 404)

    # --- connection flag review (issue #25, slice 3) ---

    FLAGS_URL = "/api/ranked/flags"

    def _flag_attempt(self, attempt_id):
        """Give an attempt a flag and four losses, as the engine would."""
        conn = migrate.connect(self.conninfo)
        for seconds in (3, 7, 11, 15):
            migrate.execute(
                conn,
                "INSERT INTO attempt_connection_events (attempt_id, kind, occurred_at)"
                " VALUES (%s, 'loss', now() - make_interval(secs => %s))",
                (attempt_id, 100 - seconds),
            )
        migrate.execute(
            conn,
            "INSERT INTO connection_flags (attempt_id, first_loss_at, last_loss_at, flagged_at)"
            " VALUES (%s, now() - interval '97 seconds', now() - interval '85 seconds', now())",
            (attempt_id,),
        )
        conn.commit()
        conn.close()

    def _flagged_player(self, username):
        player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(player, username)
        attempt_id = self._start_as_page(player)
        player.post(f"/api/ranked/attempts/{attempt_id}/quit")
        self._flag_attempt(attempt_id)
        return player, attempt_id

    def test_flags_require_a_session(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.get(self.FLAGS_URL).status_code, 401)

    def test_players_cannot_see_flags_not_even_their_own(self):
        player, attempt_id = self._flagged_player("flagged_player")
        self.assertEqual(player.get(self.FLAGS_URL).status_code, 403)
        self.assertEqual(
            player.post(f"{self.FLAGS_URL}/{attempt_id}/close",
                        json={"outcome": "network_instability"}).status_code,
            403,
        )

    def test_owner_lists_and_closes_a_flag(self):
        player, attempt_id = self._flagged_player("reviewed_player")
        self._sign_in_owner(self.client, "reviewing_owner")
        listed = self.client.get(self.FLAGS_URL)
        self.assertEqual(listed.status_code, 200, listed.text)
        entry = listed.json()[0]
        self.assertEqual(entry["attempt_id"], attempt_id)
        self.assertEqual(entry["username"], "reviewed_player")
        self.assertEqual(len(entry["events"]), 4)
        self.assertNotIn("email", entry)

        points_before = player.get("/api/ranked/entry").json()["points"]
        closed = self.client.post(
            f"{self.FLAGS_URL}/{attempt_id}/close", json={"outcome": "network_instability"}
        )
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json(), {"attempt_id": attempt_id,
                                         "outcome": "network_instability"})
        self.assertEqual(self.client.get(self.FLAGS_URL).json(), [])
        # closing changed nothing for the player
        self.assertEqual(player.get("/api/ranked/entry").json()["points"], points_before)
        self.assertEqual(player.post("/api/ranked/attempts").status_code, 201)

    def test_closing_refuses_an_unknown_outcome_or_missing_flag(self):
        _, attempt_id = self._flagged_player("odd_review_player")
        self._sign_in_owner(self.client, "strict_reviewer")
        self.assertEqual(
            self.client.post(f"{self.FLAGS_URL}/{attempt_id}/close",
                             json={"outcome": "cheating"}).status_code,
            422,
        )
        self.assertEqual(
            self.client.post(f"{self.FLAGS_URL}/00000000-0000-0000-0000-000000000000/close",
                             json={"outcome": "network_instability"}).status_code,
            404,
        )

    def test_a_second_tab_cannot_add_or_hide_connection_events(self):
        self._sign_in(self.client, "flapping_player")
        attempt_id = self._start_as_page(self.client)
        tab = self._second_tab()
        for _ in range(5):
            self.assertEqual(
                tab.post(f"/api/ranked/attempts/{attempt_id}/heartbeat").status_code, 403
            )
        conn = migrate.connect(self.conninfo)
        try:
            events = migrate.fetch_one(
                conn,
                "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id = %s",
                (attempt_id,),
            )["n"]
        finally:
            conn.close()
        self.assertEqual(events, 0)

    def test_old_closed_flags_are_cleaned_up_by_any_ranked_request(self):
        _, attempt_id = self._flagged_player("old_flag_player")
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE connection_flags SET closed_at = now() - interval '16 days',"
            " closed_outcome = 'insufficient_evidence' WHERE attempt_id = %s",
            (attempt_id,),
        )
        conn.commit()
        conn.close()
        self._sign_in(self.client, "passer_by")
        self.assertEqual(self.client.get("/api/ranked/entry").status_code, 200)
        conn = migrate.connect(self.conninfo)
        try:
            left = migrate.fetch_one(
                conn,
                "SELECT (SELECT COUNT(*) FROM connection_flags) AS flags,"
                " (SELECT COUNT(*) FROM attempt_connection_events WHERE attempt_id = %s) AS events",
                (attempt_id,),
            )
        finally:
            conn.close()
        self.assertEqual((left["flags"], left["events"]), (0, 0))

    def test_requires_authentication(self):
        anon = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(anon.post("/api/ranked/attempts").status_code, 401)

    def test_cannot_touch_another_accounts_attempt(self):
        self._sign_in(self.client, "owner_player")
        attempt_id = self._start_as_page(self.client)
        other = TestClient(create_app(), headers=BROWSER)
        self._sign_in(other, "other_player")
        res = other.get(f"/api/ranked/attempts/{attempt_id}/current")
        self.assertEqual(res.status_code, 404)

    def test_second_active_attempt_conflicts(self):
        self._sign_in(self.client, "busy_player")
        self.assertEqual(self.client.post("/api/ranked/attempts").status_code, 201)
        self.assertEqual(self.client.post("/api/ranked/attempts").status_code, 409)


if __name__ == "__main__":
    unittest.main()
