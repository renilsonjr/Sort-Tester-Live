"""Environment-only connection settings for test database tooling."""
import os
from urllib.parse import unquote, urlsplit, urlunsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict

ENV_VAR = "SORT_TESTER_TEST_DATABASE_URL"
APP_ENV_VAR = "SORT_TESTER_DATABASE_URL"
SCRATCH_DB_NAME = "sort_tester_unittest_scratch"
MAINTENANCE_DATABASE = "postgres"


class DatabaseConfigError(Exception):
    """Raised when the test database connection setting is unset or malformed."""


def test_database_url() -> str:
    """Return a validated test database URL from the environment.

    The URL must be valid postgresql conninfo whose effective database is
    the unittest scratch database. Other query options are tolerated, but
    a ``dbname`` option may not override the effective target.
    """
    raw = os.environ.get(ENV_VAR, "")
    url = raw.strip()
    if not url:
        raise DatabaseConfigError(
            f"{ENV_VAR} is not set; export it with a postgresql:// URL "
            f"pointing at the {SCRATCH_DB_NAME} database."
        )
    try:
        parts = urlsplit(url)
    except ValueError:
        raise DatabaseConfigError(
            f"{ENV_VAR} must be a valid postgresql:// conninfo URL."
        ) from None
    if parts.scheme != "postgresql":
        raise DatabaseConfigError(
            f"{ENV_VAR} must use a postgresql:// URL pointing at the "
            f"{SCRATCH_DB_NAME} database."
        )
    try:
        parameters = conninfo_to_dict(url)
    except (psycopg.Error, ValueError):
        raise DatabaseConfigError(
            f"{ENV_VAR} must be a valid postgresql:// conninfo URL."
        ) from None
    if parameters.get("dbname") != SCRATCH_DB_NAME:
        raise DatabaseConfigError(
            f"{ENV_VAR} must resolve to the {SCRATCH_DB_NAME} database so "
            "tooling cannot migrate another database."
        )
    return url


def environment_has_test_url() -> bool:
    """Return True when the test database URL is present in the environment.

    Presence only: the URL is not validated here, so callers that need a
    usable DSN should call :func:`test_database_url` and handle
    :class:`DatabaseConfigError`.
    """
    return bool(os.environ.get(ENV_VAR, "").strip())


def app_database_url() -> str:
    """Return the validated production/application database URL.

    Falls back to the test database URL in test environments for convenience.
    """
    raw = os.environ.get(APP_ENV_VAR, "").strip()
    if not raw:
        # In test environments the app may run against the scratch database.
        return test_database_url()
    url = raw
    if url.startswith("postgresql://"):
        return url
    raise DatabaseConfigError(
        f"{APP_ENV_VAR} must be a valid postgresql:// URL when set."
    )


def admin_url() -> str:
    """Return the same server URL with its database replaced by the maintenance one.

    The admin/maintenance URL keeps whatever host, port and credentials
    the test URL carries, but points its database component at
    ``MAINTENANCE_DATABASE`` so tasks like DROP/CREATE DATABASE run
    outside the database being managed.
    """
    url = test_database_url()
    parts = urlsplit(url)
    base = parts.path.rstrip("/")
    parent_path = base.rpartition("/")[0]
    query_parts = []
    for parameter in parts.query.split("&"):
        key = unquote(parameter.partition("=")[0])
        if key != "dbname":
            query_parts.append(parameter)
    return urlunsplit(
        (
            parts.scheme,
            parts.netloc,
            f"{parent_path}/{MAINTENANCE_DATABASE}",
            "&".join(query_parts),
            parts.fragment,
        )
    )
