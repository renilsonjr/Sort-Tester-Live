"""CI must not report a green database suite when unittest skipped it."""

import contextlib
import importlib
import importlib.util
import io
import json
import os
import unittest
from unittest.mock import patch

TEST_URL = "postgresql://postgres@127.0.0.1:5433/sort_tester_unittest_scratch"


class DatabaseCiRunnerTests(unittest.TestCase):
    def runner(self):
        self.assertIsNotNone(
            importlib.util.find_spec("backend.ci_tests"),
            "CI needs a runner that refuses missing database configuration and skipped tests",
        )
        return importlib.import_module("backend.ci_tests")

    def run_case(self, cases):
        runner = self.runner()
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(io.StringIO()):
            code = runner.run_suite(unittest.TestSuite(cases))
        return code, json.loads(output.getvalue().splitlines()[-1])

    def test_a_passing_nonempty_suite_is_accepted(self):
        code, report = self.run_case([unittest.FunctionTestCase(lambda: None)])
        self.assertEqual(code, 0)
        self.assertEqual(report["tests_run"], 1)
        self.assertEqual(report["skipped"], 0)

    def test_a_skipped_test_fails_even_when_unittest_considers_it_successful(self):
        def skipped():
            raise unittest.SkipTest("database unavailable")
        code, report = self.run_case([unittest.FunctionTestCase(skipped)])
        self.assertEqual(code, 1)
        self.assertEqual(report["skipped"], 1)
        self.assertFalse(report["successful"])

    def test_an_empty_suite_is_not_a_successful_ci_check(self):
        code, report = self.run_case([])
        self.assertEqual(code, 1)
        self.assertEqual(report["tests_run"], 0)

    def test_a_test_failure_still_fails_the_gate(self):
        def failing():
            raise AssertionError("fixture failure")
        code, report = self.run_case([unittest.FunctionTestCase(failing)])
        self.assertEqual(code, 1)
        self.assertEqual(report["failures"], 1)

    def assert_refused_before_discovery(self, url, app_url="", connection_env=None):
        runner = self.runner()
        with patch.dict(os.environ, {
            "SORT_TESTER_TEST_DATABASE_URL": url,
            "SORT_TESTER_DATABASE_URL": app_url,
            "PGHOSTADDR": "",
            "PGSERVICE": "",
            **(connection_env or {}),
        }), patch.object(
            runner.unittest.defaultTestLoader, "discover",
            side_effect=AssertionError("Unsafe configuration reached test discovery"),
        ):
            with contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(runner.main(), 2)

    def test_missing_test_url_stops_before_discovery(self):
        self.assert_refused_before_discovery("")

    def test_a_non_scratch_database_is_refused_before_discovery(self):
        self.assert_refused_before_discovery("postgresql://postgres@127.0.0.1:5433/not_scratch")

    def test_a_remote_database_is_refused_before_discovery(self):
        self.assert_refused_before_discovery(
            "postgresql://postgres@db.example.com/sort_tester_unittest_scratch?sslmode=verify-full"
        )

    def test_hostaddr_cannot_override_loopback_to_a_remote_server(self):
        self.assert_refused_before_discovery(TEST_URL + "?hostaddr=192.0.2.1")

    def test_an_app_database_override_is_refused_before_discovery(self):
        self.assert_refused_before_discovery(TEST_URL, "postgresql://example.invalid/app")

    def test_an_inherited_remote_hostaddr_is_refused_before_discovery(self):
        self.assert_refused_before_discovery(TEST_URL, connection_env={"PGHOSTADDR": "192.0.2.1"})

    def test_an_inherited_service_profile_is_refused_before_discovery(self):
        self.assert_refused_before_discovery(TEST_URL, connection_env={"PGSERVICE": "other-cluster"})

    def test_a_url_service_profile_is_refused_before_discovery(self):
        self.assert_refused_before_discovery(TEST_URL + "?service=other-cluster")
