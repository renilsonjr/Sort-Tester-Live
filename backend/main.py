import os
import re
from pathlib import Path
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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

    application = FastAPI()
    # one sign-up limiter per application instance (owner caps: 30/hour per
    # address, 200/day in total)
    application.state.registration_limiter = RegistrationLimiter()
    if origins:
        # Development only: allow credentials for auth endpoints on explicit loopback origins.
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-Attempt-Capability"],
            allow_credentials=True,
        )

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
