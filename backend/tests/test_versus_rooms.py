"""The Versus lobby: rooms open, fill, expire and close.

The first slice stores exactly one thing: the room. These tests hold the
lobby's rules -- one open room per host, a seat claimed once, expiry
judged at read time -- and its boundary: nothing of Ranked is touched.
"""
import unittest
from datetime import timedelta

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER
from backend.versus import rooms


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class VersusRoomsTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)

    def _player(self, username):
        client = TestClient(create_app(), headers=BROWSER)
        registration = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(registration.status_code, 200, registration.text)
        login_id = registration.json()["login_id"]
        self.assertEqual(
            client.post("/api/auth/login", json={"username": username, "login_id": login_id}).status_code,
            200,
        )
        return client

    def _one(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, sql, params)
        finally:
            conn.close()

    def _sql(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            migrate.execute(conn, sql, params)
            conn.commit()
        finally:
            conn.close()

    # -- opening a room ----------------------------------------------------

    def test_a_room_opens_with_a_code_and_waits(self):
        host = self._player("anahost")
        answer = host.post("/api/versus/rooms", json={"game": "quiz"})
        self.assertEqual(answer.status_code, 200, answer.text)
        room = answer.json()
        self.assertEqual(room["state"], "waiting")
        self.assertEqual(room["game"], "quiz")
        self.assertTrue(room["you_are_host"])
        self.assertIsNone(room["guest"])
        self.assertRegex(room["code"], r"^[A-Z]+-\d\d$")
        self.assertGreater(room["seconds_left"], 0)

    def test_an_unknown_game_is_refused(self):
        host = self._player("anahost")
        answer = host.post("/api/versus/rooms", json={"game": "chess"})
        self.assertEqual(answer.status_code, 400)

    def test_opening_a_second_room_closes_the_first(self):
        host = self._player("anahost")
        first = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        second = host.post("/api/versus/rooms", json={"game": "handler"}).json()
        self.assertNotEqual(first["id"], second["id"])
        gone = host.get(f"/api/versus/rooms/{first['id']}").json()
        self.assertEqual(gone["state"], "closed")
        self.assertEqual(host.get(f"/api/versus/rooms/{second['id']}").json()["state"], "waiting")

    def test_a_guest_cannot_open_or_watch_a_room(self):
        guest = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(guest.post("/api/versus/rooms", json={"game": "quiz"}).status_code, 401)

    # -- joining -----------------------------------------------------------

    def test_joining_by_code_fills_the_room_for_both(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "handler"}).json()
        joiner = self._player("beajoiner")
        answer = joiner.post("/api/versus/rooms/join", json={"code": room["code"]})
        self.assertEqual(answer.status_code, 200, answer.text)
        theirs = answer.json()
        self.assertEqual(theirs["state"], "full")
        self.assertFalse(theirs["you_are_host"])
        self.assertEqual(theirs["guest"]["username"], "beajoiner")
        mine = host.get(f"/api/versus/rooms/{room['id']}").json()
        self.assertEqual(mine["state"], "full")
        self.assertEqual(mine["guest"]["username"], "beajoiner")

    def test_a_code_is_joined_case_insensitively(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        joiner = self._player("beajoiner")
        answer = joiner.post("/api/versus/rooms/join", json={"code": room["code"].lower()})
        self.assertEqual(answer.status_code, 200, answer.text)

    def test_the_seat_is_claimed_only_once(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        first = self._player("beajoiner")
        self.assertEqual(first.post("/api/versus/rooms/join", json={"code": room["code"]}).status_code, 200)
        second = self._player("carlosthird")
        self.assertEqual(second.post("/api/versus/rooms/join", json={"code": room["code"]}).status_code, 404)

    def test_a_host_cannot_join_their_own_room(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        self.assertEqual(host.post("/api/versus/rooms/join", json={"code": room["code"]}).status_code, 404)

    def test_a_wrong_code_is_one_indistinguishable_404(self):
        joiner = self._player("beajoiner")
        answer = joiner.post("/api/versus/rooms/join", json={"code": "HAT-00"})
        self.assertEqual(answer.status_code, 404)

    # -- expiry and leaving ------------------------------------------------

    def test_an_expired_room_reads_as_closed_and_rejects_joiners(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        self._sql(
            "UPDATE versus_rooms SET expires_at = expires_at - %s WHERE id = %s",
            (rooms.ROOM_TTL + timedelta(seconds=1), room["id"]),
        )
        self.assertEqual(host.get(f"/api/versus/rooms/{room['id']}").json()["state"], "closed")
        joiner = self._player("beajoiner")
        self.assertEqual(joiner.post("/api/versus/rooms/join", json={"code": room["code"]}).status_code, 404)

    def test_the_host_leaving_closes_the_room(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        joiner = self._player("beajoiner")
        joiner.post("/api/versus/rooms/join", json={"code": room["code"]})
        self.assertEqual(host.post(f"/api/versus/rooms/{room['id']}/leave").status_code, 200)
        self.assertEqual(joiner.get(f"/api/versus/rooms/{room['id']}").json()["state"], "closed")

    def test_the_guest_leaving_reopens_the_seat(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        joiner = self._player("beajoiner")
        joined = joiner.post("/api/versus/rooms/join", json={"code": room["code"]}).json()
        self.assertEqual(joiner.post(f"/api/versus/rooms/{joined['id']}/leave").status_code, 200)
        mine = host.get(f"/api/versus/rooms/{room['id']}").json()
        self.assertEqual(mine["state"], "waiting")
        self.assertIsNone(mine["guest"])
        third = self._player("carlosthird")
        self.assertEqual(third.post("/api/versus/rooms/join", json={"code": room["code"]}).status_code, 200)

    def test_an_outsider_cannot_watch_a_room_by_id(self):
        host = self._player("anahost")
        room = host.post("/api/versus/rooms", json={"game": "quiz"}).json()
        outsider = self._player("carlosthird")
        self.assertEqual(outsider.get(f"/api/versus/rooms/{room['id']}").status_code, 404)

    def test_a_nonsense_room_id_is_a_404_not_an_error(self):
        host = self._player("anahost")
        self.assertEqual(host.get("/api/versus/rooms/not-a-uuid").status_code, 404)

    # -- the boundary ------------------------------------------------------

    def test_a_room_touches_nothing_of_ranked(self):
        host = self._player("anahost")
        host.post("/api/versus/rooms", json={"game": "quiz"})
        for table in ("attempts", "balances", "settlements"):
            self.assertEqual(self._one(f"SELECT COUNT(*) AS n FROM {table}")["n"], 0)


if __name__ == "__main__":
    unittest.main()
