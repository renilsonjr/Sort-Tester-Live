"""The out-of-database deletion list (issue #13, restore runbook step 4)."""
import os
import unittest
from datetime import datetime, timezone
from unittest import mock

from backend.auth import deletion_list
from backend.db import entra_token, settings

CONTAINER = "https://stsortdel.blob.core.windows.net/deletions"
ACCOUNT = "cd2e553a-7aee-448c-a385-4c89abf41079"
WHEN = datetime(2026, 11, 19, 21, 51, 4, tzinfo=timezone.utc)


def _env(**values):
    cleared = {deletion_list.ENV_VAR: ""}
    cleared.update(values)
    return mock.patch.dict(os.environ, cleared)


class FakeBlob:
    """Records every request; answers with the queued status codes."""

    def __init__(self, *statuses):
        self.calls = []
        self.statuses = list(statuses)

    def __call__(self, method, url, headers, body):
        self.calls.append((method, url, dict(headers), body))
        answer = self.statuses.pop(0) if self.statuses else 201
        if isinstance(answer, Exception):
            raise answer
        return answer


class DeletionListCase(unittest.TestCase):
    def setUp(self):
        entra_token.reset_cache()
        entra_token.set_token_fetcher(
            lambda: {"access_token": "storage-secret-token", "expires_on": "9999999999"}
        )
        self.addCleanup(entra_token.set_token_fetcher, None)
        self.addCleanup(entra_token.reset_cache)
        self.addCleanup(deletion_list.set_transport, None)
        # alembic's fileConfig (run by database tests earlier in a full suite)
        # disables every logger that already exists; assertLogs would then
        # see nothing. Same hazard as in test_entra_token.
        previous = deletion_list.logger.disabled
        deletion_list.logger.disabled = False
        self.addCleanup(setattr, deletion_list.logger, "disabled", previous)


class ConfigurationTests(DeletionListCase):
    def test_unset_means_the_list_is_off(self):
        with _env():
            self.assertIsNone(deletion_list.container_url())

    def test_the_word_disabled_turns_it_off_on_purpose(self):
        with _env(**{deletion_list.ENV_VAR: "disabled"}):
            self.assertIsNone(deletion_list.container_url())

    def test_a_blob_container_url_is_accepted(self):
        with _env(**{deletion_list.ENV_VAR: CONTAINER + "/"}):
            self.assertEqual(deletion_list.container_url(), CONTAINER)

    def test_malformed_urls_are_refused(self):
        for bad in (
            "http://stsortdel.blob.core.windows.net/deletions",  # not https
            "https://example.com/deletions",  # not blob storage
            "https://stsortdel.blob.core.windows.net",  # no container
            "https://stsortdel.blob.core.windows.net/a/b",  # more than a container
            CONTAINER + "?sv=2021&sig=abc",  # a SAS token is a secret in config
            "https://user:pw@stsortdel.blob.core.windows.net/deletions",
        ):
            with self.subTest(bad=bad), _env(**{deletion_list.ENV_VAR: bad}):
                with self.assertRaises(deletion_list.DeletionListConfigError):
                    deletion_list.container_url()

    def test_a_config_error_never_echoes_the_value(self):
        secret = CONTAINER + "?sig=TOPSECRET"
        with _env(**{deletion_list.ENV_VAR: secret}):
            with self.assertRaises(deletion_list.DeletionListConfigError) as caught:
                deletion_list.container_url()
        self.assertNotIn("TOPSECRET", str(caught.exception))


class StartupPolicyTests(DeletionListCase):
    def test_managed_identity_without_the_setting_refuses_to_start(self):
        with _env():
            with self.assertRaises(deletion_list.DeletionListConfigError):
                deletion_list.check_policy(db_auth_mode=settings.MANAGED_IDENTITY_MODE)

    def test_managed_identity_with_a_url_starts(self):
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            deletion_list.check_policy(db_auth_mode=settings.MANAGED_IDENTITY_MODE)

    def test_managed_identity_may_opt_out_explicitly(self):
        with _env(**{deletion_list.ENV_VAR: "disabled"}):
            deletion_list.check_policy(db_auth_mode=settings.MANAGED_IDENTITY_MODE)

    def test_password_mode_needs_nothing(self):
        with _env():
            deletion_list.check_policy(db_auth_mode=settings.PASSWORD_MODE)

    def test_a_malformed_url_refuses_to_start_in_any_mode(self):
        with _env(**{deletion_list.ENV_VAR: "https://example.com/x"}):
            with self.assertRaises(deletion_list.DeletionListConfigError):
                deletion_list.check_policy(db_auth_mode=settings.PASSWORD_MODE)


