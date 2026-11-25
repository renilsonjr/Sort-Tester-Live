"""The owner's recovery-message inbox over HTTP (issue #251)."""
import unittest
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

LIST = "/api/ranked/owner/recovery-messages"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OwnerRecoveryMessageTests(unittest.TestCase):
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
        # Deliberately no /api/auth/reauthenticate call: these routes must
        # work on an ordinary owner session.
        self.owner = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.owner, "the_owner")
        migrate.execute(
            self.conn,
            "UPDATE accounts SET is_owner = true WHERE username_lower = 'the_owner'",
        )
        self.conn.commit()
        self.player = TestClient(create_app(), headers=BROWSER)
        self._sign_in(self.player, "dock_owl")
        self.anon = TestClient(create_app(), headers=BROWSER)

    def _sign_in(self, client, username):
        reg = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(reg.status_code, 200, reg.text)
        login = client.post("/api/auth/login", json={"username": username, "login_id": reg.json()["login_id"]})
        self.assertEqual(login.status_code, 200, login.text)

    def _leave(self, text):
        answer = self.anon.post("/api/auth/recovery-messages", json={"message": text})
        self.assertEqual(answer.status_code, 201, answer.text)

    def _resolve(self, client, message_id):
        return client.post(f"{LIST}/{message_id}/resolve")

    def test_a_signed_out_visitor_is_refused(self):
        self.assertEqual(self.anon.get(LIST).status_code, 401)
        self.assertEqual(self._resolve(self.anon, uuid4()).status_code, 401)

    def test_a_player_is_refused(self):
        self.assertEqual(self.player.get(LIST).status_code, 403)
        self.assertEqual(self._resolve(self.player, uuid4()).status_code, 403)

    def test_the_owner_reads_messages_without_reauthenticating(self):
        self._leave("first")
        self._leave("<b>second</b>")
        answer = self.owner.get(LIST)
        self.assertEqual(answer.status_code, 200, answer.text)
        body = answer.json()
        self.assertEqual(body["open"], 2)
        self.assertEqual(
            sorted(m["body"] for m in body["messages"]), ["<b>second</b>", "first"]
        )
        for message in body["messages"]:
            self.assertEqual(set(message), {"id", "body", "created_at", "resolved_at"})
            self.assertIsNone(message["resolved_at"])

    def test_resolving_marks_it_and_is_idempotent(self):
        self._leave("help")
        message_id = self.owner.get(LIST).json()["messages"][0]["id"]
        self.assertEqual(self._resolve(self.owner, message_id).status_code, 204)
        self.assertEqual(self._resolve(self.owner, message_id).status_code, 204)
        body = self.owner.get(LIST).json()
        self.assertEqual(body["open"], 0)
        self.assertIsNotNone(body["messages"][0]["resolved_at"])

    def test_an_unknown_or_malformed_id_is_not_found(self):
        self.assertEqual(self._resolve(self.owner, uuid4()).status_code, 404)
        self.assertEqual(self._resolve(self.owner, "not-a-uuid").status_code, 404)

    def test_a_message_resolved_long_ago_is_gone_from_the_inbox(self):
        self._leave("resolved long ago")
        self._leave("resolved just now")
        migrate.execute(
            self.conn,
            "UPDATE recovery_messages SET created_at = now() - interval '40 days',"
            " resolved_at = now() - interval '31 days'"
            " WHERE body = 'resolved long ago'",
        )
        migrate.execute(
            self.conn,
            "UPDATE recovery_messages SET resolved_at = now()"
            " WHERE body = 'resolved just now'",
        )
        self.conn.commit()

        bodies = [m["body"] for m in self.owner.get(LIST).json()["messages"]]

        self.assertEqual(bodies, ["resolved just now"])
        left = migrate.fetch_one(self.conn, "SELECT count(*) AS n FROM recovery_messages")
        self.assertEqual(left["n"], 1)

