"""The public season notice, and what it is allowed to do (audit M-1).

Anyone can call this endpoint: it is what a guest's home page reads to
know whether the official season has started. It shared `get_db` with
the authenticated routes, and `get_db` runs the whole sweep chain --
closing due seasons, closing tie-break rounds, finalizing prizes,
purging retention -- taking database locks each time.

So anonymous traffic drove the locks the players' own quizzes need. A
flood of an endpoint that needs no account could stall the ranked path.
The notice reads; it must not sweep.
"""
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.tests.browser import BROWSER


class Swept(Exception):
    """Raised by a stubbed sweep, so a sweep cannot pass unnoticed."""


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class SeasonNoticeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.client = TestClient(create_app(), headers=BROWSER)

    def _refuse_every_sweep(self):
        """Make every sweep the chain runs explode if it is reached."""
        def boom(*args, **kwargs):
            raise Swept("a public request ran a sweep")

        for target in (
            "backend.routers.ranked.season_close.finish_due_seasons",
            "backend.routers.ranked.ranked_tiebreaks.close_due_rounds",
            "backend.routers.ranked.ranked_tiebreaks.finalize_prizes",
            "backend.routers.ranked.support_retention.purge_due_cases",
            "backend.routers.ranked.purge_deleted_accounts",
        ):
            patch = mock.patch(target, side_effect=boom)
            patch.start()
            self.addCleanup(patch.stop)

    def test_the_notice_answers_without_running_a_single_sweep(self):
        self._refuse_every_sweep()

        response = self.client.get("/api/ranked/season/notice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            set(response.json()),
            {"started", "label", "started_at", "closes_at"},
        )

    def test_before_a_launch_it_says_so_and_invents_no_dates(self):
        self._refuse_every_sweep()

        body = self.client.get("/api/ranked/season/notice").json()

        self.assertFalse(body["started"])
        self.assertIsNone(body["label"])
        self.assertIsNone(body["started_at"])
        self.assertIsNone(body["closes_at"])

    def test_it_still_needs_no_account(self):
        self._refuse_every_sweep()
        self.assertNotIn("sort_tester_session", self.client.cookies)

        self.assertEqual(
            self.client.get("/api/ranked/season/notice").status_code, 200
        )

    def test_an_authenticated_ranked_route_does_still_sweep(self):
        # the sweeps are how a season closes at all -- no background timer
        # runs them -- so taking them off the public path must not take
        # them off the path that has an account behind it. Sign in first:
        # an anonymous call is refused before the connection is opened.
        login_id = self.client.post(
            "/api/auth/register", json={"username": "notice_user"}
        ).json()["login_id"]
        self.client.post("/api/auth/login", json={"login_id": login_id})
        self._refuse_every_sweep()

        with self.assertRaises(Swept):
            self.client.get("/api/ranked/season")


if __name__ == "__main__":
    unittest.main()
