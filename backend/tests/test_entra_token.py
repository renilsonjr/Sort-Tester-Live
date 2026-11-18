"""The Entra token provider: cache, refresh, failure, and never logging it (#84)."""
import logging
import time
import unittest
from contextlib import contextmanager

from backend.db import entra_token


def _payload(token, ttl_seconds):
    return {"access_token": token, "expires_on": str(int(time.time()) + ttl_seconds)}


class EntraTokenTests(unittest.TestCase):
    def tearDown(self):
        entra_token.set_token_fetcher(None)
        entra_token.reset_cache()

    def test_returns_the_access_token(self):
        entra_token.set_token_fetcher(lambda: _payload("tok-abc", 3600))
        self.assertEqual(entra_token.db_access_token(), "tok-abc")

    def test_reuses_within_lifetime(self):
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            return _payload(f"tok-{calls['n']}", 3600)

        entra_token.set_token_fetcher(fetch)
        first = entra_token.db_access_token()
        second = entra_token.db_access_token()
        self.assertEqual(first, "tok-1")
        self.assertEqual(second, "tok-1")
        self.assertEqual(calls["n"], 1, "a valid cached token must be reused")

    def test_refreshes_within_the_skew_window(self):
        calls = {"n": 0}

        def fetch():
            calls["n"] += 1
            ttl = entra_token.EXPIRY_SKEW_SECONDS - 10 if calls["n"] == 1 else 3600
            return _payload(f"tok-{calls['n']}", ttl)

        entra_token.set_token_fetcher(fetch)
        self.assertEqual(entra_token.db_access_token(), "tok-1")
        self.assertEqual(entra_token.db_access_token(), "tok-2")
        self.assertEqual(calls["n"], 2)

    def test_failure_raises_tokenunavailable(self):
        def fetch():
            raise RuntimeError("imds down")

        entra_token.set_token_fetcher(fetch)
        with self.assertRaises(entra_token.TokenUnavailable):
            entra_token.db_access_token()

    @contextmanager
    def _capture_logs(self):
        """Capture this module's log records regardless of global logging
        state. assertLogs requires >=1 record and is defeated by whatever
        another test left behind; notably alembic's fileConfig runs with
        disable_existing_loggers=True and sets this logger's .disabled flag,
        which the app process (migrations run separately) never does. We
        re-enable the logger for the capture and restore every change."""
        records = []
        handler = logging.Handler()
        handler.emit = records.append
        logger = logging.getLogger("backend.db.entra_token")
        previous_level = logger.level
        previous_disabled = logger.disabled
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.disabled = False
        try:
            yield records
        finally:
            logger.removeHandler(handler)
            logger.setLevel(previous_level)
            logger.disabled = previous_disabled

    def test_token_value_is_never_logged(self):
        entra_token.set_token_fetcher(lambda: _payload("super-secret-token", 3600))
        with self._capture_logs() as records:
            entra_token.db_access_token()
        self.assertFalse(
            any("super-secret-token" in record.getMessage() for record in records),
            "the token value must never appear in logs",
        )

    def test_failure_logs_the_error_type_not_a_token(self):
        def fetch():
            raise RuntimeError("secret-looking-detail")

        entra_token.set_token_fetcher(fetch)
        with self._capture_logs() as records:
            try:
                entra_token.db_access_token()
            except entra_token.TokenUnavailable:
                pass
        messages = "\n".join(record.getMessage() for record in records)
        self.assertIn("RuntimeError", messages)
        self.assertNotIn("secret-looking-detail", messages)
