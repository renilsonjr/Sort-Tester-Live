"""The pool injects a per-connection Entra token in managed-identity mode (#84)."""
import unittest
from unittest import mock

from backend.db import pool, settings


class ManagedIdentityPoolTests(unittest.TestCase):
    def setUp(self):
        # Earlier real-database tests share the process-global pool and leave
        # it open; init_pool is idempotent, so without this the pool would
        # not be rebuilt and the mocked ConnectionPool would never be called.
        pool.close_pool()

    def tearDown(self):
        pool.close_pool()

    def test_managed_identity_builds_a_callable_kwargs_that_injects_the_token(self):
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return f"token-{calls['n']}"

        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app@host/db?sslmode=verify-full",
                auth_mode=settings.MANAGED_IDENTITY_MODE,
                token_provider=provider,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]

        self.assertTrue(callable(built_kwargs), "managed-identity kwargs must be a callable")
        first = built_kwargs()
        second = built_kwargs()
        self.assertEqual(first["password"], "token-1")
        self.assertEqual(second["password"], "token-2")
        self.assertIn("row_factory", first)

    def test_password_mode_keeps_static_kwargs(self):
        with mock.patch("backend.db.pool.ConnectionPool") as FakePool:
            FakePool.return_value = mock.MagicMock()
            pool.init_pool(
                "postgresql://app:pw@host/db?sslmode=verify-full",
                auth_mode=settings.PASSWORD_MODE,
            )
            built_kwargs = FakePool.call_args.kwargs["kwargs"]
        self.assertFalse(callable(built_kwargs))
        self.assertNotIn("password", built_kwargs)
