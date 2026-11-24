from contextlib import contextmanager
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from backend.auth.rate_limit import _client_key, _login_rate_key, get_login_rate_limiter
from backend.auth.service import (
    admin_regenerate_login_id,
    check_login_candidates,
    find_login_candidates,
    get_account_by_session,
    open_login_session,
    register_account,
)
from backend.auth.deletion_list import DeletionListUnavailable
from backend.auth.deletion import (
    OwnerAccountError,
    WrongLoginIdError,
    purge_deleted_accounts,
    request_deletion,
)
from backend.auth.sessions import revoke_session
from backend.auth.settings import AuthSettings, get_auth_settings
from backend.db import migrate, pool, settings

router = APIRouter(prefix="/api/auth", tags=["auth"])


@contextmanager
def _db_connection():
    """One pooled connection for this request (audit M-5).

    Opening a connection per request cost a connect to Postgres each time
    and had no ceiling; the pool reuses a capped set and makes a burst
    wait. Commits are still the caller's own: see backend/db/pool.py for
    why that was kept rather than folded into the checkout.
    """
    pool.init_pool(settings.app_database_url(), auth_mode=settings.db_auth_mode())
    with pool.checkout() as conn:
        yield conn


class _CountedCheck:
    failed = False

    def mark_failed(self) -> None:
        self.failed = True


@contextmanager
def _counted_check(request: Request):
    """Count one Quiz Code check against the caller's address.

    Refused with 429 before anything else happens when the address has used
    its allowance (``AddressAttemptLimiter``). The count is kept only if the
    block marks the check as failed; a check that succeeds, or that never
    ran because the request ended some other way, is given back.
    """
    attempts = request.app.state.address_attempt_limiter
    client = _client_key(request)
    if not attempts.reserve(client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests"
        )
    check = _CountedCheck()
    try:
        yield check
    finally:
        if not check.failed:
            attempts.release(client)


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
    # carried here so the profile can draw it without a second request (#272)
    avatar: str | None = None


class AdminRegenerateRequest(BaseModel):
    account_id: str


class AdminRegenerateResponse(BaseModel):
    login_id: str


class AccountResponse(BaseModel):
    account_id: str
    username: str
    tag: str
    is_owner: bool
    # the key of the icon this player chose, or None if they never did (#272)
    avatar: str | None = None


class AvatarRequest(BaseModel):
    # None clears the choice; any other value must be one of the fifteen
    avatar: str | None = None


def _purge_pending_deletions():
    # accepted deletions are purged before any auth request is handled, the
    # same per-request pattern as the season close; one statement when idle
    with _db_connection() as conn:
        purge_deleted_accounts(conn)


# runs before every auth route below
router.dependencies.append(Depends(_purge_pending_deletions))


def _current_account(request: Request):
    raw_token = request.cookies.get("sort_tester_session")
    if not raw_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    with _db_connection() as conn:
        account = get_account_by_session(conn, raw_token)
        # the idle refresh and the idle revocation are writes: without this
        # the close rolls both back, so last_seen_at never leaves the login
        # time and every session dies one idle window later (audit H-1)
        conn.commit()
    if account is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
    return account


@router.post("/register", response_model=RegisterResponse)
def register(request: Request, payload: RegisterRequest):
    limiter = request.app.state.registration_limiter
    client = _client_key(request)
    if not limiter.is_allowed(client):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many sign-ups; try again later",
        )
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
    limiter.record(client)  # only a successful sign-up counts
    return {"account_id": str(account_id), "login_id": login_id}


@router.post("/login", response_model=LoginResponse)
def login(request: Request, response: Response, payload: LoginRequest):
    limiter = get_login_rate_limiter()
    rate_key = _login_rate_key(request, payload.login_id)
    if not limiter.is_allowed(rate_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")

    auth_settings = get_auth_settings()
    with _counted_check(request) as check:
        # Three steps, and no connection held during the middle one: the
        # verification is the slow part, and a connection kept through it
        # is one that nobody else can use.
        with _db_connection() as conn:
            normalized, candidates = find_login_candidates(conn, payload.login_id)
        candidate = check_login_candidates(normalized, candidates)
        if candidate is None:
            check.mark_failed()
            limiter.record_failure(rate_key)
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
        with _db_connection() as conn:
            result = open_login_session(
                conn,
                candidate,
                ttl_seconds=auth_settings.session_ttl_seconds,
                ip_address=None,
                user_agent=None,
            )
            if result is None:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized")
            limiter.record_success(rate_key)
            token, _ = result
            account = get_account_by_session(conn, token)
            conn.commit()
    if account is None:
        # the account can be deleted between creating the session and
        # reading it back; indexing into None here made that a 500 and a
        # traceback for what is simply an unauthenticated request
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Unauthorized"
        )
    response.set_cookie(
        key="sort_tester_session",
        value=token,
        httponly=True,
        secure=auth_settings.cookie_secure,
        samesite="lax",
        path="/",
        max_age=auth_settings.session_ttl_seconds,
    )
    return {
        "account_id": str(account["id"]),
        "username": account["username"],
        "tag": account["tag"],
        "avatar": account["avatar"],
    }


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
        "avatar": account["avatar"],
    }


