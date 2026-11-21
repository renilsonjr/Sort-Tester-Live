"""Reject cross-site writes before they reach a route (issue #77).

The session lives in a cookie, so the browser attaches it to any request
another site makes on the player's behalf. A browser always states where
such a request came from, in `Origin` (or, failing that, `Referer`), and
it cannot be forged by the page making the request. So an unsafe method
is served only when that stated origin is one of ours.

Allowed:
- the app's own host (the `Host` header), whatever the scheme — behind an
  ingress that terminates TLS the browser says `https` while the app sees
  a plain `http` request for the same host;
- `SORT_TESTER_APP_ORIGIN`, the public origin, when set -- and when that
  origin is https, only over https: a plain-http page of the same host can
  be supplied by anyone on the network path, so it is not our origin;
- the explicit loopback origins in `SORT_TEST_DEV_ORIGINS`.

A request with neither header is refused too: every current browser sends
one on a write. A script that needs to call the API sends `Origin`.
"""
from urllib.parse import urlsplit

from starlette.responses import JSONResponse

GUARDED_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def _host_of(origin: str) -> str:
    """Return the host:port of *origin*, or "" when it states none."""
    if not origin or origin == "null":
        return ""
    parts = urlsplit(origin)
    # An origin is scheme://host[:port] and nothing else; a path, query or
    # fragment means this is not one, so it states no host we can trust.
    if parts.scheme not in ("http", "https") or not parts.netloc:
        return ""
    if parts.path or parts.query or parts.fragment:
        return ""
    return parts.netloc


def _referer_host(referer: str) -> str:
    """Return the host:port of the page in *referer* (which carries a path)."""
    parts = urlsplit(referer)
    if parts.scheme not in ("http", "https"):
        return ""
    return parts.netloc


def allowed_hosts(request_host: str, app_origin: str, dev_origins) -> set[str]:
    """Hosts a write may claim to come from. Empty entries are dropped.

    The request's own `Host` header used to be in here. Host is set by
    whoever makes the request, so admitting it meant the guard asked the
    caller where they came from and believed the answer: a request
    carrying a matching Origin and Host pair passed, which is the one
    thing this exists to refuse.

    It stays as the fallback only while `app_origin` is unset -- local
    development and a first deployment have no origin to compare against,
    and refusing every write there would be worse than a guard that
    cannot yet do its job.
    """
    configured = _host_of(app_origin)
    hosts = {configured} if configured else {request_host}
    hosts.update(_host_of(origin) for origin in dev_origins)
    hosts.discard("")
    return hosts


def _is_downgraded(stated_url: str, stated_host: str, app_origin: str) -> bool:
    """True when *stated_url* is the plain-http form of an https app origin."""
    configured = urlsplit(app_origin)
    if configured.scheme != "https" or stated_host != configured.netloc:
        return False
    return urlsplit(stated_url).scheme != "https"


def install(application, app_origin: str, dev_origins) -> None:
    """Add the guard to *application*. Safe methods are never touched."""

    @application.middleware("http")
    async def guard_cross_site_writes(request, call_next):
        if request.method not in GUARDED_METHODS:
            return await call_next(request)

        source = request.headers.get("origin", "")
        stated = _host_of(source)
        if not stated:
            # No usable Origin: fall back to the page in Referer.
            source = request.headers.get("referer", "")
            stated = _referer_host(source)

        permitted = allowed_hosts(request.headers.get("host", ""), app_origin, dev_origins)
        if not stated or stated not in permitted or _is_downgraded(source, stated, app_origin):
            # Say nothing about what was sent or what is configured.
            return JSONResponse({"detail": "Cross-site request rejected."}, status_code=403)

        return await call_next(request)
