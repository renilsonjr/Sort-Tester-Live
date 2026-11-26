import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import psycopg
from psycopg_pool import PoolTimeout

from backend import http_hardening, origin_guard
from backend.db import settings as db_settings
from backend.db.entra_token import TokenUnavailable
from backend.auth import deletion_list, settings as auth_settings
from backend.auth.rate_limit import AddressAttemptLimiter, RegistrationLimiter
from backend.auth.verification_gate import VerificationBusy
from backend.sweep_interval import SweepInterval
from backend.ranked import engine as ranked_engine
from backend.routers import auth, handler as handler_router, ranked, recovery_messages as recovery_messages_router

# The repository root holds index.html, src/ and assets/.
FRONTEND_ROOT = Path(__file__).resolve().parent.parent


class RevalidatedStatic(StaticFiles):
    """``src/`` and ``assets/``, with the same "ask me first" instruction
    the home page already carries.

    Until #462 these were served with an ETag and no Cache-Control at all,
    so each browser invented its own freshness window and a returning
    phone could go on running code from weeks before. The design meant to
    prevent that was a version tag in the URL -- ``src/app.js?v=...`` --
    and it failed in the plainest way: nobody changed the tag. On
    2026-11-25 the tags in index.html read ``20261121`` with sixty-two
    commits to ``src/`` since, and the tags app.js uses for its OWN
    imports read ``20261108``. chart.js was behind that second one, which
    is where the routing answers live: a player could be taught NJ 078 9
    goes to RED, three weeks after it was corrected to GOLD, with nothing
    on screen to say the code was stale.

    A tag only works if a human remembers to change it, and this is the
    evidence that they do not. ``no-cache`` asks the server instead, and
    the ETag turns an unchanged file into a 304 that costs nothing -- so
    the browser still stores everything, and a deploy always lands.
    """

    def file_response(self, *args, **kwargs):  # type: ignore[override]
        response = super().file_response(*args, **kwargs)
        response.headers["cache-control"] = "no-cache"
        return response


