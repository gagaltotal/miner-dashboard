"""
ASGI middleware for cross-cutting security concerns:

- Security response headers (CSP, X-Content-Type-Options, X-Frame-Options,
  Referrer-Policy, Permissions-Policy). Applied to *every* response,
  including error responses, so a misconfigured route can never ship
  without them.
- CSRF protection for state-changing requests. We serve the frontend and API
  from the same origin (see main.py), which already removes most CSRF risk,
  but we add a belt-and-suspenders double-submit check: the session cookie
  is `SameSite=Strict` (browsers simply will not attach it cross-site) and
  mutating requests must additionally echo a CSRF token — read from a
  non-httpOnly cookie into a custom request header — that a third-party
  site cannot read or forge because of the same-origin policy.
- A hard cap on request body size, to stop trivial memory-exhaustion DoS via
  oversized JSON payloads.
"""
from __future__ import annotations

import hmac

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from app.config import settings

_SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "same-origin"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=(), usb=(), payment=()"
        )
        # Notification permission is intentionally left off the block list —
        # the dashboard uses it (with an explicit user gesture) for best
        # share / block-found alerts.
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "font-src 'self'; "
            "connect-src 'self' ws: wss:; "
            "object-src 'none'; "
            "base-uri 'self'; "
            "frame-ancestors 'none'; "
            "form-action 'self'"
        )
        if settings.ENABLE_TLS:
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        # Don't help an attacker fingerprint the stack.
        if "server" in response.headers:
            del response.headers["server"]
        return response


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                if int(content_length) > settings.MAX_BODY_BYTES:
                    return JSONResponse({"detail": "Request body too large"}, status_code=413)
            except ValueError:
                pass
        return await call_next(request)


class CSRFMiddleware(BaseHTTPMiddleware):
    """
    Require a valid double-submit CSRF token on every mutating request that
    carries a session cookie. Requests with no session cookie (e.g. the
    login endpoint itself) are exempt since there is no session to forge
    actions against yet.
    """

    def __init__(self, app, exempt_paths: set[str] | None = None) -> None:
        super().__init__(app)
        self.exempt_paths = exempt_paths or set()

    async def dispatch(self, request: Request, call_next):
        if request.method in _SAFE_METHODS or request.url.path in self.exempt_paths:
            return await call_next(request)

        session_cookie = request.cookies.get(settings.COOKIE_NAME)
        if not session_cookie:
            # No session -> nothing to protect yet; the route itself will
            # reject as unauthenticated if it needs a session.
            return await call_next(request)

        cookie_token = request.cookies.get(settings.CSRF_COOKIE_NAME, "")
        header_token = request.headers.get(settings.CSRF_HEADER_NAME, "")
        if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
            return JSONResponse({"detail": "Missing or invalid CSRF token"}, status_code=403)

        return await call_next(request)
