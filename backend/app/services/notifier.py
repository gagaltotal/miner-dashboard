"""
Detects two events worth interrupting the user for, per device, after every
poll cycle:

1. "Best share" record — the device's reported best difficulty exceeds the
   highest value we had previously stored for it. Every adapter reports
   this directly from the device/pool's own accounting (AxeOS: `bestDiff`;
   cgminer-family: `Best Share`; Braiins: pool `best_share`), so this needs
   no external data at all.

2. "Block found" — for AxeOS-family devices this is exact: AxeOS itself
   tracks a `blockFound` counter (it knows the current network difficulty
   from the stratum job and compares locally), so we just watch that
   counter increment — no external network-difficulty lookup, no outbound
   call, nothing that conflicts with the "no cloud" requirement. Other
   adapters do not currently surface an equivalent signal, so for those
   this notification simply won't fire; we do not fake it or call out to an
   external block-explorer API to approximate it, since that would mean
   this app phoning a third party without being asked to. If the user later
   wants that for a solo cgminer/Braiins setup, the clean way to keep it
   fully local is to have this service call the user's own Bitcoin Core
   node's RPC for `getblockchaininfo` — deliberately left as a documented
   extension point rather than an always-on network call.
"""
from __future__ import annotations

import logging

from app.adapters.base import DeviceMetrics
from app.db.database import Database
from app.db import queries
from app.services.connection_manager import manager

logger = logging.getLogger("miner_dashboard.notifier")


async def check_and_notify(db: Database, device_id: str, device_name: str, previous_best_diff: float, previous_blocks: int, metrics: DeviceMetrics) -> None:
    if metrics.best_diff is not None and metrics.best_diff > previous_best_diff and previous_best_diff > 0:
        note = await queries.insert_notification(
            db, device_id, "best_share",
            f"{device_name} mencatatkan rekor share terbaik baru: {_format_diff(metrics.best_diff)}",
        )
        await manager.broadcast({"type": "notification", "notification": _serialize(note)})

    if metrics.blocks_found is not None and metrics.blocks_found > previous_blocks and previous_blocks >= 0 and previous_blocks is not None:
        if previous_blocks > 0 or metrics.blocks_found > 0:
            note = await queries.insert_notification(
                db, device_id, "block_found",
                f"🎉 {device_name} kemungkinan menemukan BLOK! Segera periksa perangkat dan pool Anda.",
            )
            await manager.broadcast({"type": "notification", "notification": _serialize(note)})


def _serialize(note: dict) -> dict:
    return {
        "id": note["id"],
        "device_id": note["device_id"],
        "kind": note["kind"],
        "message": note["message"],
        "ts": note["ts"],
        "read": bool(note.get("read", False)),
    }


def _format_diff(value: float) -> str:
    for suffix, threshold in (("T", 1e12), ("G", 1e9), ("M", 1e6), ("K", 1e3)):
        if value >= threshold:
            return f"{value / threshold:.2f}{suffix}"
    return f"{value:.0f}"