class RecordTests(DeletionListCase):
    def test_off_means_no_request_at_all(self):
        blob = FakeBlob()
        deletion_list.set_transport(blob)
        with _env():
            deletion_list.record(ACCOUNT, WHEN)
            deletion_list.forget(ACCOUNT)
        self.assertEqual(blob.calls, [])

    def test_record_writes_one_blob_named_by_the_account(self):
        blob = FakeBlob(201)
        deletion_list.set_transport(blob)
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            deletion_list.record(ACCOUNT, WHEN)
        (method, url, headers, body), = blob.calls
        self.assertEqual(method, "PUT")
        self.assertEqual(url, f"{CONTAINER}/{ACCOUNT}")
        self.assertEqual(body, b"2026-11-19T21:51:04+00:00")
        self.assertEqual(headers["Authorization"], "Bearer storage-secret-token")
        self.assertEqual(headers["x-ms-blob-type"], "BlockBlob")
        self.assertIn("x-ms-version", headers)

    def test_the_body_holds_the_time_and_nothing_else(self):
        blob = FakeBlob(201)
        deletion_list.set_transport(blob)
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            deletion_list.record(ACCOUNT, WHEN)
        body = blob.calls[0][3].decode()
        self.assertEqual(datetime.fromisoformat(body), WHEN)

    def test_a_naive_time_is_refused(self):
        deletion_list.set_transport(FakeBlob())
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertRaises(ValueError):
                deletion_list.record(ACCOUNT, datetime(2026, 11, 19, 21, 51, 4))

    def test_only_a_uuid_can_become_a_blob_name(self):
        blob = FakeBlob()
        deletion_list.set_transport(blob)
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertRaises(ValueError):
                deletion_list.record("../other-container/x", WHEN)
        self.assertEqual(blob.calls, [])

    def test_any_other_status_is_unavailable(self):
        for status in (200, 403, 404, 500, 503):
            with self.subTest(status=status):
                deletion_list.set_transport(FakeBlob(status))
                with _env(**{deletion_list.ENV_VAR: CONTAINER}):
                    with self.assertRaises(deletion_list.DeletionListUnavailable):
                        deletion_list.record(ACCOUNT, WHEN)

    def test_a_network_error_is_unavailable(self):
        deletion_list.set_transport(FakeBlob(OSError("connection refused")))
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertRaises(deletion_list.DeletionListUnavailable):
                deletion_list.record(ACCOUNT, WHEN)

    def test_no_token_is_unavailable_and_sends_nothing(self):
        def broken():
            raise OSError("identity endpoint down")

        entra_token.set_token_fetcher(broken)
        blob = FakeBlob()
        deletion_list.set_transport(blob)
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertRaises(deletion_list.DeletionListUnavailable):
                deletion_list.record(ACCOUNT, WHEN)
        self.assertEqual(blob.calls, [])

    def test_the_token_never_reaches_the_error_or_the_log(self):
        deletion_list.set_transport(FakeBlob(OSError("Bearer storage-secret-token")))
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertLogs(deletion_list.logger, level="WARNING") as logs:
                with self.assertRaises(deletion_list.DeletionListUnavailable) as caught:
                    deletion_list.record(ACCOUNT, WHEN)
        self.assertNotIn("storage-secret-token", str(caught.exception))
        self.assertNotIn("storage-secret-token", "\n".join(logs.output))


class ForgetTests(DeletionListCase):
    def test_forget_deletes_the_blob(self):
        blob = FakeBlob(202)
        deletion_list.set_transport(blob)
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            deletion_list.forget(ACCOUNT)
        (method, url, _headers, body), = blob.calls
        self.assertEqual((method, url, body), ("DELETE", f"{CONTAINER}/{ACCOUNT}", None))

    def test_forget_never_raises(self):
        for answer in (404, 500, OSError("down")):
            with self.subTest(answer=answer):
                deletion_list.set_transport(FakeBlob(answer))
                with _env(**{deletion_list.ENV_VAR: CONTAINER}):
                    deletion_list.forget(ACCOUNT)

    def test_a_failed_forget_is_logged_for_the_operator(self):
        deletion_list.set_transport(FakeBlob(500))
        with _env(**{deletion_list.ENV_VAR: CONTAINER}):
            with self.assertLogs(deletion_list.logger, level="ERROR") as logs:
                deletion_list.forget(ACCOUNT)
        self.assertIn(ACCOUNT, "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
