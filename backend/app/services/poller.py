"""
Background polling loop: the heart of the dashboard's "keep everything
local" design. Every `POLL_INTERVAL_SECONDS`, we fetch fresh metrics from
every configured device concurrently, persist a sample, run the
best-share/block-found and overheat-safety checks, and broadcast the new
state to every connected browser tab over WebSocket.

Each device fetch has its own timeout and its own try/except: one
unreachable or slow miner must never stall or crash the polling of every
other device.
"""
from __future__ import annotations

import asyncio
import logging
import time

from app.adapters.base import AdapterError
from app.adapters.registry import build_adapter
from app.config import settings
from app.db import queries
from app.db.database import Database
from app.models.schemas import DeviceKind
from app.services import autotune, notifier
from app.services.connection_manager import manager

logger = logging.getLogger("miner_dashboard.poller")


async def poll_device_once(db: Database, device: dict) -> dict:
    """Poll a single device row, persist the result, run notification/safety
    checks, and return a JSON-serializable status dict for broadcasting."""
    device_id = device["id"]
    kind = DeviceKind(device["kind"])
    adapter = build_adapter(
        kind, device["host"], device["port"],
        username=device.get("username"), password=device.get("password"),
        timeout=settings.DEVICE_TIMEOUT_SECONDS,
    )
    try:
        metrics = await asyncio.wait_for(adapter.fetch_metrics(), timeout=settings.DEVICE_TIMEOUT_SECONDS + 1)
    except (AdapterError, asyncio.TimeoutError, Exception) as exc:  # noqa: BLE001 — a bad device must never kill the poller
        await queries.upsert_device_state(db, device_id, online=False, last_error=str(exc)[:500], latest=None)
        logger.info("Poll failed for %s (%s): %s", device.get("name"), device_id, exc)
        payload = {"id": device_id, "online": False, "last_error": str(exc)[:500]}
        await manager.broadcast({"type": "device_update", "device": payload})
        return payload
    finally:
        await adapter.aclose()

    previous = await queries.get_device(db, device_id) or {}
    previous_best = float(previous.get("best_diff") or 0)
    previous_blocks = int(previous.get("blocks_found") or 0)

    latest_json = {
        "hashrate_ghs": metrics.hashrate_ghs,
        "temp_c": metrics.temp_c,
        "temp_secondary_c": metrics.temp_secondary_c,
        "fan_percent": metrics.fan_percent,
        "fan_rpm": metrics.fan_rpm,
        "power_w": metrics.power_w,
        "efficiency_j_th": metrics.efficiency_j_th,
        "shares_accepted": metrics.shares_accepted,
        "shares_rejected": metrics.shares_rejected,
        "best_diff": metrics.best_diff,
        "uptime_s": metrics.uptime_s,
        "pool_url": metrics.pool_url,
        "firmware_version": metrics.firmware_version,
        "model": metrics.model,
        "autofan_enabled": metrics.autofan_enabled,
        "target_temp_c": metrics.target_temp_c,
        "mining_paused": metrics.mining_paused,
        "raw": metrics.raw,
    }
    await queries.upsert_device_state(
        db, device_id, online=True, last_error=None, latest=latest_json,
        best_diff=metrics.best_diff, blocks_found=metrics.blocks_found,
    )
    await queries.insert_sample(db, device_id, {
        "ts": time.time(),
        "hashrate_ghs": metrics.hashrate_ghs,
        "temp_c": metrics.temp_c,
        "fan_percent": metrics.fan_percent,
        "fan_rpm": metrics.fan_rpm,
        "power_w": metrics.power_w,
        "shares_accepted": metrics.shares_accepted,
        "shares_rejected": metrics.shares_rejected,
        "best_diff": metrics.best_diff,
        "uptime_s": metrics.uptime_s,
    })

    await notifier.check_and_notify(db, device_id, device["name"], previous_best, previous_blocks, metrics)
    await autotune.run_safety_check(db, device_id, device["name"], metrics, adapter.capabilities(), adapter)

    payload = {"id": device_id, "online": True, "last_error": None, **latest_json}
    await manager.broadcast({"type": "device_update", "device": payload})
    return payload


async def poll_all_once(db: Database) -> None:
    devices = await queries.list_devices(db)
    if not devices:
        return
    await asyncio.gather(*(poll_device_once(db, d) for d in devices), return_exceptions=True)


async def prune_loop(db: Database) -> None:
    while True:
        try:
            cutoff = time.time() - settings.HISTORY_RETENTION_DAYS * 86400
            removed = await queries.prune_old_samples(db, cutoff)
            if removed:
                logger.info("Pruned %d samples older than %d days", removed, settings.HISTORY_RETENTION_DAYS)
        except Exception:
            logger.exception("Sample pruning failed")
        await asyncio.sleep(6 * 3600)


async def poll_loop(db: Database, stop_event: asyncio.Event) -> None:
    while not stop_event.is_set():
        started = time.monotonic()
        try:
            await poll_all_once(db)
        except Exception:
            logger.exception("Unexpected error in poll loop")
        elapsed = time.monotonic() - started
        delay = max(1.0, settings.POLL_INTERVAL_SECONDS - elapsed)
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=delay)
        except asyncio.TimeoutError:
            pass
