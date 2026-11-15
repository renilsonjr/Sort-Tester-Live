"""Support tickets over HTTP (issue #26, slice 5)."""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

CAPABILITY_HEADER = "X-Attempt-Capability"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SupportRouterTests(unittest.TestCase):
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
        return res.json()

    def _ended_attempt(self, client):
        start = client.post("/api/ranked/attempts")
        self.assertEqual(start.status_code, 201, start.text)
        attempt_id = start.json()["attempt_id"]
        client.headers[CAPABILITY_HEADER] = start.json()["capability"]
        quit_res = client.post(f"/api/ranked/attempts/{attempt_id}/quit")
        self.assertEqual(quit_res.status_code, 200, quit_res.text)
        return attempt_id

    def _make_owner(self, username):
        conn = migrate.connect(self.conninfo)
        migrate.execute(
            conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = %s",
            (username,),
        )
        conn.commit()
        conn.close()

    def _other_player(self):
        client = TestClient(create_app(), headers=BROWSER)
        self._sign_in(client, "other_player")
        return client

    # --- a player's own tickets -------------------------------------------

    def test_signed_out_requests_are_refused(self):
        anonymous = TestClient(create_app(), headers=BROWSER)
        for call in (
            anonymous.get("/api/ranked/support/tickets"),
            anonymous.post("/api/ranked/support/tickets", json={"attempt_id": "x"}),
            anonymous.get("/api/ranked/support/review"),
        ):
            self.assertEqual(call.status_code, 401, call.text)

    def test_a_player_opens_and_reads_their_own_ticket(self):
        self._sign_in(self.client, "player_one")
        attempt_id = self._ended_attempt(self.client)
        created = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": attempt_id, "description": "It cut out."},
        )
        self.assertEqual(created.status_code, 201, created.text)
        body = created.json()
        self.assertEqual(body["attempt_id"], attempt_id)
        self.assertEqual(body["description"], "It cut out.")
        self.assertIsNone(body["closed_at"])

        listed = self.client.get("/api/ranked/support/tickets")
        self.assertEqual(listed.status_code, 200, listed.text)
        self.assertEqual([t["id"] for t in listed.json()], [body["id"]])

        one = self.client.get(f"/api/ranked/support/tickets/{body['id']}")
        self.assertEqual(one.status_code, 200, one.text)
        self.assertEqual(one.json()["id"], body["id"])

    def test_the_description_is_optional(self):
        self._sign_in(self.client, "player_one")
        created = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self._ended_attempt(self.client)},
        )
        self.assertEqual(created.status_code, 201, created.text)
        self.assertIsNone(created.json()["description"])

    def test_another_players_attempt_is_not_found(self):
        other = self._other_player()
        their_attempt = self._ended_attempt(other)
        self._sign_in(self.client, "player_one")
        created = self.client.post(
            "/api/ranked/support/tickets", json={"attempt_id": their_attempt}
        )
        self.assertEqual(created.status_code, 404, created.text)

    def test_an_attempt_that_does_not_exist_is_not_found(self):
        self._sign_in(self.client, "player_one")
        created = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": "00000000-0000-0000-0000-000000000000"},
        )
        self.assertEqual(created.status_code, 404, created.text)

    def test_a_second_request_about_one_attempt_is_a_conflict(self):
        self._sign_in(self.client, "player_one")
        attempt_id = self._ended_attempt(self.client)
        self.client.post("/api/ranked/support/tickets", json={"attempt_id": attempt_id})
        again = self.client.post(
            "/api/ranked/support/tickets", json={"attempt_id": attempt_id}
        )
        self.assertEqual(again.status_code, 409, again.text)

    def test_another_players_ticket_is_not_found(self):
        other = self._other_player()
        their_attempt = self._ended_attempt(other)
        theirs = other.post(
            "/api/ranked/support/tickets", json={"attempt_id": their_attempt}
        ).json()["id"]
        self._sign_in(self.client, "player_one")
        self.assertEqual(
            self.client.get(f"/api/ranked/support/tickets/{theirs}").status_code, 404
        )
        self.assertEqual(self.client.get("/api/ranked/support/tickets").json(), [])

    # --- review ------------------------------------------------------------

    def test_an_ordinary_player_cannot_reach_the_review_queue(self):
        self._sign_in(self.client, "player_one")
        self.assertEqual(self.client.get("/api/ranked/support/review").status_code, 403)

    def test_an_ordinary_player_cannot_close_or_reopen(self):
        self._sign_in(self.client, "player_one")
        attempt_id = self._ended_attempt(self.client)
        ticket = self.client.post(
            "/api/ranked/support/tickets", json={"attempt_id": attempt_id}
        ).json()["id"]
        closing = self.client.post(
            f"/api/ranked/support/review/{ticket}/close",
            json={"outcome": "network_instability"},
        )
        self.assertEqual(closing.status_code, 403, closing.text)
        self.assertEqual(
            self.client.post(f"/api/ranked/support/review/{ticket}/reopen").status_code,
            403,
        )

    def test_the_owner_reviews_closes_and_reopens(self):
        other = self._other_player()
        their_attempt = self._ended_attempt(other)
        ticket = other.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": their_attempt, "description": "It cut out."},
        ).json()["id"]

        self._sign_in(self.client, "the_owner")
        self._make_owner("the_owner")

        queue = self.client.get("/api/ranked/support/review")
        self.assertEqual(queue.status_code, 200, queue.text)
        self.assertEqual([row["id"] for row in queue.json()], [ticket])
        row = queue.json()[0]
        self.assertEqual(row["username"], "other_player")
        self.assertIn("events", row)

        closed = self.client.post(
            f"/api/ranked/support/review/{ticket}/close",
            json={"outcome": "insufficient_evidence"},
        )
        self.assertEqual(closed.status_code, 200, closed.text)
        self.assertEqual(closed.json()["outcome"], "insufficient_evidence")
        self.assertEqual(self.client.get("/api/ranked/support/review").json(), [])

        reopened = self.client.post(f"/api/ranked/support/review/{ticket}/reopen")
        self.assertEqual(reopened.status_code, 200, reopened.text)
        self.assertEqual(
            [row["id"] for row in self.client.get("/api/ranked/support/review").json()],
            [ticket],
        )

    def test_the_review_queue_returns_no_other_detail_about_the_player(self):
        other = self._other_player()
        other.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self._ended_attempt(other)},
        )
        self._sign_in(self.client, "the_owner")
        self._make_owner("the_owner")
        row = self.client.get("/api/ranked/support/review").json()[0]
        self.assertEqual(
            set(row),
            {"id", "attempt_id", "username", "tag", "description", "opened_at", "events"},
        )

    def test_an_unknown_outcome_is_refused(self):
        other = self._other_player()
        ticket = other.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self._ended_attempt(other)},
        ).json()["id"]
        self._sign_in(self.client, "the_owner")
        self._make_owner("the_owner")
        refused = self.client.post(
            f"/api/ranked/support/review/{ticket}/close", json={"outcome": "cheating"}
        )
        self.assertEqual(refused.status_code, 422, refused.text)

    # --- what the screens need --------------------------------------------

    def test_a_closed_ticket_carries_its_evidence_deletion_date(self):
        other = self._other_player()
        ticket = other.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self._ended_attempt(other)},
        ).json()["id"]
        self._sign_in(self.client, "the_owner")
        self._make_owner("the_owner")
        self.client.post(
            f"/api/ranked/support/review/{ticket}/close",
            json={"outcome": "network_instability"},
        )
        shown = other.get(f"/api/ranked/support/tickets/{ticket}").json()
        self.assertIsNotNone(shown["closed_at"])
        self.assertIsNotNone(shown["evidence_deleted_at"])
        self.assertFalse(shown["evidence_held_by_open_case"])

    def test_an_open_ticket_has_no_deletion_date(self):
        self._sign_in(self.client, "player_one")
        shown = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self._ended_attempt(self.client)},
        ).json()
        self.assertIsNone(shown["evidence_deleted_at"])
        self.assertFalse(shown["evidence_held_by_open_case"])

    def test_closure_changes_no_points(self):
        other = self._other_player()
        attempt_id = self._ended_attempt(other)
        ticket = other.post(
            "/api/ranked/support/tickets", json={"attempt_id": attempt_id}
        ).json()["id"]
        before = other.get("/api/ranked/season").json()
        self._sign_in(self.client, "the_owner")
        self._make_owner("the_owner")
        self.client.post(
            f"/api/ranked/support/review/{ticket}/close",
            json={"outcome": "insufficient_evidence"},
        )
        self.assertEqual(other.get("/api/ranked/season").json(), before)
