"""
Authentication endpoints.

The dashboard has exactly one local operator account (this is a
single-user home tool, not a multi-tenant service) created on first run via
`POST /api/auth/setup`. Every response that establishes or clears a session
sets the session cookie as HttpOnly + SameSite=Strict (+ Secure when TLS is
on) so it is never readable from page JavaScript and is never attached to
cross-site requests by the browser — the primary defense against session
theft via XSS and against CSRF, respectively. See security/middleware.py
for the belt-and-suspenders CSRF token check layered on top.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status

from app.config import settings
from app.db import queries
from app.db.database import db
from app.models.schemas import ChangePasswordRequest, LoginRequest, SetupRequest
from app.security.auth import hash_password, issue_token, new_csrf_token, verify_password
from app.api.deps import client_key, login_lockout, login_rate_limiter, require_session

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_session_cookies(response: Response, username: str) -> None:
    token = issue_token(username, settings.SESSION_TTL_SECONDS)
    csrf_token = new_csrf_token()
    response.set_cookie(
        settings.COOKIE_NAME, token, max_age=settings.SESSION_TTL_SECONDS,
        httponly=True, samesite="strict", secure=settings.ENABLE_TLS, path="/",
    )
    response.set_cookie(
        settings.CSRF_COOKIE_NAME, csrf_token, max_age=settings.SESSION_TTL_SECONDS,
        httponly=False, samesite="strict", secure=settings.ENABLE_TLS, path="/",
    )


@router.get("/status")
async def auth_status():
    operator = await queries.get_operator(db)
    return {"setup_complete": operator is not None}


@router.post("/setup", status_code=status.HTTP_201_CREATED)
async def setup(body: SetupRequest, response: Response):
    existing = await queries.get_operator(db)
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Setup has already been completed")
    await queries.create_operator(db, body.username, hash_password(body.password))
    _set_session_cookies(response, body.username)
    return {"username": body.username}


@router.post("/login")
async def login(body: LoginRequest, request: Request, response: Response):
    key = client_key(request)
    locked_for = await login_lockout.is_locked(key)
    if locked_for > 0:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts. Try again in {int(locked_for)}s.",
            headers={"Retry-After": str(int(locked_for) + 1)},
        )
    if not await login_rate_limiter.allow(key):
        retry_after = await login_rate_limiter.retry_after(key)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "Too many login attempts",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )

    operator = await queries.get_operator(db)
    # Always run a hash verification, even with no operator row or a
    # username mismatch, using a fixed dummy hash — this keeps response
    # timing indistinguishable from a real wrong-password attempt and avoids
    # leaking (via timing) whether a username exists.
    dummy_hash = "$argon2id$v=19$m=65536,t=3,p=2$AAAAAAAAAAAAAAAAAAAAAA$AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"
    stored_hash = operator["password_hash"] if operator else dummy_hash
    password_ok = verify_password(body.password, stored_hash)
    username_ok = bool(operator) and operator["username"] == body.username

    if not (operator and username_ok and password_ok):
        await login_lockout.record_failure(key)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid username or password")

    await login_lockout.record_success(key)
    _set_session_cookies(response, operator["username"])
    return {"username": operator["username"]}


@router.post("/logout")
async def logout(response: Response, _: str = Depends(require_session)):
    response.delete_cookie(settings.COOKIE_NAME, path="/")
    response.delete_cookie(settings.CSRF_COOKIE_NAME, path="/")
    return {"ok": True}


@router.get("/me")
async def me(username: str = Depends(require_session)):
    return {"username": username}


@router.put("/password")
async def change_password(body: ChangePasswordRequest, username: str = Depends(require_session)):
    operator = await queries.get_operator(db)
    if not operator or not verify_password(body.current_password, operator["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Current password is incorrect")
    await queries.update_operator_password(db, hash_password(body.new_password))
    return {"ok": True}
