"""The Entra token provider: cache, refresh, failure, and never logging it (#84)."""
import logging
import time
import unittest
from contextlib import contextmanager
from unittest import mock

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


class TokenEndpointSelectionTests(unittest.TestCase):
    """Which identity endpoint the request targets, per hosting platform (#84)."""

    def _headers(self, request):
        return {key.lower(): value for key, value in request.header_items()}

    def test_container_apps_endpoint_is_preferred_when_injected(self):
        # Container Apps / App Service inject these; the request must go there,
        # not to the VM IMDS address the app previously hard-coded.
        env = {
            entra_token.settings.DB_IDENTITY_CLIENT_ID_ENV_VAR: "client-123",
            entra_token.IDENTITY_ENDPOINT_ENV_VAR: "http://localhost:42356/msi/token",
            entra_token.IDENTITY_HEADER_ENV_VAR: "header-secret",
        }
        with mock.patch.dict(entra_token.os.environ, env, clear=True):
            request = entra_token._token_request()
        self.assertTrue(request.full_url.startswith("http://localhost:42356/msi/token?"))
        self.assertIn("api-version=2019-08-01", request.full_url)
        self.assertIn("client_id=client-123", request.full_url)
        headers = self._headers(request)
        self.assertEqual(headers.get("x-identity-header"), "header-secret")
        self.assertNotIn("metadata", headers)

    def test_falls_back_to_imds_without_an_identity_endpoint(self):
        env = {entra_token.settings.DB_IDENTITY_CLIENT_ID_ENV_VAR: "client-123"}
        with mock.patch.dict(entra_token.os.environ, env, clear=True):
            request = entra_token._token_request()
        self.assertTrue(request.full_url.startswith("http://169.254.169.254/"))
        self.assertIn("api-version=2018-02-01", request.full_url)
        headers = self._headers(request)
        self.assertEqual(headers.get("metadata"), "true")
        self.assertNotIn("x-identity-header", headers)

    def test_a_blank_identity_header_is_not_treated_as_the_endpoint(self):
        # Half-configured platform: endpoint present, header empty. Must not
        # send a headerless MSI request; fall back to IMDS instead.
        env = {
            entra_token.settings.DB_IDENTITY_CLIENT_ID_ENV_VAR: "client-123",
            entra_token.IDENTITY_ENDPOINT_ENV_VAR: "http://localhost:42356/msi/token",
            entra_token.IDENTITY_HEADER_ENV_VAR: "",
        }
        with mock.patch.dict(entra_token.os.environ, env, clear=True):
            request = entra_token._token_request()
        self.assertTrue(request.full_url.startswith("http://169.254.169.254/"))

    def test_missing_client_id_raises_token_unavailable(self):
        with mock.patch.dict(entra_token.os.environ, {}, clear=True):
            with self.assertRaises(entra_token.TokenUnavailable):
                entra_token._token_request()


class TokenResourceTests(unittest.TestCase):
    """One identity, more than one resource: the database and blob storage (#13)."""

    def setUp(self):
        entra_token.set_token_fetcher(None)
        entra_token.reset_cache()
        self.addCleanup(entra_token.set_token_fetcher, None)
        self.addCleanup(entra_token.reset_cache)

    def test_the_request_asks_for_the_named_resource(self):
        env = {
            entra_token.settings.DB_IDENTITY_CLIENT_ID_ENV_VAR: "client-123",
            entra_token.IDENTITY_ENDPOINT_ENV_VAR: "http://localhost:42356/msi/token",
            entra_token.IDENTITY_HEADER_ENV_VAR: "header-secret",
        }
        with mock.patch.dict(entra_token.os.environ, env, clear=True):
            storage = entra_token._token_request(entra_token.STORAGE_TOKEN_RESOURCE)
            database = entra_token._token_request()
        self.assertIn("resource=https%3A%2F%2Fstorage.azure.com", storage.full_url)
        self.assertIn("resource=https%3A%2F%2Fossrdbms-aad.database.windows.net", database.full_url)

    def test_each_resource_gets_and_caches_its_own_token(self):
        asked = []

        def fetch(resource):
            asked.append(resource)
            return {"access_token": f"tok-for-{resource}", "expires_on": "9999999999"}

        with mock.patch.object(entra_token, "_fetch_token", fetch):
            db_first = entra_token.db_access_token()
            storage = entra_token.access_token(entra_token.STORAGE_TOKEN_RESOURCE)
            db_again = entra_token.db_access_token()
            storage_again = entra_token.access_token(entra_token.STORAGE_TOKEN_RESOURCE)
        self.assertEqual(db_first, db_again)
        self.assertEqual(storage, storage_again)
        self.assertNotEqual(db_first, storage)
        self.assertEqual(
            asked, [entra_token.DB_TOKEN_RESOURCE, entra_token.STORAGE_TOKEN_RESOURCE]
        )


class ExpiresOnParsingTests(unittest.TestCase):
    """expires_on comes back in more than one shape across endpoints (#84)."""

    def test_epoch_seconds_as_string_or_number(self):
        self.assertEqual(entra_token._parse_expires_on("1700000000"), 1700000000.0)
        self.assertEqual(entra_token._parse_expires_on(1700000000), 1700000000.0)

    def test_a_formatted_datetime_is_parsed_to_epoch(self):
        # An App Service build returns "MM/DD/YYYY h:mm:ss AM +00:00".
        parsed = entra_token._parse_expires_on("11/19/2026 5:22:47 PM +00:00")
        self.assertIsInstance(parsed, float)
        self.assertGreater(parsed, 1_700_000_000)

    def test_an_unreadable_expiry_raises_rather_than_never_expiring(self):
        with self.assertRaises(entra_token.TokenUnavailable):
            entra_token._parse_expires_on("not-a-date")
