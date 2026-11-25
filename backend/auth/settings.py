import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class AuthSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SORT_TESTER_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    argon2_time_cost: int = 3
    argon2_memory_cost: int = 65536
    argon2_parallelism: int = 1
    cookie_secure: bool = False
    session_ttl_seconds: int = 8 * 60 * 60
    # A session also ends when it is left alone. The app warns a minute
    # before and signs the player out at the same figure, so the two halves
    # agree; the server's copy is the one that counts, because it is the one
    # a stolen cookie has to get past.
    session_idle_seconds: int = 15 * 60


def get_auth_settings() -> AuthSettings:
    return AuthSettings()


class InsecureCookieError(RuntimeError):
    """Raised at startup rather than discovered on the wire."""


def check_cookie_policy(*, cookie_secure: bool, app_origin: str) -> None:
    """Refuse to serve an https origin with a cookie that is not Secure.

    Without the Secure flag the browser will send the session cookie over
    plain http too, so anything that can make the browser touch an http
    URL on this host gets the token. Nothing about that is visible from
    the app: it works perfectly, right up until someone is on a network
    where it matters.

    The default stays False so local development over http keeps working;
    what the deployment sets is SORT_TESTER_COOKIE_SECURE. This is the
    check that the two agree, and it runs at startup because a setting
    that must be remembered will eventually be forgotten.
    """
    if cookie_secure:
        return
    if app_origin.strip().lower().startswith("https://"):
        raise InsecureCookieError(
            "SORT_TESTER_APP_ORIGIN is an https origin but "
            "SORT_TESTER_COOKIE_SECURE is false: the session cookie would "
            "be sent over plain http as well. Set SORT_TESTER_COOKIE_SECURE=true."
        )
