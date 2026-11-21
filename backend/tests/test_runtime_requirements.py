"""The container's dependency list stays small and in step with development."""
import re
import unittest
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def pins(name):
    found = {}
    for line in (BACKEND / name).read_text(encoding="utf-8").splitlines():
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)(?:\[[^\]]*\])?==([^\s#]+)", line.strip())
        if match:
            found[re.sub(r"[-_.]+", "-", match.group(1)).lower()] = match.group(2)
    return found


class RuntimeRequirementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.runtime = pins("requirements-runtime.txt")
        cls.development = pins("requirements.txt")

    def test_every_line_is_an_exact_pin(self):
        lines = [
            line.strip()
            for line in (BACKEND / "requirements-runtime.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        self.assertEqual(len(lines), len(self.runtime), "a line is not name==version")

    def test_versions_match_the_development_environment(self):
        differing = {
            name: (version, self.development[name])
            for name, version in self.runtime.items()
            if name in self.development and self.development[name] != version
        }
        self.assertEqual(differing, {})

    def test_what_the_app_imports_is_installed(self):
        for name in ("fastapi", "uvicorn", "psycopg", "psycopg-binary", "pydantic",
                     "pydantic-settings", "argon2-cffi", "alembic", "sqlalchemy"):
            with self.subTest(name=name):
                self.assertIn(name, self.runtime)

    def test_development_only_packages_stay_out_of_the_container(self):
        for name in ("sentry-sdk", "requests", "httpx", "fastapi-cli", "fastapi-cloud-cli",
                     "opentelemetry-sdk", "watchfiles", "websockets", "pyyaml", "rich",
                     "setuptools", "pip"):
            with self.subTest(name=name):
                self.assertNotIn(name, self.runtime)

    def test_the_list_stays_small(self):
        self.assertLessEqual(len(self.runtime), 30)


if __name__ == "__main__":
    unittest.main()
