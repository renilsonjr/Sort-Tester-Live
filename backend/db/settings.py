"""Environment-only connection settings for test database tooling."""
import os
from urllib.parse import unquote, urlsplit, urlunsplit

import psycopg
from psycopg.conninfo import conninfo_to_dict

ENV_VAR = "SORT_TESTER_TEST_DATABASE_URL"
APP_ENV_VAR = "SORT_TESTER_DATABASE_URL"
SCRATCH_DB_NAME = "sort_tester_unittest_scratch"
MAINTENANCE_DATABASE = "postgres"

DB_AUTH_ENV_VAR = "SORT_TESTER_DB_AUTH"
DB_IDENTITY_CLIENT_ID_ENV_VAR = "SORT_TESTER_DB_IDENTITY_CLIENT_ID"
PASSWORD_MODE = "password"
MANAGED_IDENTITY_MODE = "managed_identity"
_DB_AUTH_MODES = (PASSWORD_MODE, MANAGED_IDENTITY_MODE)


class DatabaseConfigError(Exception):
    """Raised when the test database connection setting is unset or malformed."""


def db_auth_mode() -> str:
    """Which runtime authentication mode the app uses.

    Defaults to password so development and CI need no new variable. An
    unknown value stops startup rather than guessing (audit #84).
    """
    raw = os.environ.get(DB_AUTH_ENV_VAR, "").strip()
    if not raw:
        return PASSWORD_MODE
    if raw not in _DB_AUTH_MODES:
        raise DatabaseConfigError(
            f"{DB_AUTH_ENV_VAR} must be one of {', '.join(_DB_AUTH_MODES)}; "
            f"got {raw!r}."
        )
    return raw


# libpq's own default is "prefer", which falls back to an unencrypted
# connection without saying so. Only the modes that actually keep TLS are
# accepted; "require" encrypts but does not check who answered, so it is
# the floor rather than the goal (audit M-4).
VERIFYING_SSLMODES = ("require", "verify-ca", "verify-full")
LOOPBACK_HOSTS = ("localhost", "127.0.0.1", "::1")


def _is_loopback(parameters) -> bool:
    """Whether this DSN reaches a database on this same machine.

    A loopback connection never crosses a network, so there is nothing on
    the wire to read and no certificate anyone could present. Requiring
    one would only mean the app could not be run locally at all.
    """
    host = (parameters.get("host") or "").strip().strip("[]")
    return host in LOOPBACK_HOSTS


def _require_verified_tls(url: str, env_var: str) -> None:
    """Refuse a DSN that would reach a remote database without verified TLS."""
    try:
        parameters = conninfo_to_dict(url)
    except (psycopg.Error, ValueError):
        return  # malformed: the caller's own validation reports it
    if _is_loopback(parameters):
        return
    sslmode = (parameters.get("sslmode") or "").strip()
    if sslmode in VERIFYING_SSLMODES:
        return
    raise DatabaseConfigError(
        f"{env_var} must set sslmode to one of "
        f"{', '.join(VERIFYING_SSLMODES)} (verify-full is the one that also "
        "checks the server's certificate). Without it libpq defaults to "
        "'prefer' and will quietly connect without encryption."
    )


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
    _require_verified_tls(url, ENV_VAR)
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
    if not url.startswith("postgresql://"):
        raise DatabaseConfigError(
            f"{APP_ENV_VAR} must be a valid postgresql:// URL when set."
        )
    _require_verified_tls(url, APP_ENV_VAR)
    return url


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
