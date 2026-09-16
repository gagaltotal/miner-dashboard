"""
Device CRUD, discovery, history, and control.

Server-side enforcement for controls (this is what actually stops a
tampered/replayed request from doing something the UI would normally
prevent — the frontend hiding a button is not a security control):

1. Every device is stamped `read_only` at creation time based on its kind
   (`registry.READ_ONLY_KINDS`) and that stamp is checked again on every
   control request, independent of what the adapter reports.
2. The adapter's own `capabilities()` is checked before dispatching any
   control call, so e.g. a `fan` request against an Avalon Nano (which
   supports no fan API) is rejected with a clear 409, not silently
   attempted.
3. All numeric bounds (fan percent 0-100, target temp 30-90) are enforced
   by Pydantic (see models/schemas.py) before this code ever runs.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends, HTTPException, status

from app.adapters.base import AdapterError, NotSupportedError
from app.adapters.registry import READ_ONLY_KINDS, build_adapter, default_port
from app.api.deps import enforce_api_rate_limit, enforce_control_rate_limit, require_session
from app.config import settings
from app.db import queries
from app.db.database import db
from app.discovery.scanner import scan_lan
from app.models.schemas import (
    ActionRequest, AutotuneRequest, DeviceCreate, DeviceKind, DeviceRename,
    FanControlRequest, HistoryRange, MarkReadRequest,
)
from app.security.netsafety import UnsafeTargetError, assert_safe_target

router = APIRouter(prefix="/api/devices", tags=["devices"], dependencies=[Depends(require_session), Depends(enforce_api_rate_limit)])

_RANGE_SECONDS: dict[str, int] = {"1h": 3600, "24h": 86400, "7d": 7 * 86400, "30d": 30 * 86400}


def _to_device_out(row: dict) -> dict:
    import json as _json

    latest = _json.loads(row.get("latest_json") or "{}")
    kind = DeviceKind(row["kind"])
    read_only = bool(row["read_only"]) or kind in READ_ONLY_KINDS
    adapter_caps = build_adapter(kind, row["host"], row["port"]).capabilities()
    capabilities = {
        "fan_control": adapter_caps.fan_control and not read_only,
        "autotune": adapter_caps.autotune and not read_only,
        "restart": adapter_caps.restart and not read_only,
        "pause_resume": adapter_caps.pause_resume and not read_only,
        "identify": adapter_caps.identify and not read_only,
    }
    return {
        "id": row["id"],
        "kind": kind,
        "name": row["name"],
        "host": row["host"],
        "port": row["port"],
        "read_only": read_only,
        "online": bool(row.get("online")),
        "last_seen": row.get("last_seen"),
        "last_error": row.get("last_error"),
        "capabilities": capabilities,
        "metrics": latest,
        "autotune_enabled": bool(row.get("autotune_enabled")),
        "target_temp_c": row.get("target_temp_c"),
        "manual_fan_percent": row.get("manual_fan_percent"),
        "best_diff": float(row.get("best_diff") or 0),
        "blocks_found": int(row.get("blocks_found") or 0),
    }


@router.get("")
async def list_devices():
    rows = await queries.list_devices(db)
    return [_to_device_out(r) for r in rows]


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_device(body: DeviceCreate):
    port = body.port or default_port(body.kind)
    try:
        assert_safe_target(body.host)
    except UnsafeTargetError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

    read_only = body.kind in READ_ONLY_KINDS
    extra = {}
    if body.username:
        extra["username"] = body.username
    if body.password:
        extra["password"] = body.password

    device_id = await queries.insert_device(db, body.kind.value, body.name, body.host, port, read_only, extra)
    row = await queries.get_device(db, device_id)
    return _to_device_out(row)


@router.get("/discovery/scan")
async def discover(_: None = None):
    hits = await scan_lan()
    return [
        {"kind": h.kind, "host": h.host, "port": h.port, "suggested_name": h.suggested_name, "fingerprint": h.fingerprint}
        for h in hits
    ]


@router.get("/{device_id}")
async def get_device(device_id: str):
    row = await queries.get_device(db, device_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return _to_device_out(row)


@router.patch("/{device_id}")
async def rename_device(device_id: str, body: DeviceRename):
    row = await queries.get_device(db, device_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    await queries.rename_device(db, device_id, body.name)
    row = await queries.get_device(db, device_id)
    return _to_device_out(row)


@router.delete("/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_device(device_id: str):
    row = await queries.get_device(db, device_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    await queries.delete_device(db, device_id)


@router.get("/{device_id}/history")
async def device_history(device_id: str, range: HistoryRange = "24h"):  # noqa: A002 — matches the query param name
    row = await queries.get_device(db, device_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    window = _RANGE_SECONDS.get(range, 86400)
    since = time.time() - window
    points = await queries.get_history(db, device_id, since, max_points=500)
    return {"range": range, "points": points}


async def _load_device_and_adapter(device_id: str):
    row = await queries.get_device(db, device_id)
    if not row:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    kind = DeviceKind(row["kind"])
    read_only = bool(row["read_only"]) or kind in READ_ONLY_KINDS
    if read_only:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This device is monitored in read-only mode and cannot be controlled")

    import json as _json
    extra = _json.loads(row.get("extra_json") or "{}")
    adapter = build_adapter(
        kind, row["host"], row["port"], username=extra.get("username"), password=extra.get("password"),
        timeout=settings.DEVICE_TIMEOUT_SECONDS,
    )
    return row, adapter


@router.post("/{device_id}/fan", dependencies=[Depends(enforce_control_rate_limit)])
async def control_fan(device_id: str, body: FanControlRequest):
    row, adapter = await _load_device_and_adapter(device_id)
    caps = adapter.capabilities()
    if not caps.fan_control:
        raise HTTPException(status.HTTP_409_CONFLICT, "This device does not support fan control")
    try:
        await adapter.set_fan(body.mode, body.manual_percent)
    except NotSupportedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    finally:
        await adapter.aclose()
    await queries.update_device_settings(
        db, device_id,
        manual_fan_percent=body.manual_percent if body.mode.value == "manual" else None,
    )
    return {"ok": True}


@router.post("/{device_id}/autotune", dependencies=[Depends(enforce_control_rate_limit)])
async def control_autotune(device_id: str, body: AutotuneRequest):
    row, adapter = await _load_device_and_adapter(device_id)
    caps = adapter.capabilities()
    if not caps.autotune:
        raise HTTPException(status.HTTP_409_CONFLICT, "This device does not support automatic temperature control")
    target = body.target_temp_c
    if target is not None and not (settings.AUTOTUNE_MIN_TARGET_C <= target <= settings.AUTOTUNE_MAX_TARGET_C):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"target_temp_c must be between {settings.AUTOTUNE_MIN_TARGET_C:.0f} and {settings.AUTOTUNE_MAX_TARGET_C:.0f}",
        )
    try:
        await adapter.set_autotune(body.enabled, target)
    except NotSupportedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    finally:
        await adapter.aclose()
    await queries.update_device_settings(db, device_id, autotune_enabled=body.enabled, target_temp_c=target)
    return {"ok": True}


@router.post("/{device_id}/action", dependencies=[Depends(enforce_control_rate_limit)])
async def control_action(device_id: str, body: ActionRequest):
    row, adapter = await _load_device_and_adapter(device_id)
    caps = adapter.capabilities()
    allowed = {
        "restart": caps.restart,
        "pause": caps.pause_resume,
        "resume": caps.pause_resume,
        "identify": caps.identify,
    }
    if not allowed.get(body.action.value, False):
        raise HTTPException(status.HTTP_409_CONFLICT, f"This device does not support '{body.action.value}'")
    try:
        await adapter.perform_action(body.action)
    except NotSupportedError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    except AdapterError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc
    finally:
        await adapter.aclose()
    return {"ok": True}


notifications_router = APIRouter(prefix="/api/notifications", tags=["notifications"], dependencies=[Depends(require_session), Depends(enforce_api_rate_limit)])


@notifications_router.get("")
async def list_notifications():
    rows = await queries.list_notifications(db)
    return [
        {"id": r["id"], "device_id": r["device_id"], "kind": r["kind"], "message": r["message"], "ts": r["ts"], "read": bool(r["read"])}
        for r in rows
    ]


@notifications_router.post("/mark-read")
async def mark_read(body: MarkReadRequest):
    await queries.mark_notifications_read(db, body.ids)
    return {"ok": True}
