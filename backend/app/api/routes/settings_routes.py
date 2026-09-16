"""
Global (non-per-device) settings. Currently this is a thin read/write layer
over values that live in `app.config.settings` for the running process —
changing the poll interval or retention window here takes effect
immediately for the current process without a restart, but (being simple
in-memory values, not persisted to the DB) revert to the `.env` values on
the next restart. The `.env` file remains the source of truth for anyone
who wants a permanent change.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.deps import enforce_api_rate_limit, require_session
from app.config import settings
from app.models.schemas import GlobalSettingsUpdate

router = APIRouter(prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_session), Depends(enforce_api_rate_limit)])


@router.get("")
async def get_settings():
    return {
        "poll_interval_seconds": settings.POLL_INTERVAL_SECONDS,
        "history_retention_days": settings.HISTORY_RETENTION_DAYS,
        "allow_public_targets": settings.ALLOW_PUBLIC_TARGETS,
    }


@router.patch("")
async def update_settings(body: GlobalSettingsUpdate):
    if body.poll_interval_seconds is not None:
        settings.POLL_INTERVAL_SECONDS = body.poll_interval_seconds
    if body.history_retention_days is not None:
        settings.HISTORY_RETENTION_DAYS = body.history_retention_days
    return {
        "poll_interval_seconds": settings.POLL_INTERVAL_SECONDS,
        "history_retention_days": settings.HISTORY_RETENTION_DAYS,
        "allow_public_targets": settings.ALLOW_PUBLIC_TARGETS,
    }
