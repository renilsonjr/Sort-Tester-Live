"""The Handler mini-game's stored best score (#396).

The first release stores exactly one thing: the best score per account per
mode. These tests hold that boundary as much as they hold the feature --
several of them exist to prove the mini-game does NOT reach anything else.
"""
import unittest

from fastapi.testclient import TestClient

from backend.db import migrate, settings
from backend.handler import best_scores
from backend.main import create_app
from backend.tests.browser import BROWSER


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class HandlerBestScoreTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.login_ids = {}
        migrate.reset_scratch_to_head(self.admin, settings.SCRATCH_DB_NAME)
        conn = migrate.connect(self.conninfo)
        migrate.execute(conn, "INSERT INTO seasons (phase, label) VALUES ('pre_season', 'Pre')")
        conn.commit()
        conn.close()

    def _player(self, username="handlerplayer"):
        client = TestClient(create_app(), headers=BROWSER)
        registration = client.post("/api/auth/register", json={"username": username})
        self.assertEqual(registration.status_code, 200, registration.text)
        login_id = registration.json()["login_id"]
        self.assertEqual(
            client.post("/api/auth/login", json={"username": username, "login_id": login_id}).status_code,
            200,
        )
        self.login_ids[username] = login_id
        return client, registration.json()["account_id"]

    def _sql(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            migrate.execute(conn, sql, params)
            conn.commit()
        finally:
            conn.close()

    def _one(self, sql, params=()):
        conn = migrate.connect(self.conninfo)
        try:
            return migrate.fetch_one(conn, sql, params)
        finally:
            conn.close()

    # -- what it stores ---------------------------------------------------

    def test_a_new_account_has_a_zero_in_every_mode(self):
        client, _ = self._player()
        answer = client.get("/api/handler/best")
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json()["best"], {"easy": 0, "medium": 0, "hard": 0, "expert": 0})

    def test_a_score_is_kept_and_only_ever_goes_up(self):
        client, _ = self._player()
        self.assertEqual(client.put("/api/handler/best", json={"mode": "hard", "score": 21}).json()["best"], 21)
        # A worse round does not overwrite a better one.
        self.assertEqual(client.put("/api/handler/best", json={"mode": "hard", "score": 8}).json()["best"], 21)
        self.assertEqual(client.put("/api/handler/best", json={"mode": "hard", "score": 34}).json()["best"], 34)
        self.assertEqual(client.get("/api/handler/best").json()["best"]["hard"], 34)

    def test_each_mode_keeps_its_own_score(self):
        # Rule 16's reason: a two-minute round in Easy is not a two-minute
        # round in Hard, so the four are never compared, merged or summed.
        client, _ = self._player()
        for mode, score in (("easy", 40), ("medium", 25), ("hard", 12), ("expert", 7)):
            client.put("/api/handler/best", json={"mode": mode, "score": score})
        self.assertEqual(
            client.get("/api/handler/best").json()["best"],
            {"easy": 40, "medium": 25, "hard": 12, "expert": 7},
        )

    def test_one_row_per_account_and_mode(self):
        client, account_id = self._player()
        for score in (5, 9, 2, 30):
            client.put("/api/handler/best", json={"mode": "easy", "score": score})
        row = self._one(
            "SELECT count(*) AS rows FROM handler_best_scores WHERE account_id = %s",
            (account_id,),
        )
        self.assertEqual(row["rows"], 1, "a round must not add a row; only the best is kept")

    # -- what it refuses --------------------------------------------------

    def test_a_guest_is_refused_rather_than_given_a_silent_zero(self):
        guest = TestClient(create_app(), headers=BROWSER)
        self.assertEqual(guest.get("/api/handler/best").status_code, 401)
        self.assertEqual(guest.put("/api/handler/best", json={"mode": "easy", "score": 3}).status_code, 401)

    def test_an_unknown_mode_is_refused(self):
        client, _ = self._player()
        answer = client.put("/api/handler/best", json={"mode": "nightmare", "score": 3})
        self.assertEqual(answer.status_code, 400, answer.text)
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], 0)

    def test_a_negative_or_absurd_score_is_refused(self):
        client, _ = self._player()
        self.assertEqual(client.put("/api/handler/best", json={"mode": "easy", "score": -1}).status_code, 422)
        self.assertEqual(
            client.put("/api/handler/best", json={"mode": "easy", "score": best_scores.SCORE_CEILING + 1}).status_code,
            422,
        )
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], 0)

    def test_one_account_cannot_read_or_raise_another_account_s_score(self):
        first, first_id = self._player("handlerone")
        second, _ = self._player("handlertwo")
        first.put("/api/handler/best", json={"mode": "hard", "score": 50})
        self.assertEqual(second.get("/api/handler/best").json()["best"]["hard"], 0)
        second.put("/api/handler/best", json={"mode": "hard", "score": 1})
        row = self._one("SELECT score FROM handler_best_scores WHERE account_id = %s AND mode = 'hard'", (first_id,))
        self.assertEqual(row["score"], 50)

    # -- the persistence boundary ----------------------------------------

    def test_playing_Handler_touches_nothing_else(self):
        """Mini-game results never reach Ranked points, prizes, badges, the
        leaderboard or the Shift log. This is the boundary the spec sets, and
        it is the reason this issue was rewritten, so it is asserted rather
        than assumed."""
        client, _ = self._player()
        # Every table a Ranked round would touch. If Handler ever starts
        # writing to one of these, this test says which.
        untouched = (
            "balances", "balance_history", "settlements", "attempts",
            "attempt_answers", "season_prizes", "assignments",
            "tiebreak_attempts", "tiebreak_placements",
        )
        before = {name: self._one(f"SELECT count(*) AS rows FROM {name}")["rows"] for name in untouched}
        for mode in best_scores.MODES:
            answer = client.put("/api/handler/best", json={"mode": mode, "score": 99})
            self.assertEqual(answer.status_code, 200, answer.text)
        after = {name: self._one(f"SELECT count(*) AS rows FROM {name}")["rows"] for name in untouched}
        self.assertEqual(before, after, "Handler reached a table the boundary keeps it out of")
        # And it did store the one thing it is allowed to store.
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], len(best_scores.MODES))

    def test_deleting_an_account_takes_its_scores_with_it(self):
        client, account_id = self._player()
        client.put("/api/handler/best", json={"mode": "easy", "score": 11})
        conn = migrate.connect(self.conninfo)
        migrate.execute(conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        conn.commit()
        conn.close()
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], 0)


    # -- a best score belongs to a season (#417) --------------------------

    def test_a_new_season_opens_with_every_best_at_zero_and_erases_nothing(self):
        client, _ = self._player()
        client.put("/api/handler/best", json={"mode": "easy", "score": 30})
        self._sql("UPDATE seasons SET closed_at = now()")
        self._sql("INSERT INTO seasons (phase, label) VALUES ('official', 'Season 1')")
        answer = client.get("/api/handler/best").json()
        self.assertEqual(answer["best"]["easy"], 0)
        self.assertTrue(answer["in_season"])
        # a lower score than last season's is this season's best
        raised = client.put("/api/handler/best", json={"mode": "easy", "score": 4}).json()
        self.assertEqual(raised, {"mode": "easy", "best": 4, "saved": True})
        rows = self._one("SELECT count(*) AS rows, max(score) AS top FROM handler_best_scores")
        self.assertEqual((rows["rows"], rows["top"]), (2, 30))

    def test_between_seasons_a_score_is_not_stored_and_the_answer_says_so(self):
        client, _ = self._player()
        self._sql("UPDATE seasons SET closed_at = now()")
        answer = client.put("/api/handler/best", json={"mode": "easy", "score": 9})
        self.assertEqual(answer.status_code, 200, answer.text)
        self.assertEqual(answer.json(), {"mode": "easy", "best": 0, "saved": False})
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], 0)
        read = client.get("/api/handler/best").json()
        self.assertFalse(read["in_season"])
        self.assertEqual(set(read["best"].values()), {0})

    def test_a_bad_score_is_still_refused_between_seasons(self):
        client, _ = self._player()
        self._sql("UPDATE seasons SET closed_at = now()")
        self.assertEqual(
            client.put("/api/handler/best", json={"mode": "nightmare", "score": 1}).status_code, 400
        )

    def test_an_account_that_deletes_itself_leaves_no_score_in_any_season(self):
        client, account_id = self._player()
        client.put("/api/handler/best", json={"mode": "easy", "score": 11})
        self._sql("UPDATE seasons SET closed_at = now()")
        self._sql("INSERT INTO seasons (phase, label) VALUES ('official', 'Season 1')")
        client.put("/api/handler/best", json={"mode": "hard", "score": 5})
        other, _ = self._player("bystander")
        other.put("/api/handler/best", json={"mode": "easy", "score": 2})
        gone = client.post(
            "/api/auth/account/delete",
            json={"login_id": self.login_ids["handlerplayer"], "acknowledge": True},
        )
        self.assertEqual(gone.status_code, 202, gone.text)
        # the account row is kept and only marked, so this is not the cascade
        self.assertIsNotNone(self._one("SELECT deleted_at FROM accounts WHERE id = %s", (account_id,))["deleted_at"])
        left = self._one("SELECT count(*) AS rows FROM handler_best_scores WHERE account_id = %s", (account_id,))
        self.assertEqual(left["rows"], 0)
        self.assertEqual(self._one("SELECT count(*) AS rows FROM handler_best_scores")["rows"], 1)

    def test_scores_stored_before_seasons_applied_move_to_the_newest_season(self):
        from alembic import command

        client, account_id = self._player()
        config = migrate._alembic_config(self.conninfo)
        try:
            command.downgrade(config, "0041")
            self._sql(
                "INSERT INTO handler_best_scores (account_id, mode, score) VALUES (%s, 'easy', 21)",
                (account_id,),
            )
            command.upgrade(config, "head")
        finally:
            config.attributes["connection"].dispose()
        self.assertEqual(client.get("/api/handler/best").json()["best"]["easy"], 21)


