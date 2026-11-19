"""Profile stats data module: best Ranked correct-count and place (#218).

The endpoint's exposure is tested in test_ranked_profile_stats_router.py;
here we pin the data rules against hand-built rows.
"""
import unittest

from backend.db import migrate, settings
from backend.ranked import profile_stats


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class _StatsBase(unittest.TestCase):
    _digest_counter = iter(f"{index:064x}" for index in range(1, 100000))

    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.reset_scratch_to_head(cls.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)
        self._n = 0

    # --- fixtures (minimal, mirroring test_db_attempts_answers_schema.py) ---

    def _account(self, username="player"):
        self._n += 1
        name = f"{username}{self._n}"
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (name, name.lower(), f"T{self._n:05d}"),
        )["id"]

    def _season(self, phase="pre_season", label=None):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES (%s, %s, now())"
            " RETURNING id",
            (phase, label or phase),
        )["id"]

    def _question_version(self):
        digest = next(self._digest_counter)
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
            " VALUES ('sort.basic', 'easy', %s) RETURNING id",
            (digest,),
        )["id"]

    def _settled_attempt(self, account_id, season_id, *, correct,
                         mode="normal", final_outcome="completed",
                         state="finalized", tiebreak_round=None):
        """A finalized attempt whose first `correct` of 15 answers are correct."""
        assignment_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, %s, %s) RETURNING id",
            (account_id, mode, season_id),
        )["id"]
        attempt_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
            " state, tiebreak_round, final_outcome, settled_at)"
            " VALUES (%s, %s, %s, %s, %s, %s, %s, now()) RETURNING id",
            (account_id, assignment_id, mode, season_id, state,
             tiebreak_round, final_outcome),
        )["id"]
        for seq in range(1, 16):
            outcome = "correct" if seq <= correct else "wrong"
            migrate.execute(
                self.conn,
                "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
                " first_sent_at, deadline_at, outcome)"
                " VALUES (%s, %s, %s, '2026-01-01T00:00:00Z',"
                " '2026-01-01T00:00:10Z', %s)",
                (attempt_id, seq, self._question_version(), outcome),
            )
        return attempt_id


class BestRankedTests(_StatsBase):
    def test_returns_best_correct_count_across_attempts(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=8)
        self._settled_attempt(acc, season, correct=13)
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, acc), 13)

    def test_none_when_no_settled_attempt(self):
        acc = self._account()
        self.assertIsNone(profile_stats.best_ranked_correct(self.conn, acc))

    def test_perfect_quiz_counts_all_fifteen(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=15)
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, acc), 15)

    def test_excludes_voids_and_tiebreaks(self):
        acc = self._account()
        season = self._season()
        # a wiped-at-launch attempt with a perfect score does not count
        self._settled_attempt(acc, season, correct=15, final_outcome="launch_reset")
        # nor does a tie-break, whose score stays hidden
        self._settled_attempt(acc, season, correct=14, mode="tiebreak",
                              tiebreak_round=1, final_outcome="completed")
        self.assertIsNone(profile_stats.best_ranked_correct(self.conn, acc))

    def test_includes_promotion_and_quit(self):
        acc = self._account()
        season = self._season()
        self._settled_attempt(acc, season, correct=15, mode="promotion")
        self._settled_attempt(acc, season, correct=6, final_outcome="quit")
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, acc), 15)

    def test_unfinalized_attempt_does_not_count(self):
        acc = self._account()
        season = self._season()
        # an ended-but-not-settled attempt is not a result yet
        self._settled_attempt(acc, season, correct=12, state="terminal_pending",
                              final_outcome="completed")
        self.assertIsNone(profile_stats.best_ranked_correct(self.conn, acc))

    def test_private_to_the_account(self):
        mine = self._account("mine")
        other = self._account("other")
        season = self._season()
        self._settled_attempt(other, season, correct=15)
        self._settled_attempt(mine, season, correct=9)
        self.assertEqual(profile_stats.best_ranked_correct(self.conn, mine), 9)


class LeaderboardPlaceTests(_StatsBase):
    def _official_season(self):
        season_id = migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES"
            " ('official', 'Peak Season', now()) RETURNING id",
        )["id"]
        return season_id

    def _make_eligible(self, account_id, season_id, points):
        self._n += 1
        migrate.execute(
            self.conn,
            "INSERT INTO participant_links (account_id, roster_reference)"
            " VALUES (%s, %s)",
            (account_id, f"twilight-{self._n}"),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)"
            " ON CONFLICT (account_id) DO UPDATE SET current_points = EXCLUDED.current_points",
            (account_id, points),
        )
        # standings only lists an account that has a finalized qualifying
        # attempt in the season (it must have played), so give it one
        self._settled_attempt(account_id, season_id, correct=0)

    def test_none_before_official_launch(self):
        acc = self._account()
        self.assertIsNone(profile_stats.leaderboard_place(self.conn, acc))

    def test_matches_standings_place_after_launch(self):
        season = self._official_season()
        top = self._account("top")
        second = self._account("second")
        self._make_eligible(top, season, 1420)
        self._make_eligible(second, season, 910)
        self.assertEqual(profile_stats.leaderboard_place(self.conn, top), 1)
        self.assertEqual(profile_stats.leaderboard_place(self.conn, second), 2)

    def test_none_for_an_ineligible_account(self):
        season = self._official_season()
        eligible = self._account("elig")
        self._make_eligible(eligible, season, 500)
        outsider = self._account("outsider")  # no participant link
        self.assertIsNone(profile_stats.leaderboard_place(self.conn, outsider))


if __name__ == "__main__":
    unittest.main()
