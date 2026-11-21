"""Response headers and request limits for every route (security sweep, 2026-11-14).

- Fixed security headers on every response, refusals included.
- A content security policy that allows only what the page really loads.
- API answers are never cached.
- Request bodies are capped: the largest legitimate body is a few hundred
  bytes of JSON, so anything large is refused before it is parsed.
"""
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

# The page loads its own modules, styles, fonts and images, plus one pinned
# spreadsheet library. It has a <style> block and a few style attributes, so
# inline styles are allowed; inline scripts are not.
CONTENT_SECURITY_POLICY = "; ".join(
    (
        "default-src 'self'",
        "script-src 'self' https://cdn.sheetjs.com",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "font-src 'self'",
        "connect-src 'self'",
        "frame-ancestors 'none'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
    )
)

SECURITY_HEADERS = {
    # Browsers honour this only over HTTPS; over plain HTTP it is ignored.
    "Strict-Transport-Security": "max-age=31536000",
    "X-Content-Type-Options": "nosniff",
    # Never render this app inside another site's frame (clickjacking).
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "same-origin",
    "Content-Security-Policy": CONTENT_SECURITY_POLICY,
}

MAX_BODY_BYTES = 64 * 1024
BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
UNCACHED_PREFIXES = ("/api/", "/health")


class _BodyTooLarge(Exception):
    """More body arrived than the cap allows."""


class HardeningMiddleware:
    """Plain ASGI, so the body is counted as it streams and never buffered."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        started = False
        uncached = scope["path"].startswith(UNCACHED_PREFIXES)

        async def send_hardened(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                headers = MutableHeaders(scope=message)
                for name, value in SECURITY_HEADERS.items():
                    headers[name] = value
                if uncached:
                    headers["Cache-Control"] = "no-store"
            await send(message)

        async def refuse():
            await JSONResponse({"detail": "Request body too large."}, status_code=413)(
                scope, receive, send_hardened
            )

        if scope["method"] not in BODY_METHODS:
            await self.app(scope, receive, send_hardened)
            return

        declared = Headers(scope=scope).get("content-length")
        if declared is not None and (not declared.isdigit() or int(declared) > MAX_BODY_BYTES):
            await refuse()
            return

        received = 0

        async def counted_receive():
            # A chunked body declares no length, so count what actually arrives.
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > MAX_BODY_BYTES:
                    raise _BodyTooLarge
            return message

        try:
            await self.app(scope, counted_receive, send_hardened)
        except _BodyTooLarge:
            if started:
                raise
            await refuse()


def install(application) -> None:
    """Add the hardening middleware. Call last, so it wraps every other answer."""
    application.add_middleware(HardeningMiddleware)
