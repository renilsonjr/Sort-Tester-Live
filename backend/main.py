import os
import re
from urllib.parse import urlsplit

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    configured = os.environ.get("SORT_TEST_DEV_ORIGINS", "").strip()
    origins = [value.strip() for value in configured.split(",")] if configured else []
    for origin in origins:
        if not re.fullmatch(r"https?://(?:[A-Za-z0-9.-]+|\[[0-9A-Fa-f:]+\])(?::[0-9]{1,5})?", origin):
            raise ValueError("SORT_TEST_DEV_ORIGINS must contain explicit HTTP(S) origins without paths or wildcards")
        # urlsplit also rejects invalid IPv6 addresses and out-of-range ports.
        urlsplit(origin).port

    application = FastAPI()
    if origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET"],
            allow_headers=[],
            allow_credentials=False,
        )

    @application.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    return application


app = create_app()
