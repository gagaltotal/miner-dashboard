"""Shared FastAPI dependencies: session enforcement and rate limiting."""
from __future__ import annotations

from fastapi import HTTPException, Request, status

from app.config import settings
from app.security.auth import verify_token
from app.security.rate_limit import LockoutTracker, SlidingWindowRateLimiter

# One limiter per concern, so a burst of read traffic never eats into the
# budget reserved for login attempts or control actions.
login_rate_limiter = SlidingWindowRateLimiter(
    settings.LOGIN_RATE_LIMIT_ATTEMPTS, settings.LOGIN_RATE_LIMIT_WINDOW_SECONDS
)
login_lockout = LockoutTracker(settings.LOGIN_RATE_LIMIT_ATTEMPTS * 3, settings.LOGIN_LOCKOUT_SECONDS)
api_rate_limiter = SlidingWindowRateLimiter(
    settings.API_RATE_LIMIT_REQUESTS, settings.API_RATE_LIMIT_WINDOW_SECONDS
)
control_rate_limiter = SlidingWindowRateLimiter(
    settings.CONTROL_RATE_LIMIT_REQUESTS, settings.CONTROL_RATE_LIMIT_WINDOW_SECONDS
)


def client_key(request: Request) -> str:
    """The real TCP peer address — never a client-supplied header — used as
    the rate-limiting identity."""
    return request.client.host if request.client else "unknown"


async def require_session(request: Request) -> str:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    payload = verify_token(token)
    if payload is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Session expired or invalid")
    return payload.subject


async def enforce_api_rate_limit(request: Request) -> None:
    key = client_key(request)
    if not await api_rate_limiter.allow(key):
        retry_after = await api_rate_limiter.retry_after(key)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many requests",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


async def enforce_control_rate_limit(request: Request) -> None:
    key = client_key(request)
    if not await control_rate_limiter.allow(key):
        retry_after = await control_rate_limiter.retry_after(key)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many control requests",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )
