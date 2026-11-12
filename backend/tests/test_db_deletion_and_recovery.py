"""Deletion cascade/redaction and migration/restore/concurrency contract.

Issue #6 build/acceptance checks 5 and 6. All tests run against the live
scratch database and skip cleanly when ``SORT_TESTER_TEST_DATABASE_URL`` is
unset or malformed. No engine, API, or deletion flow is exercised here; these
prove the schema's deletion and recovery guarantees only.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
import uuid

from backend.db import migrate, settings


PROJECT_TABLES = (
    "accounts", "emails", "participant_links", "season_markers",
    "question_versions", "assignments", "assignment_questions",
    "attempts", "attempt_answers", "seasons", "settlements",
    "balances", "balance_history", "outbox", "login_credentials", "sessions",
)


class _SeedMixin:
    """Commit-based seeding helpers shared by the live-database tests.

    Rows are committed on ``self.setup`` because PostgreSQL foreign-key and
    cascade behaviour only sees committed rows; ``self.conn`` is a read-only
    verifier rolled back in teardown. Every committed account is purged at
    teardown so unique username/tag keys are reusable across tests.
    """

    def _seed_setup(self):
        self.conn = migrate.connect(self.conninfo)
        self.setup = migrate.connect(self.conninfo)
        self._committed_accounts = []
        self._committed_marker_refs = []
        self._counter = 0
        # purge runs on its own fresh connection (robust to tests that close or
        # recreate self.conn/self.setup); best-effort closes follow after it
        self.addCleanup(self._close_quietly, "conn")
        self.addCleanup(self._close_quietly, "setup")
        self.addCleanup(self._purge_committed)

    def _close_quietly(self, attr):
        conn = getattr(self, attr, None)
        if conn is None:
            return
        try:
            conn.close()
        except Exception:
            pass

    def _purge_committed(self):
        if not self._committed_accounts and not self._committed_marker_refs:
            return
        conn = migrate.connect(self.conninfo)
        try:
            if self._committed_accounts:
                migrate.execute(
                    conn, "DELETE FROM accounts WHERE id = ANY(%s)",
                    (self._committed_accounts,),
                )
            if self._committed_marker_refs:
                # season_markers have no account FK, so the account cascade
                # never reaches them; clean them up by their roster reference
                migrate.execute(
                    conn, "DELETE FROM season_markers WHERE roster_reference = ANY(%s)",
                    (self._committed_marker_refs,),
                )
            conn.commit()
        finally:
            conn.close()

    def _tag(self, prefix="DEL"):
        self._counter += 1
        return f"{prefix}{self._counter:03d}"

    def _make_account(self, tag):
        username = f"deltest_{tag.lower()}"
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO accounts (username, username_lower, tag)"
            " VALUES (%s, %s, %s) RETURNING id",
            (username, username, tag),
        )
        self._committed_accounts.append(row["id"])
        self.setup.commit()
        return row["id"]

    def _make_season(self):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO seasons (phase, label) VALUES ('pre_season', %s)"
            " RETURNING id",
            (f"del_{uuid.uuid4().hex}",),
        )
        self.setup.commit()
        return row["id"]

    def _make_question_version(self):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO question_versions (bank_key, difficulty, content_sha256)"
            " VALUES (%s, 'easy', %s) RETURNING id",
            (f"bank_{uuid.uuid4().hex}", uuid.uuid4().hex + uuid.uuid4().hex),
        )
        self.setup.commit()
        return row["id"]

    def _make_assignment(self, account_id, season_id, qv_id):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO assignments (account_id, mode, season_id)"
            " VALUES (%s, 'normal', %s) RETURNING id",
            (account_id, season_id),
        )
        assignment_id = row["id"]
        migrate.execute(
            self.setup,
            "INSERT INTO assignment_questions (assignment_id, seq, question_version_id)"
            " VALUES (%s, 1, %s)",
            (assignment_id, qv_id),
        )
        self.setup.commit()
        return assignment_id

    def _make_attempt(self, account_id, assignment_id, season_id, qv_id):
        # a finalized attempt so a settlement can attach (settlement requires a
        # terminal attempt) and the active-attempt lock does not block seeding
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO attempts (account_id, assignment_id, mode, state,"
            " season_id, final_outcome, settled_at)"
            " VALUES (%s, %s, 'normal', 'finalized', %s, 'quit', now())"
            " RETURNING id",
            (account_id, assignment_id, season_id),
        )
        attempt_id = row["id"]
        migrate.execute(
            self.setup,
            "INSERT INTO attempt_answers (attempt_id, seq, question_version_id,"
            " first_sent_at, deadline_at, outcome)"
            " VALUES (%s, 1, %s, now(), now() + interval '10 seconds', 'unsent')",
            (attempt_id, qv_id),
        )
        self.setup.commit()
        return attempt_id

    def _make_settlement(self, attempt_id, season_id):
        row = migrate.fetch_one(
            self.setup,
            "INSERT INTO settlements (attempt_id, season_id, raw_score, adjustment,"
            " final_outcome) VALUES (%s, %s, 0, 0, 'quit') RETURNING attempt_id",
            (attempt_id, season_id),
        )
        self.setup.commit()
        return row["attempt_id"]

    def _make_balance_and_history(self, account_id, settlement_id):
        migrate.execute(
            self.setup,
            "INSERT INTO balances (account_id, current_points) VALUES (%s, 0)",
            (account_id,),
        )
        migrate.execute(
            self.setup,
            "INSERT INTO balance_history (account_id, settlement_id, raw_score,"
            " adjustment, points_before, points_after, badge_before, badge_after)"
            " VALUES (%s, %s, 0, 0, 0, 0, 'Iron', 'Iron')",
            (account_id, settlement_id),
        )
        self.setup.commit()

    def _make_email(self, account_id):
        addr = f"{uuid.uuid4().hex}@example.test"
        migrate.execute(
            self.setup,
            "INSERT INTO emails (account_id, address, address_normalized, state)"
            " VALUES (%s, %s, %s, 'pending')",
            (account_id, addr, addr.lower()),
        )
        self.setup.commit()

    def _make_participant_link(self, account_id, roster_ref):
        migrate.execute(
            self.setup,
            "INSERT INTO participant_links (account_id, roster_reference)"
            " VALUES (%s, %s)",
            (account_id, roster_ref),
        )
        self.setup.commit()

    def _make_login_and_session(self, account_id):
        migrate.execute(
            self.setup,
            "INSERT INTO login_credentials (account_id, lookup_key, verifier)"
            " VALUES (%s, %s, 'argon2-verifier')",
            (account_id, uuid.uuid4().hex[:24]),
        )
        migrate.execute(
            self.setup,
            "INSERT INTO sessions (account_id, token_hash, expires_at)"
            " VALUES (%s, %s, now() + interval '1 hour')",
            (account_id, uuid.uuid4().bytes + uuid.uuid4().bytes),
        )
        self.setup.commit()

    def _make_season_marker(self, roster_ref):
        label = f"season_{uuid.uuid4().hex}"
        migrate.execute(
            self.setup,
            "INSERT INTO season_markers (roster_reference, season, ineligible)"
            " VALUES (%s, %s, true)",
            (roster_ref, label),
        )
        self._committed_marker_refs.append(roster_ref)
        self.setup.commit()

    def _seed_full_account(self, tag):
        """Seed one account with a row in every owned table plus its marker."""
        account_id = self._make_account(tag)
        roster_ref = f"roster-{tag}-{uuid.uuid4().hex[:8]}"
        season_id = self._make_season()
        qv_id = self._make_question_version()
        assignment_id = self._make_assignment(account_id, season_id, qv_id)
        attempt_id = self._make_attempt(account_id, assignment_id, season_id, qv_id)
        settlement_id = self._make_settlement(attempt_id, season_id)
        self._make_balance_and_history(account_id, settlement_id)
        self._make_email(account_id)
        self._make_participant_link(account_id, roster_ref)
        self._make_login_and_session(account_id)
        self._make_season_marker(roster_ref)
        return {
            "account_id": account_id,
            "roster_ref": roster_ref,
            "season_id": season_id,
            "qv_id": qv_id,
            "assignment_id": assignment_id,
            "attempt_id": attempt_id,
            "settlement_id": settlement_id,
        }

    def _count(self, sql_text, params):
        row = migrate.fetch_one(self.conn, sql_text, params)
        return row["n"]


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class DeletionCascadeTests(_SeedMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self._seed_setup()

    def test_account_delete_wipes_all_owned_rows(self):
        a = self._seed_full_account(self._tag())
        acc = a["account_id"]

        migrate.execute(self.setup, "DELETE FROM accounts WHERE id = %s", (acc,))
        self.setup.commit()

        # every account-owned table is empty for this account
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM accounts WHERE id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM emails WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM participant_links WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM login_credentials WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM sessions WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM balances WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM balance_history WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM assignments WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM attempts WHERE account_id=%s", (acc,)), 0)
        self.assertEqual(self._count(
            "SELECT COUNT(*) AS n FROM assignment_questions WHERE assignment_id=%s", (a["assignment_id"],)), 0)
        self.assertEqual(self._count(
            "SELECT COUNT(*) AS n FROM attempt_answers WHERE attempt_id=%s", (a["attempt_id"],)), 0)
        self.assertEqual(self._count(
            "SELECT COUNT(*) AS n FROM settlements WHERE attempt_id=%s", (a["settlement_id"],)), 0)

    def test_season_marker_survives_account_delete(self):
        a = self._seed_full_account(self._tag())
        migrate.execute(self.setup, "DELETE FROM accounts WHERE id = %s", (a["account_id"],))
        self.setup.commit()
        # the sole approved retention record remains
        self.assertEqual(self._count(
            "SELECT COUNT(*) AS n FROM season_markers WHERE roster_reference=%s",
            (a["roster_ref"],)), 1)

    def test_shared_content_and_other_account_untouched(self):
        a = self._seed_full_account(self._tag())
        b = self._seed_full_account(self._tag())
        migrate.execute(self.setup, "DELETE FROM accounts WHERE id = %s", (a["account_id"],))
        self.setup.commit()
        # account B is fully intact
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM accounts WHERE id=%s", (b["account_id"],)), 1)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM attempts WHERE account_id=%s", (b["account_id"],)), 1)
        # shared, non-personal content survives (not cascaded)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM question_versions WHERE id=%s", (a["qv_id"],)), 1)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM seasons WHERE id=%s", (a["season_id"],)), 1)

    def test_no_deleted_player_row_remains_anywhere(self):
        a = self._seed_full_account(self._tag())
        acc = a["account_id"]
        migrate.execute(self.setup, "DELETE FROM accounts WHERE id = %s", (acc,))
        self.setup.commit()
        # no owned table keeps a shadow row keyed to the gone account
        for table, col in (
            ("accounts", "id"), ("emails", "account_id"), ("balances", "account_id"),
            ("balance_history", "account_id"), ("assignments", "account_id"),
            ("attempts", "account_id"), ("sessions", "account_id"),
            ("login_credentials", "account_id"), ("participant_links", "account_id"),
        ):
            self.assertEqual(
                self._count(f"SELECT COUNT(*) AS n FROM {table} WHERE {col}=%s", (acc,)), 0,
                f"{table}.{col} kept a deleted-account shadow row",
            )

    # --- pending-purge state (migration 0013) ---

    def test_pending_purge_index_finds_only_marked_accounts(self):
        active = self._make_account(self._tag())
        pending = self._make_account(self._tag())
        migrate.execute(self.setup, "UPDATE accounts SET deleted_at = now() WHERE id=%s", (pending,))
        self.setup.commit()
        rows = migrate.fetch_all(
            self.conn,
            "SELECT id FROM accounts WHERE deleted_at IS NOT NULL AND id = ANY(%s)",
            ([active, pending],),
        )
        self.assertEqual([r["id"] for r in rows], [pending])
        # the row and its data persist while deletion is pending (purge unrun)
        self.assertEqual(self._count("SELECT COUNT(*) AS n FROM accounts WHERE id=%s", (pending,)), 1)

    def test_pending_purge_partial_index_exists(self):
        row = migrate.fetch_one(
            self.conn,
            "SELECT indexdef FROM pg_indexes WHERE indexname = 'accounts_pending_purge'",
            (),
        )
        self.assertIsNotNone(row, "accounts_pending_purge partial index is missing")
        self.assertIn("deleted_at", row["indexdef"].lower())

    def test_deleted_at_cannot_predate_created_at(self):
        acc = self._make_account(self._tag())
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(
                self.setup,
                "UPDATE accounts SET deleted_at = created_at - interval '1 day' WHERE id=%s",
                (acc,),
            )
        self.setup.rollback()


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class ConcurrencyConstraintTests(_SeedMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self._seed_setup()

    def test_settlement_applies_at_most_once(self):
        a = self._seed_full_account(self._tag())
        # the first settlement already exists from seeding; a second insert for
        # the same attempt hits the settlements primary key (the at-most-once key)
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(
                self.setup,
                "INSERT INTO settlements (attempt_id, season_id, raw_score, adjustment,"
                " final_outcome) VALUES (%s, %s, 0, 0, 'quit')",
                (a["attempt_id"], a["season_id"]),
            )
        self.setup.rollback()

    def test_only_one_active_attempt_per_account(self):
        acc = self._make_account(self._tag())
        season_id = self._make_season()
        qv_id = self._make_question_version()
        a1 = self._make_assignment(acc, season_id, qv_id)
        a2 = self._make_assignment(acc, season_id, qv_id)
        migrate.execute(
            self.setup,
            "INSERT INTO attempts (account_id, assignment_id, mode, state, season_id)"
            " VALUES (%s, %s, 'normal', 'active', %s)",
            (acc, a1, season_id),
        )
        self.setup.commit()
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(
                self.setup,
                "INSERT INTO attempts (account_id, assignment_id, mode, state, season_id)"
                " VALUES (%s, %s, 'normal', 'active', %s)",
                (acc, a2, season_id),
            )
        self.setup.rollback()

    def test_committed_rows_survive_reconnect(self):
        acc = self._make_account(self._tag())
        # close the writing connection entirely, then open a brand-new one
        self.setup.close()
        fresh = migrate.connect(self.conninfo)
        self.addCleanup(fresh.close)
        row = migrate.fetch_one(fresh, "SELECT id FROM accounts WHERE id=%s", (acc,))
        self.assertIsNotNone(row)
        # reopen setup so the teardown purge can run
        self.setup = migrate.connect(self.conninfo)


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class FullChainMigrationTests(unittest.TestCase):
    def setUp(self):
        try:
            self.conninfo = settings.test_database_url()
            self.admin = settings.admin_url()
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def test_full_chain_upgrade_creates_every_table(self):
        migrate.upgrade_to_head(self.conninfo)
        for table in PROJECT_TABLES:
            self.assertTrue(
                migrate.table_exists(self.conninfo, table),
                f"{table} missing after upgrade to head",
            )

    def test_full_chain_downgrade_removes_every_table(self):
        migrate.upgrade_to_head(self.conninfo)
        migrate.downgrade_all(self.conninfo)
        self.assertIsNone(migrate.current_revision(self.conninfo))
        for table in PROJECT_TABLES:
            self.assertFalse(
                migrate.table_exists(self.conninfo, table),
                f"{table} still present after downgrade to base",
            )


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class DumpRestoreTests(_SeedMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if shutil.which("pg_dump") is None or shutil.which("pg_restore") is None:
            raise unittest.SkipTest("pg_dump/pg_restore not on PATH; restore test skipped")
        try:
            cls.conninfo = settings.test_database_url()
            cls.admin = settings.admin_url()
            migrate.recreate_scratch_database(cls.admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        self._seed_setup()

    def test_dump_drop_restore_round_trip_preserves_data(self):
        a = self._seed_full_account(self._tag())
        before = {
            t: self._count(f"SELECT COUNT(*) AS n FROM {t}", ())
            for t in PROJECT_TABLES
        }
        # close every connection so DROP DATABASE WITH (FORCE) is clean
        self.conn.rollback()
        self.conn.close()
        self.setup.close()

        with tempfile.NamedTemporaryFile(suffix=".dump", delete=False) as fh:
            dump_path = fh.name
        try:
            subprocess.run(
                ["pg_dump", "--format=custom", "--dbname", self.conninfo, "--file", dump_path],
                check=True, capture_output=True, text=True,
            )
            migrate.recreate_scratch_database(self.admin, settings.SCRATCH_DB_NAME)
            subprocess.run(
                ["pg_restore", "--dbname", self.conninfo, dump_path],
                check=True, capture_output=True, text=True,
            )
        finally:
            os.unlink(dump_path)

        verify = migrate.connect(self.conninfo)
        try:
            after = {}
            for t in PROJECT_TABLES:
                r = migrate.fetch_one(verify, f"SELECT COUNT(*) AS n FROM {t}", ())
                after[t] = r["n"]
            marker = migrate.fetch_one(
                verify,
                "SELECT COUNT(*) AS n FROM season_markers WHERE roster_reference=%s",
                (a["roster_ref"],),
            )
        finally:
            verify.close()
        self.assertEqual(after, before, "row counts changed across dump/restore")
        self.assertEqual(marker["n"], 1, "season marker did not survive restore")
        # reopen the shared connections so _seed_setup teardown can purge
        self.conn = migrate.connect(self.conninfo)
        self.setup = migrate.connect(self.conninfo)


if __name__ == "__main__":
    unittest.main()
