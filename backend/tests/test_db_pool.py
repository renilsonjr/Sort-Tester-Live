"""Pooled connections for the request path (audit M-5).

Every request used to open its own connection to Postgres and close it
again. Opening a connection there is not cheap, and nothing capped how
many a burst could ask for: the database's own limit was the only brake,
and reaching it refuses connections to everyone, not only to the burst.

A pool reuses a fixed set and makes the rest wait. The statement timeout
is the other half: without it one stuck query holds a pooled connection
for as long as the query lives, and eight of those are the whole pool.

What these tests pin down is mostly the ways a pool goes wrong quietly --
a connection handed out still inside someone else's transaction, a commit
nobody asked for, a timeout that was configured but never reached the
session.
"""
import unittest

import psycopg

from backend.db import migrate, pool, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class PoolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            admin = settings.admin_url()
            migrate.recreate_scratch_database(admin, settings.SCRATCH_DB_NAME)
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        pool.close_pool()
        pool.init_pool(self.conninfo)
        self.addCleanup(pool.close_pool)

    def test_a_released_connection_is_handed_out_again(self):
        # the point of the whole thing: without a pool these are two
        # different objects, because each one opened its own connection
        with pool.checkout() as first:
            first_id = id(first)
        with pool.checkout() as second:
            self.assertEqual(id(second), first_id)

    def test_init_pool_twice_does_not_build_a_second_pool(self):
        # it is called from app startup and defensively from checkout, so
        # a second call must be a no-op rather than another eight
        # connections nobody tracks
        before = pool.current_pool()
        pool.init_pool(self.conninfo)
        self.assertIs(pool.current_pool(), before)

    def test_the_pool_is_capped(self):
        self.assertEqual(pool.current_pool().max_size, pool.MAX_SIZE)
        self.assertLessEqual(pool.MAX_SIZE, 8)

    def test_a_statement_timeout_is_in_force_on_a_pooled_connection(self):
        # configured is not the same as applied: this asks the session
        # itself what it will enforce
        with pool.checkout() as conn:
            row = migrate.fetch_one(conn, "SHOW statement_timeout")
            self.assertEqual(row["statement_timeout"], "5s")

    def test_a_clean_exit_does_not_commit_on_its_own(self):
        # owner decision 2026-11-17, against the plan's first sketch:
        # writes stay explicit. psycopg_pool's own `connection()` helper
        # commits here, which is why this code does not use it.
        with pool.checkout() as conn:
            migrate.execute(
                conn,
                "INSERT INTO accounts (username, username_lower, tag)"
                " VALUES ('pooltest', 'pooltest', 'POOLA1')",
            )
        with pool.checkout() as conn:
            row = migrate.fetch_one(
                conn,
                "SELECT count(*) AS n FROM accounts WHERE username = 'pooltest'",
            )
            self.assertEqual(row["n"], 0, "an uncommitted write must not survive")

    def test_an_explicit_commit_still_persists(self):
        with pool.checkout() as conn:
            migrate.execute(
                conn,
                "INSERT INTO accounts (username, username_lower, tag)"
                " VALUES ('poolkeep', 'poolkeep', 'POOLB2')",
            )
            conn.commit()
        try:
            with pool.checkout() as conn:
                row = migrate.fetch_one(
                    conn,
                    "SELECT count(*) AS n FROM accounts WHERE username = 'poolkeep'",
                )
                self.assertEqual(row["n"], 1)
        finally:
            with pool.checkout() as conn:
                migrate.execute(
                    conn, "DELETE FROM accounts WHERE username = 'poolkeep'"
                )
                conn.commit()

    def test_a_failure_leaves_no_transaction_on_the_returned_connection(self):
        # the quiet disaster: a connection goes back to the pool still
        # inside an aborted transaction, and the next request to borrow it
        # fails on a statement that has nothing wrong with it
        class Boom(Exception):
            pass

        with self.assertRaises(Boom):
            with pool.checkout() as conn:
                migrate.execute(conn, "SELECT 1")
                raise Boom()

        with pool.checkout() as conn:
            row = migrate.fetch_one(conn, "SELECT 1 AS ok")
            self.assertEqual(row["ok"], 1)
            self.assertEqual(
                conn.info.transaction_status,
                psycopg.pq.TransactionStatus.INTRANS,
                "a plain read opens a transaction; what matters is it is not INERROR",
            )

    def test_a_connection_comes_back_clean_even_after_a_plain_read(self):
        with pool.checkout() as conn:
            migrate.execute(conn, "SELECT 1")
        with pool.checkout() as conn:
            self.assertEqual(
                conn.info.transaction_status,
                psycopg.pq.TransactionStatus.IDLE,
                "a borrowed connection must start outside a transaction",
            )


if __name__ == "__main__":
    unittest.main()
