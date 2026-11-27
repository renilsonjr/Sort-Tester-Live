"""Free text with a NUL character is refused as bad input, never a 500.

PostgreSQL cannot store U+0000 in text. A request carrying one used to reach
the database and come back as an unhandled error; it is now refused before
it gets there, and anything of the same kind that still reaches the
database is answered as a bad request.
"""
import unittest
from unittest import mock

import psycopg
from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.text_input import has_nul
from backend.tests.browser import BROWSER


class HasNulTests(unittest.TestCase):
    def test_finds_it_anywhere(self):
        for text in ("\x00", "a\x00", "\x00b", "a\x00b"):
            self.assertTrue(has_nul(text))

    def test_ordinary_text_is_fine(self):
        for text in ("", "plain", "emoji 😀", "accents ção", "<b>markup</b>", "tab\tand\nnewline"):
            self.assertFalse(has_nul(text))


class AnonymousRecoveryMessageTests(unittest.TestCase):
    def test_a_nul_in_a_recovery_message_is_refused_without_touching_the_database(self):
        client = TestClient(create_app(), headers=BROWSER, raise_server_exceptions=False)
        with mock.patch("backend.db.pool.checkout") as checkout:
            answer = client.post("/api/auth/recovery-messages", json={"message": "lost\x00code"})
        self.assertEqual(answer.status_code, 422)
        checkout.assert_not_called()


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SignedInTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        conn = migrate.connect(self.conninfo)
        self.addCleanup(conn.close)
        migrate.execute(conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'text-test')")
        conn.commit()
        self.client = TestClient(create_app(), headers=BROWSER, raise_server_exceptions=False)
        code = self.client.post("/api/auth/register", json={"username": "text_player"}).json()["login_id"]
        self.client.post("/api/auth/login", json={"username": "text_player", "login_id": code})
        started = self.client.post("/api/ranked/attempts").json()
        self.attempt = started["attempt_id"]
        self.client.headers["X-Attempt-Capability"] = started["capability"]

    def test_a_nul_in_a_support_request_is_refused(self):
        answer = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self.attempt, "description": "it\x00broke"},
        )
        self.assertEqual(answer.status_code, 422)

    def test_ordinary_text_still_goes_through(self):
        answer = self.client.post(
            "/api/ranked/support/tickets",
            json={"attempt_id": self.attempt, "description": "it broke <b>twice</b> 😀"},
        )
        self.assertIn(answer.status_code, (200, 201), answer.text)

    def test_bad_data_that_reaches_the_database_is_a_bad_request(self):
        error = psycopg.errors.CharacterNotInRepertoire("invalid byte sequence")
        with mock.patch("backend.support.tickets.open_ticket", side_effect=error):
            answer = self.client.post(
                "/api/ranked/support/tickets",
                json={"attempt_id": self.attempt, "description": "fine"},
            )
        self.assertEqual(answer.status_code, 400)
        self.assertEqual(answer.json(), {"detail": "Invalid input."})
        self.assertNotIn("byte sequence", answer.text)
        self.assertEqual(answer.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
