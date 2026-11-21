"""Run the complete backend suite against a local scratch DB, without skips.

Ordinary unittest treats skipped tests as success. CI needs a stricter
contract: a missing/unusable database must not produce a green check.
Run from the repository root with ``python -m backend.ci_tests``.
"""

import json
import os
import sys
import unittest

from psycopg.conninfo import conninfo_to_dict

from backend.db import settings


def run_suite(suite):
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    successful = result.wasSuccessful() and result.testsRun > 0 and not result.skipped
    print(json.dumps({
        "tests_run": result.testsRun,
        "failures": len(result.failures),
        "errors": len(result.errors),
        "skipped": len(result.skipped),
        "successful": bool(successful),
    }), flush=True)
    return 0 if successful else 1


def main():
    try:
        url = settings.test_database_url()  # Enforces the scratch database name.
        parameters = conninfo_to_dict(url)
        if parameters.get("service") or os.environ.get("PGSERVICE", "").strip():
            raise settings.DatabaseConfigError("Database CI does not use connection service profiles.")
        host = (parameters.get("host") or "").strip().strip("[]")
        hostaddr = (parameters.get("hostaddr") or os.environ.get("PGHOSTADDR") or host).strip().strip("[]")
        if host not in settings.LOOPBACK_HOSTS or hostaddr not in settings.LOOPBACK_HOSTS:
            raise settings.DatabaseConfigError("Database CI requires an explicit loopback host/address.")
        if os.environ.get(settings.APP_ENV_VAR, "").strip():
            raise settings.DatabaseConfigError("Unset the application database override before database CI.")
    except settings.DatabaseConfigError as exc:
        print(f"Database CI refused: {exc}", file=sys.stderr)
        return 2

    suite = unittest.defaultTestLoader.discover("backend/tests")
    return run_suite(suite)


if __name__ == "__main__":
    raise SystemExit(main())
