"""Private connection review flags (issue #25, slice 2)."""
import tempfile
from datetime import datetime, timedelta, timezone
import unittest

from backend.db import migrate, settings
from backend.ranked import engine, flags, outages, scoring, settlement
from backend.tests.ranked_helpers import make_unconstrained_bank
from backend.tests.test_ranked_clock import FakeClock

T0 = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def at(seconds):
    return T0 + timedelta(seconds=seconds)


class FlagTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        try:
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(self.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.clock = FakeClock(T0)
        self.bank = make_unconstrained_bank(tempfile.mkdtemp())
        migrate.execute(
            self.conn,
            "INSERT INTO seasons (phase, label, opened_at) VALUES ('pre_season', 'Pre', %s)",
            (T0 - timedelta(days=1),),
        )
        self.conn.commit()
        self._accounts = 0

    def _account(self, points=500):
        self._accounts += 1
        tag = f"F{self._accounts:05d}"
        row = migrate.fetch_one(
            self.conn,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (f"flag_{tag.lower()}", f"flag_{tag.lower()}", tag),
        )
        migrate.execute(
            self.conn,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, %s)",
            (row["id"], points),
        )
        self.conn.commit()
        return row["id"]

    def _start(self, account_id):
        return engine.start_attempt(
            self.conn, account_id, clock=self.clock, bank=self.bank
        )

    def _flap(self, attempt_id, times):
        """Go silent and come back ``times`` times, four seconds apart.

        The engine declares each loss three seconds after the last heartbeat,
        so losses land at 3, 7, 11, ... seconds and returns at 4, 8, 12, ...
        """
        for _ in range(times):
            self.clock.advance(4)
            engine.heartbeat(self.conn, attempt_id, clock=self.clock)

    def _quit_and_settle(self, attempt_id):
        engine.quit_attempt(self.conn, attempt_id, clock=self.clock)
        return settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)

    def _flag(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT first_loss_at, last_loss_at FROM connection_flags WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return None if row is None else (row["first_loss_at"], row["last_loss_at"])

    def _flag_count(self):
        row = migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM connection_flags")
        self.conn.commit()
        return row["n"]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FlagCreationTests(FlagTestCase):
    def test_four_close_losses_create_one_flag(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)
        self._quit_and_settle(attempt_id)
        self.assertEqual(self._flag(attempt_id), (at(3), at(15)))

    def test_three_close_losses_create_no_flag(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 3)
        self._quit_and_settle(attempt_id)
        self.assertIsNone(self._flag(attempt_id))

    def test_a_steady_quiz_creates_no_flag(self):
        attempt_id = self._start(self._account())
        self._quit_and_settle(attempt_id)
        self.assertIsNone(self._flag(attempt_id))

    def test_a_flag_changes_nothing_else(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._flap(attempt_id, 4)
        result = self._quit_and_settle(attempt_id)
        self.assertIsNotNone(self._flag(attempt_id))

        answers = migrate.fetch_all(
            self.conn,
            "SELECT qv.difficulty, aa.answer FROM attempt_answers aa"
            " JOIN question_versions qv ON qv.id = aa.question_version_id"
            " WHERE aa.attempt_id = %s ORDER BY aa.seq",
            (attempt_id,),
        )
        expected = scoring.settle(
            500, "normal", "quit", [(r["difficulty"], r["answer"]) for r in answers]
        )
        self.assertEqual(result, expected)  # the flag added no deduction
        points = migrate.fetch_one(
            self.conn,
            "SELECT current_points FROM balances WHERE account_id = %s",
            (account_id,),
        )["current_points"]
        self.assertEqual(points, expected.points_after)
        self.conn.commit()
        # no restriction: the flagged player can play ranked again at once
        self.assertNotEqual(self._start(account_id), attempt_id)

    def test_settling_twice_keeps_one_flag(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)
        self._quit_and_settle(attempt_id)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertEqual(self._flag_count(), 1)

    def test_a_voided_quiz_is_never_flagged(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)
        engine.void_attempts_for_outage(
            self.conn, outage_start=self.clock.now(), outage_end=self.clock.now()
        )
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        self.assertIsNone(self._flag(attempt_id))

    def test_losses_inside_a_saved_outage_do_not_count(self):
        migrate.execute(
            self.conn,
            "INSERT INTO confirmed_outages (starts_at, ends_at) VALUES (%s, %s)",
            (at(6), at(8)),  # covers the loss at 7 and the return at 8
        )
        self.conn.commit()
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)  # losses at 3, 7, 11, 15
        self._quit_and_settle(attempt_id)
        self.assertIsNone(self._flag(attempt_id))  # 3, 11, 15: gap of 8 resets

    def test_flags_are_deleted_with_the_account(self):
        account_id = self._account()
        attempt_id = self._start(account_id)
        self._flap(attempt_id, 4)
        self._quit_and_settle(attempt_id)
        migrate.execute(self.conn, "DELETE FROM accounts WHERE id = %s", (account_id,))
        self.conn.commit()
        self.assertEqual(self._flag_count(), 0)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OutageRecordingTests(FlagTestCase):
    def _record(self, start, end):
        return outages.record_outage(
            self.conn, starts_at=start, ends_at=end, clock=self.clock
        )

    def _outage_count(self):
        row = migrate.fetch_one(self.conn, "SELECT COUNT(*) AS n FROM confirmed_outages")
        self.conn.commit()
        return row["n"]

    def _flagged_quiz(self, flaps=4):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, flaps)  # losses at 3, 7, 11, 15, ...
        self._quit_and_settle(attempt_id)
        self.assertIsNotNone(self._flag(attempt_id))
        return attempt_id

    def test_an_outage_that_explains_the_run_removes_the_flag(self):
        attempt_id = self._flagged_quiz()
        removed = self._record(at(6), at(8))  # the loss at 7 was the server's
        self.assertEqual(removed, 1)
        self.assertIsNone(self._flag(attempt_id))
        self.assertEqual(self._outage_count(), 1)

    def test_a_flag_the_outage_does_not_explain_comes_back(self):
        attempt_id = self._flagged_quiz(flaps=5)  # losses at 3, 7, 11, 15, 19
        removed = self._record(at(2), at(4))       # only the loss at 3
        self.assertEqual(removed, 0)
        # without that loss, 7, 11, 15, 19 still qualify on their own
        self.assertEqual(self._flag(attempt_id), (at(7), at(19)))

    def test_an_outage_elsewhere_leaves_flags_alone(self):
        attempt_id = self._flagged_quiz()
        self.assertEqual(self._record(at(100), at(110)), 0)
        self.assertEqual(self._flag(attempt_id), (at(3), at(15)))

    def test_an_outage_voids_and_settles_quizzes_it_interrupted(self):
        account_id = self._account(points=500)
        attempt_id = self._start(account_id)
        self._flap(attempt_id, 4)  # unstable, but the server was down
        self._record(at(0), self.clock.now())
        row = migrate.fetch_one(
            self.conn, "SELECT state, final_outcome FROM attempts WHERE id = %s",
            (attempt_id,),
        )
        points = migrate.fetch_one(
            self.conn, "SELECT current_points FROM balances WHERE account_id = %s",
            (account_id,),
        )["current_points"]
        self.conn.commit()
        self.assertEqual((row["state"], row["final_outcome"]), ("finalized", "outage_void"))
        self.assertEqual(points, 500)
        self.assertIsNone(self._flag(attempt_id))

    def test_an_outage_that_ends_before_it_starts_is_refused(self):
        with self.assertRaises(ValueError):
            self._record(at(10), at(5))
        self.conn.rollback()
        self.assertEqual(self._outage_count(), 0)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FlagReviewTests(FlagTestCase):
    def _flagged_quiz(self, flaps=4):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, flaps)
        self._quit_and_settle(attempt_id)
        return attempt_id

    def _closed(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT closed_at, closed_outcome FROM connection_flags WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return None if row is None else (row["closed_at"], row["closed_outcome"])

    def test_open_flags_list_only_the_review_evidence(self):
        attempt_id = self._flagged_quiz()
        listed = flags.open_flags(self.conn)
        self.assertEqual(len(listed), 1)
        entry = listed[0]
        self.assertEqual(
            set(entry),
            {"attempt_id", "username", "tag", "first_loss_at", "last_loss_at",
             "flagged_at", "events"},
        )
        self.assertEqual(entry["attempt_id"], attempt_id)
        self.assertEqual((entry["first_loss_at"], entry["last_loss_at"]), (at(3), at(15)))
        kinds = [event["kind"] for event in entry["events"]]
        self.assertEqual(kinds.count("loss"), 4)
        self.assertEqual(kinds.count("recovery"), 4)

    def test_closing_with_each_outcome(self):
        for outcome in ("network_instability", "insufficient_evidence"):
            with self.subTest(outcome=outcome):
                attempt_id = self._flagged_quiz()
                self.assertEqual(
                    flags.close_flag(self.conn, attempt_id, outcome, clock=self.clock),
                    outcome,
                )
                self.assertEqual(self._closed(attempt_id), (self.clock.now(), outcome))
        self.assertEqual(flags.open_flags(self.conn), [])  # closed flags leave the list

    def test_closing_twice_keeps_the_first_review(self):
        attempt_id = self._flagged_quiz()
        flags.close_flag(self.conn, attempt_id, "network_instability", clock=self.clock)
        first = self._closed(attempt_id)
        self.clock.advance(60)
        again = flags.close_flag(
            self.conn, attempt_id, "insufficient_evidence", clock=self.clock
        )
        self.assertEqual(again, "network_instability")
        self.assertEqual(self._closed(attempt_id), first)

    def test_closing_refuses_an_unknown_outcome_or_missing_flag(self):
        attempt_id = self._flagged_quiz()
        with self.assertRaises(ValueError):
            flags.close_flag(self.conn, attempt_id, "cheating", clock=self.clock)
        self.conn.rollback()
        unflagged = self._start(self._account())
        with self.assertRaises(flags.FlagNotFoundError):
            flags.close_flag(self.conn, unflagged, "network_instability", clock=self.clock)
        self.conn.rollback()
        self.assertEqual(self._closed(attempt_id), (None, None))

    def test_a_closed_flag_the_outage_does_not_explain_keeps_its_review(self):
        attempt_id = self._flagged_quiz(flaps=5)  # losses at 3..19
        flags.close_flag(self.conn, attempt_id, "network_instability", clock=self.clock)
        reviewed = self._closed(attempt_id)
        outages.record_outage(self.conn, starts_at=at(2), ends_at=at(4), clock=self.clock)
        self.assertEqual(self._closed(attempt_id), reviewed)
        # untouched: still the first qualifying run recorded at scoring time
        self.assertEqual(self._flag(attempt_id), (at(3), at(15)))

    def test_a_closed_flag_the_outage_explains_is_removed(self):
        attempt_id = self._flagged_quiz()
        flags.close_flag(self.conn, attempt_id, "insufficient_evidence", clock=self.clock)
        removed = outages.record_outage(
            self.conn, starts_at=at(6), ends_at=at(8), clock=self.clock
        )
        self.assertEqual(removed, 1)
        self.assertIsNone(self._flag(attempt_id))


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FlagRetentionTests(FlagTestCase):
    def _closed_flag(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)
        self._quit_and_settle(attempt_id)
        flags.close_flag(self.conn, attempt_id, "network_instability", clock=self.clock)
        return attempt_id

    def _event_count(self, attempt_id):
        row = migrate.fetch_one(
            self.conn,
            "SELECT COUNT(*) AS n FROM attempt_connection_events WHERE attempt_id = %s",
            (attempt_id,),
        )
        self.conn.commit()
        return row["n"]

    def _purge(self):
        return flags.purge_closed_flags(self.conn, clock=self.clock)

    def test_a_closed_flag_is_kept_for_fourteen_days(self):
        attempt_id = self._closed_flag()
        self.clock.advance(timedelta(days=15).total_seconds() - 1)
        self.assertEqual(self._purge(), 0)
        self.assertIsNotNone(self._flag(attempt_id))
        self.assertEqual(self._event_count(attempt_id), 8)

    def test_a_closed_flag_and_its_events_go_after_fifteen_days(self):
        attempt_id = self._closed_flag()
        self.clock.advance(timedelta(days=15).total_seconds())
        self.assertEqual(self._purge(), 1)
        self.assertIsNone(self._flag(attempt_id))
        self.assertEqual(self._event_count(attempt_id), 0)
        # seasonal scores and quiz history remain
        kept = migrate.fetch_one(
            self.conn,
            "SELECT (SELECT COUNT(*) FROM attempts WHERE id = %(a)s) AS attempts,"
            " (SELECT COUNT(*) FROM attempt_answers WHERE attempt_id = %(a)s) AS answers,"
            " (SELECT COUNT(*) FROM settlements WHERE attempt_id = %(a)s) AS settlements,"
            " (SELECT COUNT(*) FROM balance_history WHERE settlement_id = %(a)s) AS history",
            {"a": attempt_id},
        )
        self.conn.commit()
        self.assertEqual(
            (kept["attempts"], kept["answers"], kept["settlements"], kept["history"]),
            (1, 1, 1, 1),
        )
        self.assertEqual(self._purge(), 0)  # nothing left to do

    def test_an_open_flag_is_never_purged(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)
        self._quit_and_settle(attempt_id)
        self.clock.advance(timedelta(days=60).total_seconds())
        self.assertEqual(self._purge(), 0)
        self.assertIsNotNone(self._flag(attempt_id))

    def test_unflagged_attempts_keep_their_events(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 2)
        self._quit_and_settle(attempt_id)
        self.clock.advance(timedelta(days=60).total_seconds())
        self._purge()
        self.assertEqual(self._event_count(attempt_id), 4)

    # --- races ---

    def test_grace_expiry_in_the_middle_of_unstable_play_still_flags(self):
        attempt_id = self._start(self._account())
        self._flap(attempt_id, 4)  # losses at 3, 7, 11, 15
        self.clock.advance(30)     # then the connection never comes back
        engine.expire_stale_attempts(self.conn, clock=self.clock)
        settlement.settle_attempt(self.conn, attempt_id, clock=self.clock)
        row = migrate.fetch_one(
            self.conn, "SELECT final_outcome FROM attempts WHERE id = %s", (attempt_id,)
        )
        self.conn.commit()
        self.assertEqual(row["final_outcome"], "disconnect")
        self.assertEqual(self._flag(attempt_id), (at(3), at(15)))


if __name__ == "__main__":
    unittest.main()