@router.put("/avatar", status_code=status.HTTP_204_NO_CONTENT)
def set_avatar(
    payload: AvatarRequest,
    account: dict = Depends(_current_account),
):
    """Choose the icon shown on this player's profile and the leaderboard.

    There is no account id in the route: it acts on the session's own
    account and nothing else. The value stored is a key from
    ``backend.auth.avatars``; anything not on that list is refused, so no
    text a player typed can ever reach a screen this way (#272).
    """
    from backend.auth import avatars

    if payload.avatar is not None and not avatars.is_allowed(payload.avatar):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="That is not one of the icons.",
        )
    with _db_connection() as conn:
        migrate.execute(
            conn,
            "UPDATE accounts SET avatar = %s WHERE id = %s AND deleted_at IS NULL",
            (payload.avatar, account["id"]),
        )
        conn.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/admin/regenerate", response_model=AdminRegenerateResponse)
def admin_regenerate(
    payload: AdminRegenerateRequest,
    account: dict = Depends(_current_account),
):
    """Withdrawn: this route reset a login ID on the owner's say-so alone.

    The settled recovery policy requires in-person verification against a
    trusted participant link established **before** the request, and says
    plainly that without such a link there is no reset by this route.
    Being the owner is the authority to act, not evidence about who is
    asking, so this endpoint was short of the rule it was meant to carry.

    Recovery now goes through ``/api/ranked/owner/recoveries``, which
    records the request, refuses when no older link exists, and shows the
    new login ID once. A caller that still reaches here is told where to
    go rather than quietly being served.
    """
    if not account["is_owner"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")
    raise HTTPException(
        status_code=status.HTTP_410_GONE,
        detail=(
            "Access recovery moved to the owner's Access recovery screen,"
            " which checks the in-person roster link this route never did."
        ),
    )


class ReauthenticateRequest(BaseModel):
    login_id: str


@router.post("/reauthenticate", status_code=status.HTTP_204_NO_CONTENT)
def reauthenticate_session(
    request: Request,
    payload: ReauthenticateRequest,
    account: dict = Depends(_current_account),
):
    """Re-enter the login ID on this session (#11 box 5).

    Confirms this device for the owner's sensitive actions for five
    minutes. The login ID is checked against the signed-in account only,
    so this cannot test somebody else's; a wrong one counts as a failed
    login against the same limiter as sign-in, and the refusal is the same
    whatever was wrong with it.
    """
    from backend.auth import reauth
    from backend.ranked.clock import system_clock

    limiter = get_login_rate_limiter()
    rate_key = _login_rate_key(request, payload.login_id)
    if not limiter.is_allowed(rate_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    with _counted_check(request) as check, _db_connection() as conn:
        try:
            reauth.reauthenticate(
                conn,
                request.cookies.get("sort_tester_session") or "",
                payload.login_id,
                clock=system_clock(),
            )
        except reauth.WrongLoginId:
            check.mark_failed()
            limiter.record_failure(rate_key)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="That Quiz Code does not match this account.",
            ) from None
        conn.commit()
    return None


class DeleteAccountRequest(BaseModel):
    login_id: str
    acknowledge: bool = False


@router.post("/sessions/revoke-others")
def revoke_other_sessions(
    request: Request,
    account: dict = Depends(_current_account),
):
    """End every other device signed in to this account, keeping this one.

    Behind the same re-entry gate as the owner's guarded actions: a stolen
    session alone must not be enough to sign the real player out, so the
    Quiz Code is asked for first (#270).
    """
    from backend.auth import reauth
    from backend.auth.sessions import revoke_other_account_sessions
    from backend.ranked.clock import system_clock

    raw_token = request.cookies.get("sort_tester_session") or ""
    with _db_connection() as conn:
        try:
            reauth.require_recent(conn, raw_token, clock=system_clock())
        except reauth.ReauthRequired:
            raise HTTPException(
                status_code=status.HTTP_428_PRECONDITION_REQUIRED,
                detail=(
                    "Re-enter your Quiz Code to continue. It stays confirmed"
                    " on this device for five minutes."
                ),
            ) from None
        session = reauth._session(conn, raw_token)
        ended = revoke_other_account_sessions(conn, account["id"], session["id"])
        conn.commit()
    return {"ended": ended}


@router.post("/account/delete", status_code=status.HTTP_202_ACCEPTED)
def delete_account(
    request: Request,
    response: Response,
    payload: DeleteAccountRequest,
    account: dict = Depends(_current_account),
):
    """Delete the signed-in account. Irreversible once accepted: the account
    is locked out at once and its data is purged. Re-entering the login ID
    is the reauthentication; a wrong one counts as a failed login."""
    if payload.acknowledge is not True:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Acknowledge that deletion cannot be undone",
        )
    limiter = get_login_rate_limiter()
    rate_key = _login_rate_key(request, payload.login_id)
    if not limiter.is_allowed(rate_key):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many requests")
    with _counted_check(request) as check, _db_connection() as conn:
        try:
            request_deletion(conn, account["id"], payload.login_id)
        except WrongLoginIdError:
            check.mark_failed()
            limiter.record_failure(rate_key)
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden") from None
        except OwnerAccountError:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The owner account cannot be deleted",
            ) from None
        except DeletionListUnavailable:
            # the deletion could not be made restore-proof, so it was not
            # accepted: nothing changed and the player can try again (#13)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Deletion is temporarily unavailable. Nothing was changed; try again shortly.",
            ) from None
    response.delete_cookie(key="sort_tester_session", path="/")
    return {"status": "accepted"}
