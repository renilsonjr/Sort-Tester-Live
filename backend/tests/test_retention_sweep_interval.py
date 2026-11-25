"""Retention runs at most once a minute; the game's clock runs every time."""
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.main import create_app
from backend.routers import ranked as ranked_router
from backend.sweep_interval import RETENTION_INTERVAL_SECONDS, SweepInterval
from backend.tests.browser import BROWSER


class FakeClock:
    def __init__(self):
        self.now = 500.0

    def __call__(self):
        return self.now


class SweepIntervalTests(unittest.TestCase):
    def test_the_first_call_is_due(self):
        self.assertTrue(SweepInterval(clock=FakeClock()).due())

    def test_it_is_due_once_per_interval(self):
        clock = FakeClock()
        interval = SweepInterval(seconds=60, clock=clock)
        self.assertEqual([interval.due() for _ in range(4)], [True, False, False, False])
        clock.now += 59
        self.assertFalse(interval.due())
        clock.now += 1
        self.assertTrue(interval.due())
        self.assertFalse(interval.due())

    def test_reset_makes_it_due_again(self):
        interval = SweepInterval(clock=FakeClock())
        interval.due()
        interval.reset()
        self.assertTrue(interval.due())

    def test_retention_is_swept_once_a_minute(self):
        self.assertEqual(RETENTION_INTERVAL_SECONDS, 60.0)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class RequestSweepTests(unittest.TestCase):
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
        self.client = TestClient(self.app, headers=BROWSER)
        reg = self.client.post("/api/auth/register", json={"username": "sweep_player"})
        self.client.post("/api/auth/login", json={"username": "sweep_player", "login_id": reg.json()["login_id"]})

    def _spies(self):
        retention = mock.Mock(side_effect=ranked_router._sweep_retention)
        game = mock.Mock(side_effect=ranked_router.season_close.finish_due_seasons)
        for target, name, spy in (
            (ranked_router, "_sweep_retention", retention),
            (ranked_router.season_close, "finish_due_seasons", game),
        ):
            patcher = mock.patch.object(target, name, spy)
            patcher.start()
            self.addCleanup(patcher.stop)
        return retention, game

    def test_three_requests_sweep_retention_once_and_the_game_clock_each_time(self):
        retention, game = self._spies()
        for _ in range(3):
            self.assertEqual(self.client.get("/api/ranked/entry").status_code, 200)
        self.assertEqual(retention.call_count, 1)
        self.assertEqual(game.call_count, 3)

    def test_retention_runs_again_once_the_interval_has_passed(self):
        retention, _game = self._spies()
        self.client.get("/api/ranked/entry")
        self.client.get("/api/ranked/entry")
        self.assertEqual(retention.call_count, 1)
        self.app.state.retention_interval.reset()  # a minute later
        self.client.get("/api/ranked/entry")
        self.assertEqual(retention.call_count, 2)

    def test_what_retention_deletes_is_kept_even_when_the_route_only_reads(self):
        # an expired session row from long ago, nobody's any more
        account = migrate.fetch_one(
            self.conn, "SELECT id FROM accounts WHERE username_lower = 'sweep_player'"
        )["id"]
        migrate.execute(
            self.conn,
            "INSERT INTO sessions (account_id, token_hash, expires_at, last_seen_at, created_at)"
            " VALUES (%s, 'retention-test-hash', now() - interval '9 days',"
            " now() - interval '10 days', now() - interval '10 days')",
            (account,),
        )
        self.conn.commit()

        self.assertEqual(self.client.get("/api/ranked/entry").status_code, 200)

        left = migrate.fetch_one(
            self.conn,
            "SELECT count(*) AS n FROM sessions WHERE token_hash = 'retention-test-hash'",
        )
        self.assertEqual(left["n"], 0)


if __name__ == "__main__":
    unittest.main()
