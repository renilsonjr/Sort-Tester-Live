from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.auth.rate_limit import _client_key, get_login_rate_limiter
from backend.auth.service import (
    admin_regenerate_login_id,
    get_account_by_session,
    login_with_id,
    register_account,
)
from backend.auth.sessions import revoke_session
from backend.auth.settings import AuthSettings, get_auth_settings
from backend.db import migrate, settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@contextmanager
def _db_connection():
    conn = migrate.connect(settings.app_database_url())
    try:
        yield conn
    finally:
        conn.close()


def get_db():
    with _db_connection() as conn:
        yield conn


class RegisterRequest(BaseModel):
    # the accounts table's own rule: 3-24 letters, digits or underscores
    username: str = Field(pattern=r"^[A-Za-z0-9_]{3,24}$")


class RegisterResponse(BaseModel):
    account_id: str
    login_id: str


class LoginRequest(BaseModel):
    login_id: str


class LoginResponse(BaseModel):
    account_id: str
    username: str
    tag: str


class AdminRegenerateRequest(BaseModel):
    account_id: str


class AdminRegenerateResponse(BaseModel):
    login_id: str


class AccountResponse(BaseModel):
    account_id: str
    username: str
    tag: str
    is_owner: bool


def _current_account(request: Request):
    raw_token = request.cookies.get("sort_tester_session")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    with _db_connection() as conn:
        account = get_account_by_session(conn, raw_token)
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return account


@router.post("/register", response_model=RegisterResponse)
def register(payload: RegisterRequest):
    with _db_connection() as conn:
        try:
            account_id, login_id = register_account(conn, payload.username)
        except migrate.IntegrityError:
            # the unique key on username_lower decides, so a race between two
            # sign-ups for one name also ends here, never in a server error
            conn.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Username taken"
            ) from None
        conn.commit()
    return {"account_id": str(account_id), "login_id": login_id}


@router.post("/login", response_model=LoginResponse)
def login(request: Request, response: Response, payload: LoginRequest):
    limiter = get_login_rate_limiter()
    rate_key = _client_key(request)
    if not limiter.is_allowed(rate_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    with _db_connection() as conn:
        auth_settings = get_auth_settings()
        result = login_with_id(
            conn,
            payload.login_id,
            ttl_seconds=auth_settings.session_ttl_seconds,
            ip_address=None,
            user_agent=None,
        )
        if result is None:
            limiter.record_failure(rate_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        limiter.record_success(rate_key)
        token, _ = result
        account = get_account_by_session(conn, token)
        conn.commit()
    response.set_cookie(
        key="sort_tester_session",
        value=token,
        httponly=True,
        secure=auth_settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=auth_settings.session_ttl_seconds,
    )
    return {"account_id": str(account["id"]), "username": account["username"], "tag": account["tag"]}


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, request: Request):
    raw_token = request.cookies.get("sort_tester_session")
    if raw_token:
        with _db_connection() as conn:
            from backend.auth.sessions import authenticate_session

            session = authenticate_session(conn, raw_token)
            if session is not None:
                revoke_session(conn, session["id"])
            conn.commit()
    response.delete_cookie(key="sort_tester_session", path="/")
    return None


@router.get("/me", response_model=AccountResponse)
def me(account: dict = Depends(_current_account)):
    return {
        "account_id": str(account["id"]),
        "username": account["username"],
        "tag": account["tag"],
        "is_owner": account["is_owner"],
    }


@router.post("/admin/regenerate", response_model=AdminRegenerateResponse)
def admin_regenerate(
    payload: AdminRegenerateRequest,
    account: dict = Depends(_current_account),
):
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    with _db_connection() as conn:
        new_login_id = admin_regenerate_login_id(conn, account["id"], UUID(payload.account_id))
        conn.commit()
    if new_login_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return {"login_id": new_login_id}
