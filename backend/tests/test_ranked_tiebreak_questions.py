"""The five shared questions of each tie-break round (issue #24, slice 2).

Run against the real pinned bank, so "ten fresh sets per season" is
measured here rather than assumed.
"""
import random
import unittest
from datetime import datetime, timedelta, timezone

from backend.db import migrate, settings
from backend.ranked import tiebreaks
from backend.ranked_bank.catalog import load_reviewed_bank

T0 = datetime(2026, 12, 31, 23, 59, tzinfo=timezone.utc)
BANK = load_reviewed_bank()


class Clock:
    def __init__(self, moment):
        self.moment = moment

    def now(self):
        return self.moment


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class TiebreakQuestionTests(unittest.TestCase):
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
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.season = self._season("Peak Season")
        self.group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'season_close', 700, 1, %s) RETURNING id",
            (self.season, T0),
        )["id"]
        self.conn.commit()
        self.rng = random.Random(7)
        self._round_no = 0

    def _season(self, label):
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at, closes_at)"
            " VALUES ('official', %s, %s, %s) RETURNING id",
            (label, T0 - timedelta(days=60), T0),
        )["id"]

    def _round(self, group=None, status="open"):
        self._round_no += 1
        number = ((self._round_no - 1) % 5) + 1
        if number == 1 and self._round_no > 1:
            # a fresh group per five rounds, since a group has at most five
            group = migrate.fetch_one(
                self.conn,
                "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
                " VALUES (%s, 'replacement', 600, 1, %s) RETURNING id",
                (self.season, T0),
            )["id"]
            self._current_group = group
        group = group or getattr(self, "_current_group", self.group)
        return migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at, status)"
            " VALUES (%s, %s, %s, %s, %s) RETURNING id",
            (group, number, T0, T0 + timedelta(hours=24), status),
        )["id"]

    def _assign(self, round_id, season=None):
        return tiebreaks.assign_round_questions(
            self.conn, round_id, season or self.season, BANK, rng=self.rng
        )

    def _round_questions(self, round_id):
        return migrate.fetch_all(
            self.conn,
            "SELECT seq, bank_key FROM tiebreak_round_questions WHERE round_id = %s ORDER BY seq",
            (round_id,),
        )

    # --- the pool ---

    def test_the_pool_is_the_53_approved_hard_questions(self):
        """Owner decision 2026-11-15: the regular bank's Hard questions."""
        pool = tiebreaks.fresh_questions(self.conn, self.season, BANK)
        self.assertEqual(len(pool), 53)
        self.assertTrue(all(q.difficulty.lower() == "hard" for q in pool))

    def test_a_season_has_ten_fresh_sets(self):
        self.assertEqual(tiebreaks.fresh_sets_left(self.conn, self.season, BANK), 10)

    # --- one round ---

    def test_a_round_gets_five_questions_numbered_one_to_five(self):
        round_id = self._round()
        self._assign(round_id)
        rows = self._round_questions(round_id)
        self.assertEqual([r["seq"] for r in rows], [1, 2, 3, 4, 5])
        self.assertEqual(len({r["bank_key"] for r in rows}), 5)

    def test_every_question_is_hard(self):
        round_id = self._round()
        chosen = self._assign(round_id)
        self.assertTrue(all(q.difficulty.lower() == "hard" for q in chosen))

    def test_the_questions_are_pinned_to_their_content(self):
        """A later bank revision cannot change a round already played."""
        round_id = self._round()
        self._assign(round_id)
        pinned = migrate.fetch_all(
            self.conn,
            "SELECT qv.content_sha256 FROM tiebreak_round_questions t"
            " JOIN question_versions qv ON qv.id = t.question_version_id"
            " WHERE t.round_id = %s",
            (round_id,),
        )
        self.assertEqual(len(pinned), 5)
        self.assertTrue(all(len(row["content_sha256"]) == 64 for row in pinned))

    # --- never reused ---

    def test_no_question_is_reused_across_ten_rounds(self):
        seen = set()
        for _ in range(10):
            round_id = self._round()
            self._assign(round_id)
            keys = {r["bank_key"] for r in self._round_questions(round_id)}
            self.assertFalse(keys & seen, "a question came back")
            seen |= keys
        self.assertEqual(len(seen), 50)

    def test_the_eleventh_round_has_no_fresh_set(self):
        for _ in range(10):
            self._assign(self._round())
        self.assertEqual(tiebreaks.fresh_sets_left(self.conn, self.season, BANK), 0)
        with self.assertRaises(tiebreaks.NoFreshSet):
            self._assign(self._round())

    def test_a_voided_rounds_questions_stay_used(self):
        """Its players saw them, so an outage restart gets fresh ones."""
        voided = self._round(status="void")
        self._assign(voided)
        used = {r["bank_key"] for r in self._round_questions(voided)}
        pool = {q.canonical_id for q in tiebreaks.fresh_questions(self.conn, self.season, BANK)}
        self.assertFalse(used & pool)

    def test_another_season_starts_with_all_53_again(self):
        """No reuse within a season; a new season is a new pool."""
        for _ in range(3):
            self._assign(self._round())
        other = self._season("Next Season")
        self.assertEqual(len(tiebreaks.fresh_questions(self.conn, other, BANK)), 53)

    def test_the_database_refuses_a_reused_question_even_if_the_code_slipped(self):
        first = self._round()
        self._assign(first)
        reused = self._round_questions(first)[0]["bank_key"]
        second = self._round()
        version = migrate.fetch_one(
            self.conn,
            "SELECT question_version_id FROM tiebreak_round_questions"
            " WHERE round_id = %s AND seq = 1",
            (first,),
        )["question_version_id"]
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(
                self.conn,
                "INSERT INTO tiebreak_round_questions"
                " (round_id, seq, question_version_id, season_id, bank_key)"
                " VALUES (%s, 1, %s, %s, %s)",
                (second, version, self.season, reused),
            )
        self.conn.rollback()

    def test_a_failed_assignment_writes_nothing(self):
        for _ in range(10):
            self._assign(self._round())
        self.conn.commit()
        doomed = self._round()
        with self.assertRaises(tiebreaks.NoFreshSet):
            self._assign(doomed)
        self.assertEqual(self._round_questions(doomed), [])

    # --- through the freeze ---

    def test_opening_a_tie_gives_round_one_its_questions(self):
        season = self._season("Freeze Season")
        self.conn.commit()
        self._tie_in(season)
        group = tiebreaks.open_prize_tiebreaks(
            self.conn, season, clock=Clock(T0 + timedelta(minutes=10)), bank=BANK, rng=self.rng
        )
        round_id = migrate.fetch_one(
            self.conn, "SELECT id FROM tiebreak_rounds WHERE group_id = %s", (group,)
        )["id"]
        self.assertEqual(len(self._round_questions(round_id)), 5)

    def test_with_no_fresh_set_left_the_group_waits_for_the_owner(self):
        """No round is opened that cannot be played."""
        season = self._season("Exhausted Season")
        self.conn.commit()
        exhausted_group = migrate.fetch_one(
            self.conn,
            "INSERT INTO tiebreak_groups (season_id, reason, tied_points, hats_available, opened_at)"
            " VALUES (%s, 'replacement', 100, 1, %s) RETURNING id",
            (season, T0),
        )["id"]
        for number in range(1, 11):
            rid = migrate.fetch_one(
                self.conn,
                "INSERT INTO tiebreak_rounds (group_id, round_number, opened_at, deadline_at, status)"
                " VALUES (%s, %s, %s, %s, 'void') RETURNING id",
                (exhausted_group, min(number, 5), T0, T0 + timedelta(hours=24)),
            )["id"]
            tiebreaks.assign_round_questions(self.conn, rid, season, BANK, rng=self.rng)
        self._tie_in(season)
        group = tiebreaks.open_prize_tiebreaks(
            self.conn, season, clock=Clock(T0 + timedelta(minutes=10)), bank=BANK, rng=self.rng
        )
        status = migrate.fetch_one(
            self.conn, "SELECT status FROM tiebreak_groups WHERE id = %s", (group,)
        )["status"]
        self.assertEqual(status, "owner_selection")
        self.assertEqual(
            migrate.fetch_all(
                self.conn, "SELECT id FROM tiebreak_rounds WHERE group_id = %s", (group,)
            ),
            [],
        )

    # --- helpers ---

    def _tie_in(self, season):
        """Four eligible players, the last two tied at third."""
        for i, points in enumerate((900, 800, 700, 700)):
            tag = f"Q{season.hex[:3].upper()}{i:02d}"[:6]
            account = migrate.fetch_one(
                self.conn,
                "INSERT INTO accounts (username, username_lower, tag)"
                " VALUES (%s, %s, %s) RETURNING id",
                (f"t_{tag.lower()}", f"t_{tag.lower()}", tag),
            )["id"]
            migrate.execute(
                self.conn,
                "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
                (account, points),
            )
            migrate.execute(
                self.conn,
                "INSERT INTO participant_links (account_id, roster_reference) VALUES (%s, %s)",
                (account, f"r-{tag}"),
            )
            assignment = migrate.fetch_one(
                self.conn,
                "INSERT INTO assignments (account_id, mode, season_id)"
                " VALUES (%s, 'normal', %s) RETURNING id",
                (account, season),
            )["id"]
            migrate.execute(
                self.conn,
                "INSERT INTO attempts (account_id, assignment_id, mode, season_id,"
                " state, final_outcome, settled_at)"
                " VALUES (%s, %s, 'normal', %s, 'finalized', 'completed', %s)",
                (account, assignment, season, T0),
            )
        self.conn.commit()


if __name__ == "__main__":
    unittest.main()
