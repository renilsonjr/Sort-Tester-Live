"""Exercise the operator SQL against the disposable scratch database only."""
import os
import shutil
import subprocess
import unittest
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch
from fastapi.testclient import TestClient
from backend.main import create_app
from backend.tests.browser import BROWSER

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from backend.db import migrate, settings

SCRIPT = Path(__file__).resolve().parents[2] / "infra/azure/db-role.sql"

@unittest.skipUnless(settings.environment_has_test_url() and shutil.which("psql"),
                     "scratch PostgreSQL URL and psql required")
class RuntimeRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.url = settings.test_database_url()
        migrate.recreate_scratch_database(settings.admin_url(), settings.SCRATCH_DB_NAME)
        migrate.upgrade_to_head(cls.url)

    def setUp(self):
        self.role = "sort_runtime_test_" + uuid4().hex[:12]
        self.admin = psycopg.connect(self.url, autocommit=True)
        self.addCleanup(self.admin.close)
        self.addCleanup(self.remove_role)

    def remove_role(self):
        if self.admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (self.role,)).fetchone():
            self.admin.execute(sql.SQL("DROP OWNED BY {}").format(sql.Identifier(self.role)))
            self.admin.execute(sql.SQL("DROP ROLE {}").format(sql.Identifier(self.role)))

    def provision(self, target=settings.SCRATCH_DB_NAME):
        self.assertTrue(SCRIPT.exists(), "operator role script is missing")
        params = conninfo_to_dict(self.url)
        env = os.environ.copy()
        for key, name in [("host", "PGHOST"), ("port", "PGPORT"), ("user", "PGUSER"),
                          ("password", "PGPASSWORD"), ("dbname", "PGDATABASE"),
                          ("sslmode", "PGSSLMODE"), ("sslrootcert", "PGSSLROOTCERT")]:
            if key in params:
                env[name] = params[key]
        owner = self.admin.execute("SELECT current_user").fetchone()[0]
        return subprocess.run([shutil.which("psql"), "-X", "-v", f"target_database={target}",
                               "-v", f"runtime_role={self.role}", "-v", f"migration_role={owner}",
                               "-f", str(SCRIPT)], env=env, capture_output=True, text=True)

    def test_wrong_database_is_refused_before_creating_a_role(self):
        result = self.provision(target="wrong_target")
        self.assertNotEqual(result.returncode, 0)
        self.assertIsNone(self.admin.execute("SELECT 1 FROM pg_roles WHERE rolname=%s", (self.role,)).fetchone())

    def test_runtime_can_write_app_data_but_cannot_migrate_or_edit_metadata(self):
        result = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.admin.execute(
            "SELECT rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls FROM pg_roles WHERE rolname=%s",
            (self.role,)).fetchone(), (False, False, False, False, False, False))
        with psycopg.connect(self.url, autocommit=True) as conn:
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self.role)))
            row = conn.execute("INSERT INTO accounts(username, username_lower, tag) VALUES ('role_test', 'role_test', 'ROL123') RETURNING id").fetchone()
            conn.execute("UPDATE accounts SET username='role_updated' WHERE id=%s", (row[0],))
            self.assertEqual(conn.execute("SELECT username FROM accounts WHERE id=%s", (row[0],)).fetchone()[0], "role_updated")
            conn.execute("DELETE FROM accounts WHERE id=%s", (row[0],))
            for statement in ["CREATE TABLE forbidden_probe(id int)",
                              "ALTER TABLE accounts ADD COLUMN forbidden_probe int",
                              "UPDATE alembic_version SET version_num='0001'",
                              "SELECT * FROM tooling_probe"]:
                with self.assertRaises(psycopg.errors.InsufficientPrivilege):
                    conn.execute(statement)
        self.admin.execute("CREATE TABLE runtime_future_probe(id bigserial PRIMARY KEY)")
        try:
            self.assertTrue(self.admin.execute("SELECT has_table_privilege(%s, 'runtime_future_probe', 'INSERT')", (self.role,)).fetchone()[0])
            self.assertTrue(self.admin.execute("SELECT has_sequence_privilege(%s, 'runtime_future_probe_id_seq', 'USAGE')", (self.role,)).fetchone()[0])
        finally:
            self.admin.execute("DROP TABLE runtime_future_probe")
        # A second execution must refuse an existing role, not alter it.
        self.assertNotEqual(self.provision().returncode, 0)

    def test_register_login_and_logout_work_with_runtime_privileges(self):
        result = self.provision()
        self.assertEqual(result.returncode, 0, result.stderr)
        def limited_connection():
            conn = migrate.connect(self.url)
            conn.execute(sql.SQL("SET ROLE {}").format(sql.Identifier(self.role)))
            conn.commit()
            return conn
        with patch("backend.routers.auth._db_connection", side_effect=limited_connection):
            with TestClient(create_app(), headers=BROWSER) as client:
                registered = client.post("/api/auth/register", json={"username": "runtime_login"})
                self.assertEqual(registered.status_code, 200)
                logged_in = client.post("/api/auth/login", json={"login_id": registered.json()["login_id"]})
                self.assertEqual(logged_in.status_code, 200)
                self.assertEqual(client.get("/api/auth/me").status_code, 200)
                self.assertEqual(client.post("/api/auth/logout").status_code, 204)
                self.assertEqual(client.get("/api/auth/me").status_code, 401)