class HandlerBestScoreRulesTestCase(unittest.TestCase):
    """The rules that need no database."""

    def _migration(self):
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "migrations" / "versions" / "0041_handler_best_scores.py"
        spec = importlib.util.spec_from_file_location("handler_migration_0041", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_four_modes_match_the_migration(self):
        # The module checks the mode before the database does. If the two
        # lists drift, a mode passes here and is refused by the CHECK, which
        # is a 500 rather than a clear refusal.
        self.assertEqual(tuple(best_scores.MODES), tuple(self._migration().MODES))

    def test_the_migration_says_the_table_needs_a_grant(self):
        # A new table does not inherit the privileges of the ones beside it,
        # so the app would start and then fail on its first read. The
        # instruction belongs where whoever runs the migration will see it.
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "migrations" / "versions"
                / "0041_handler_best_scores.py").read_text(encoding="utf-8")
        self.assertIn("GRANT", text)
        self.assertIn("before the image", text)

    def test_a_score_is_refused_outside_the_module_too(self):
        for mode, score in (("nightmare", 1), ("easy", -1), ("easy", best_scores.SCORE_CEILING + 1), ("easy", True)):
            with self.subTest(mode=mode, score=score):
                with self.assertRaises(best_scores.ScoreRefused):
                    best_scores.record(object(), "account", "season", mode, score)

    def test_the_season_migration_says_the_role_needs_delete(self):
        # Deleting an account now runs a DELETE on this table as the app.
        # Without the privilege, account deletion itself would fail.
        from pathlib import Path

        text = (Path(__file__).resolve().parents[1] / "migrations" / "versions"
                / "0042_handler_scores_per_season.py").read_text(encoding="utf-8")
        self.assertIn("GRANT SELECT, INSERT, UPDATE, DELETE ON handler_best_scores", text)
        self.assertIn("then swap the image", text)
