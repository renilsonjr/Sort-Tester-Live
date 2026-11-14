import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend import http_hardening, origin_guard
from backend.auth.rate_limit import RegistrationLimiter
from backend.routers import auth, ranked

# The repository root holds index.html, src/ and assets/.
FRONTEND_ROOT = Path(__file__).resolve().parent.parent


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
    application = FastAPI(
        docs_url="/docs" if docs else None,
        redoc_url="/redoc" if docs else None,
        openapi_url="/openapi.json" if docs else None,
    )
    # one sign-up limiter per application instance (owner caps: 30/hour per
    # address, 200/day in total)
    application.state.registration_limiter = RegistrationLimiter()

    # Added first so it sits innermost: CORS still answers preflight, and the
    # guard only ever sees a real write.
    origin_guard.install(
        application,
        app_origin=os.environ.get("SORT_TESTER_APP_ORIGIN", "").strip(),
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

    application.include_router(auth.router)
    application.include_router(ranked.router)

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    # Same-origin frontend: serve ONLY this allowlist (the home page and the
    # src/ and assets/ folders), never the repository root. Registered after
    # the API so /api and /health always win.
    index_page = FRONTEND_ROOT / "index.html"

    @application.get("/", include_in_schema=False)
    def home() -> FileResponse:
        return FileResponse(index_page, media_type="text/html")

    for folder in ("src", "assets"):
        application.mount(f"/{folder}", StaticFiles(directory=FRONTEND_ROOT / folder), name=folder)

    return application


app = create_app()