def create_app() -> FastAPI:
    configured = os.environ.get("SORT_TEST_DEV_ORIGINS", "").strip()
    origins = [value.strip() for value in configured.split(",")] if configured else []
    for origin in origins:
        if not re.fullmatch(r"https?://(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(?::[0-9]{1,5})?", origin):
            raise ValueError("SORT_TEST_DEV_ORIGINS must contain explicit HTTP(S) origins without paths or wildcards")
        # urlsplit also rejects invalid IPv6 addresses and out-of-range ports.
        urlsplit(origin).port

    # The generated API docs list every route, owner and admin ones included,
    # so they exist only where a developer asks for them.
    docs = os.environ.get("SORT_TESTER_API_DOCS", "").strip() == "1"
    @asynccontextmanager
    async def lifespan(_application: FastAPI):
        # The moment this server came up. An attempt found silent since
        # before it, with nothing showing the server alive after its grace
        # ran out, was cut off by the restart and not by its player (issue
        # #13, box 3). Set here and not at import, so only a server that is
        # really running claims to have started.
        ranked_engine.set_process_started_at(datetime.now(timezone.utc))
        try:
            yield
        finally:
            ranked_engine.set_process_started_at(None)

    application = FastAPI(
        lifespan=lifespan,
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    # one sign-up limiter per application instance (owner caps: 30/hour per
    # address, 200/day in total)
    application.state.registration_limiter = RegistrationLimiter()
    # recovery messages from the sign-in screen (#251, owner caps: 3/hour
    # per address, 50/day in total); the same sliding-window rule
    application.state.recovery_message_limiter = RegistrationLimiter(
        per_client=3, per_client_window=3600.0, total=50, total_window=86400.0
    )

    # retention deletes what is days old: once a minute, not on every request
    application.state.retention_interval = SweepInterval()
    # failed Quiz Code checks from one address (owner cap: 20 in 5 minutes)
    application.state.address_attempt_limiter = AddressAttemptLimiter()

    app_origin = os.environ.get("SORT_TESTER_APP_ORIGIN", "").strip()

    # An insecure session cookie on an https origin is invisible from the
    # app and discovered on the wire. Checked here so a deployment that
    # forgot the flag fails to start instead of serving quietly.
    auth_settings.check_cookie_policy(
        cookie_secure=auth_settings.get_auth_settings().cookie_secure,
        app_origin=app_origin,
    )

    # A hosted deployment that forgot the deletion list would accept
    # deletions a restore silently undoes; it fails to start instead (#13).
    deletion_list.check_policy(db_auth_mode=db_settings.db_auth_mode())

    # Added first so it sits innermost: CORS still answers preflight, and the
    # guard only ever sees a real write.
    origin_guard.install(
        application,
        app_origin=app_origin,
        dev_origins=origins,
    )

    if origins:
        # Development only: allow credentials for auth endpoints on explicit loopback origins.
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Attempt-Capability"],
            allow_credentials=True,
        )

    # Added after the guard and CORS so it is outermost: its headers and the
    # body cap apply to every answer, refusals and preflight included.
    http_hardening.install(application)

    # Outermost of all, so it compresses whatever the others answer. The
    # app serves its own frontend, and until 2026-11-26 every byte of it
    # went out raw: opening the site cost 904 KB, most of it text that
    # compresses to about a quarter. ETags are untouched, so the
    # ask-before-reusing rule from #462 still answers 304 with no body.
    application.add_middleware(GZipMiddleware, minimum_size=1024)

    application.include_router(auth.router)
    application.include_router(recovery_messages_router.router)
    application.include_router(ranked.router)
    application.include_router(handler_router.router)

    @application.exception_handler(TokenUnavailable)
    @application.exception_handler(PoolTimeout)
    def _database_unavailable(_request: Request, _exc: Exception) -> JSONResponse:
        # No token or DSN is read from the exception, so nothing secret can
        # reach the client or the log. A request that needs a *new*
        # connection while none can be made gets this; healthy pooled
        # connections keep serving (audit #84).
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "database temporarily unavailable"},
        )

    @application.exception_handler(VerificationBusy)
    def _verification_busy(_request: Request, _exc: Exception) -> JSONResponse:
        # Too many Quiz Code checks were already under way. This one never
        # started, so nothing changed and it can simply be sent again.
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"detail": "busy; try again in a moment"},
            headers={"Retry-After": "5"},
        )

    @application.exception_handler(psycopg.DataError)
    def _bad_data(_request: Request, _exc: Exception) -> JSONResponse:
        # A value the database cannot store (a character it has no room
        # for, a number out of range) is the request's fault, not the
        # server's. Nothing from the exception is echoed back.
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": "Invalid input."},
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        # The version rides on the one route that needs no session, because
        # the Profile screen and an uptime check both read it (#274). Nothing
        # else goes here: no commit, no host, no database name.
        from backend.version import VERSION

        return {"status": "ok", "version": VERSION}

    # Same-origin frontend: serve ONLY this allowlist (the home page and the
    # src/ and assets/ folders), never the repository root. Registered after
    # the API so /api and /health always win.
    index_page = FRONTEND_ROOT / "index.html"

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        # `no-cache` means "ask me first", not "never store": the browser
        # keeps the copy and revalidates, and FileResponse's ETag turns a
        # match into a 304 that costs nothing.
        #
        # Without it there is no instruction at all, so each browser
        # invents its own freshness window from the Last-Modified date.
        # That is how a deployment can be live, verified from one machine
        # and still invisible on another -- which happened on 2026-11-18
        # and cost an afternoon of looking in the wrong place.
        #
        # The page carries the whole stylesheet inline, so a stale copy is
        # a stale design. src/ and assets/ used to be left on the default,
        # on the reasoning that "their URLs carry a version tag when they
        # change" -- which held only as long as somebody changed the tag.
        # They did not, for sixty-two commits. See RevalidatedStatic.
        return FileResponse(
            index_page,
            media_type="text/html",
            headers={"cache-control": "no-cache"},
        )

    for folder in ("src", "assets"):
        application.mount(
            f"/{folder}",
            RevalidatedStatic(directory=FRONTEND_ROOT / folder),
            name=folder,
        )

    return application


app = create_app()
