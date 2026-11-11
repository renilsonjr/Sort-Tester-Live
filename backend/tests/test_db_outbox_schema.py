"""Durable outbox extension contract (issue #6 check 4)."""
import json
import unittest

from backend.db import migrate, settings


@unittest.skipUnless(
    settings.environment_has_test_url(),
    "SORT_TESTER_TEST_DATABASE_URL not set; database tests skipped",
)
class OutboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:
            cls.conninfo = settings.test_database_url()
            migrate.recreate_scratch_database(
                settings.admin_url(), settings.SCRATCH_DB_NAME
            )
            migrate.upgrade_to_head(cls.conninfo)
        except settings.DatabaseConfigError as exc:
            raise unittest.SkipTest(str(exc)) from None

    def setUp(self):
        # rollback at teardown keeps tests isolated (no committed rows leak
        # between tests; only the migration's schema is committed); cleanups
        # run LIFO, so register close first to roll back before closing
        self.conn = migrate.connect(self.conninfo)
        self.addCleanup(self.conn.close)
        self.addCleanup(self.conn.rollback)

    def test_message_key_unique(self):
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k1', '{}'::jsonb, 'v1')
        """)
        with self.assertRaises(migrate.IntegrityError):
            migrate.execute(self.conn, """
                INSERT INTO outbox (message_key, payload, recipient_destination_version)
                VALUES ('k1', '{}'::jsonb, 'v1')
            """)

    def test_payload_jsonb(self):
        payload = {"to": "a@example.com", "subject": "launch"}
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k2', %s::jsonb, 'v1')
        """, (json.dumps(payload),))
        row = migrate.fetch_one(
            self.conn, "SELECT payload FROM outbox WHERE message_key = 'k2'"
        )
        self.assertEqual(row['payload'], payload)

    def test_attempt_count_and_lease_update(self):
        migrate.execute(self.conn, """
            INSERT INTO outbox (message_key, payload, recipient_destination_version)
            VALUES ('k3', '{}'::jsonb, 'v1')
        """)
        migrate.execute(self.conn, """
            UPDATE outbox
            SET attempt_count = 1, worker_lease_until = now() + interval '5 minutes'
            WHERE message_key = 'k3'
        """)
        row = migrate.fetch_one(
            self.conn,
            "SELECT attempt_count, worker_lease_until FROM outbox"
            " WHERE message_key = 'k3'",
        )
        self.assertEqual(row['attempt_count'], 1)
        self.assertIsNotNone(row['worker_lease_until'])

    def test_no_feature_dependencies(self):
        row = migrate.fetch_one(self.conn, """
            SELECT COUNT(*) AS n FROM information_schema.table_constraints
            WHERE table_name = 'outbox' AND constraint_type = 'FOREIGN KEY'
        """)
        self.assertEqual(row['n'], 0)
