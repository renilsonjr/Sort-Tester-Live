"""Leaving a recovery message over HTTP (issue #251).

The rule is tested in test_auth_recovery_messages.py. Here: anybody may
call it, it says nothing back, and it cannot be used to flood the table.
"""
import unittest

from fastapi.testclient import TestClient

from backend.auth.rate_limit import RegistrationLimiter
from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER

URL = "/api/auth/recovery-messages"


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RecoveryMessageRouterTests(unittest.TestCase):
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
        self.app = create_app()
        self.anon = TestClient(self.app, headers=BROWSER)

    def _stored(self):
        self.conn.rollback()
        return [
            row["body"] for row in migrate.fetch_all(
                self.conn, "SELECT body FROM recovery_messages ORDER BY created_at"
            )
        ]

    def test_a_signed_out_visitor_can_leave_a_message(self):
        answer = self.anon.post(URL, json={"message": "  I lost my login ID  "})
        self.assertEqual(answer.status_code, 201, answer.text)
        self.assertEqual(answer.content, b"")
        self.assertEqual(self._stored(), ["I lost my login ID"])

    def test_the_answer_is_the_same_whether_or_not_an_account_is_named(self):
        self.anon.post("/api/auth/register", json={"username": "dock_owl"})
        real = self.anon.post(URL, json={"message": "I am dock_owl"})
        fake = self.anon.post(URL, json={"message": "I am nobody_here"})
        self.assertEqual((real.status_code, real.content), (fake.status_code, fake.content))
        self.assertEqual(real.headers.get("content-length"), fake.headers.get("content-length"))

    def test_empty_and_overlong_messages_are_refused(self):
        for body in ({"message": "   "}, {"message": "x" * 501}, {}):
            self.assertEqual(self.anon.post(URL, json=body).status_code, 422)
        self.assertEqual(self._stored(), [])

    def test_the_fourth_message_in_an_hour_from_one_address_is_refused(self):
        for n in range(3):
            self.assertEqual(self.anon.post(URL, json={"message": f"m{n}"}).status_code, 201)
        fourth = self.anon.post(URL, json={"message": "m3"})
        self.assertEqual(fourth.status_code, 429)
        self.assertEqual(len(self._stored()), 3)

    def test_refused_messages_do_not_use_up_the_allowance(self):
        for _ in range(5):
            self.anon.post(URL, json={"message": ""})
        self.assertEqual(self.anon.post(URL, json={"message": "real"}).status_code, 201)

    def test_the_daily_total_is_capped(self):
        self.app.state.recovery_message_limiter = RegistrationLimiter(
            per_client=100, per_client_window=3600.0, total=2, total_window=86400.0
        )
        self.assertEqual(self.anon.post(URL, json={"message": "a"}).status_code, 201)
        self.assertEqual(self.anon.post(URL, json={"message": "b"}).status_code, 201)
        self.assertEqual(self.anon.post(URL, json={"message": "c"}).status_code, 429)

    def test_a_full_inbox_refuses_and_stores_nothing(self):
        migrate.execute(
            self.conn,
            "INSERT INTO recovery_messages (body) SELECT 'filler' FROM generate_series(1, 100)",
        )
        self.conn.commit()
        self.assertEqual(self.anon.post(URL, json={"message": "one more"}).status_code, 429)
        self.assertNotIn("one more", self._stored())

    def test_a_write_without_an_origin_is_refused_like_any_other(self):
        bare = TestClient(self.app)
        self.assertEqual(bare.post(URL, json={"message": "hi"}).status_code, 403)
