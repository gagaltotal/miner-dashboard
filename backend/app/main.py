"""
Application entry point.

Route registration order matters here: the API routers and the WebSocket
route are registered first, and the catch-all SPA fallback is added last.
Starlette matches routes in registration order, so `/api/...` and `/ws`
requests are always handled by their explicit handlers and can never be
shadowed by the SPA catch-all — see the request_evaluation notes in
`_spa_fallback` for the path-traversal guard on the other half of that
route.
"""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import FastAPI, HTTPException, status
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.staticfiles import StaticFiles

from app.api.routes.auth import router as auth_router
from app.api.routes.devices import notifications_router, router as devices_router
from app.api.routes.settings_routes import router as settings_router
from app.api.routes.ws import router as ws_router
from app.config import settings
from app.db.database import db
from app.security.middleware import BodySizeLimitMiddleware, CSRFMiddleware, SecurityHeadersMiddleware
from app.services.poller import poll_loop, prune_loop

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("miner_dashboard")

_stop_event = asyncio.Event()
_background_tasks: list[asyncio.Task] = []


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    await db.connect()
    _stop_event.clear()
    _background_tasks.append(asyncio.create_task(poll_loop(db, _stop_event)))
    _background_tasks.append(asyncio.create_task(prune_loop(db)))
    logger.info("Miner dashboard backend started, polling every %.0fs", settings.POLL_INTERVAL_SECONDS)
    try:
        yield
    finally:
        _stop_event.set()
        for task in _background_tasks:
            task.cancel()
        for task in _background_tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await db.close()


app = FastAPI(title="Local Miner Dashboard", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)

# Order: body-size guard first (reject oversized requests before anything
# else touches them), then CSRF, then security headers applied to whatever
# response comes back (including error responses from the two above).
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(CSRFMiddleware, exempt_paths={"/api/auth/login", "/api/auth/setup"})
app.add_middleware(BodySizeLimitMiddleware)

app.include_router(auth_router)
app.include_router(devices_router)
app.include_router(notifications_router)
app.include_router(settings_router)
app.include_router(ws_router)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    # Never leak internals (stack traces, file paths) in error responses —
    # HTTPException.detail is always something a route author set
    # deliberately, so it's safe to return as-is.
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers=getattr(exc, "headers", None))


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc: Exception):
    logger.exception("Unhandled exception while processing %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error"}, status_code=500)


# --- Static frontend (built React app) served from the same origin as the
# API — this is what removes the need for CORS entirely, since the browser
# never sees this as a cross-origin request. ---------------------------

_FRONTEND_DIST = settings.FRONTEND_DIST
_ASSETS_DIR = _FRONTEND_DIST / "assets"

if _ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=str(_ASSETS_DIR)), name="assets")


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    """
    Serve the built SPA for any path not already matched by an API route or
    the /assets mount above.

    Path-traversal guard: `full_path` is attacker-influenced (it's the raw
    request path), so we resolve the candidate file and require it to still
    be located inside `_FRONTEND_DIST` before ever serving it. Without this
    check, a request like `/../../../../etc/passwd` could otherwise escape
    the intended directory — this is exactly the LFI class of bug the
    project explicitly asked to be closed off.
    """
    index_path = _FRONTEND_DIST / "index.html"
    if not index_path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Frontend build not found. Run the frontend build first.")

    if full_path:
        base = _FRONTEND_DIST.resolve()
        candidate = (_FRONTEND_DIST / full_path).resolve()
        try:
            is_inside = candidate.is_relative_to(base)
        except AttributeError:  # Python <3.9 fallback (not expected here, kept for safety)
            is_inside = str(candidate).startswith(str(base))
        if is_inside and candidate.is_file():
            return FileResponse(candidate)

    return FileResponse(index_path)


def run() -> None:
    """Convenience entry point used by `python -m app.main` / run.sh."""
    import uvicorn

    ssl_kwargs = {}
    if settings.ENABLE_TLS:
        from app.security.tls import ensure_self_signed_cert

        cert_path, key_path = ensure_self_signed_cert()
        ssl_kwargs = {"ssl_certfile": str(cert_path), "ssl_keyfile": str(key_path)}
        logger.info("TLS enabled with a self-signed certificate at %s", cert_path)

    uvicorn.run(app, host=settings.HOST, port=settings.PORT, log_level="info", **ssl_kwargs)


if __name__ == "__main__":
    run()
