"""The app's version number (issue #274).

One string, in one file, reported by /health. The app asks the server what
is running rather than drawing what was in the file when the page was
written, so the number on screen is the number actually serving it.
"""
import re
import unittest

from fastapi.testclient import TestClient

from backend import version as version_module
from backend import main


class VersionStringTests(unittest.TestCase):
    def test_it_is_a_version_and_nothing_else(self):
        # major.minor.patch, with an optional pre-release suffix while a
        # release is being prepared (0.1.0-dev until the tag is cut)
        self.assertRegex(version_module.VERSION, r"^\d+\.\d+\.\d+(-[a-z0-9.]+)?$")

    def test_it_lives_in_one_place(self):
        source = (version_module.__file__)
        with open(source, encoding="utf-8") as handle:
            text = handle.read()
        # exactly one assignment, so there is nothing to keep in step
        self.assertEqual(len(re.findall(r"^VERSION\s*=", text, re.M)), 1)


class HealthVersionTests(unittest.TestCase):
    def test_health_reports_the_running_version(self):
        with TestClient(main.app) as client:
            body = client.get("/health").json()
        self.assertEqual(body["status"], "ok")
        self.assertEqual(body["version"], version_module.VERSION)

    def test_health_still_needs_no_session(self):
        # the sign-in screen and an uptime check both read it
        with TestClient(main.app) as client:
            self.assertEqual(client.get("/health").status_code, 200)

    def test_health_says_nothing_else(self):
        # not a place to leak a commit, a host or a database name
        with TestClient(main.app) as client:
            body = client.get("/health").json()
        self.assertEqual(set(body), {"status", "version"})


if __name__ == "__main__":
    unittest.main()
