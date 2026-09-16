"""
"Automatic, safe temperature control" is implemented as two independent
layers, deliberately not as one PID loop we reimplement ourselves:

1. Native auto mode (the common case): Bitaxe/NerdQaxe (`autofanspeed` +
   `temptarget`) and Braiins OS+ (`cooling/mode: auto` + `target_temperature`)
   already run a closed-loop fan controller *on the device itself*, at a much
   tighter cycle than this dashboard's poll interval could match. Turning
   "autotune" on for these devices (see api/routes/devices.py) simply asks
   the device to enable that native loop with the user's chosen target —
   we get a better controller than we could write, for free, and we are not
   fighting the firmware's own logic by also trying to drive the fan from
   here.

2. This module: an independent safety net that runs after every poll, for
   every device, regardless of whether "autotune" is turned on and
   regardless of whether the device has any fan control at all (this is
   exactly the case for Avalon Nano and LuxOS, where we cannot touch the
   fan but can still protect the hardware). If a device's reported chip
   temperature stays above a hard, operator-configurable ceiling
   (`AUTOTUNE_HARD_CUTOFF_C`, conservative default 88°C) for several
   consecutive polls, and the device supports pausing, we pause mining and
   raise a critical notification. We deliberately do NOT auto-resume once
   temperature drops — an unattended pause/resume oscillation could mask a
   genuinely failed fan and keep re-heating the chip. Resuming is left to
   the operator, after checking the hardware.
"""
from __future__ import annotations

import logging

from app.adapters.base import DeviceCapabilities, DeviceMetrics, MinerAdapter, NotSupportedError
from app.config import settings
from app.db import queries
from app.db.database import Database
from app.models.schemas import MinerAction
from app.services.connection_manager import manager

logger = logging.getLogger("miner_dashboard.autotune")

_CONSECUTIVE_BREACHES_REQUIRED = 2
_breach_counts: dict[str, int] = {}
_already_tripped: set[str] = set()


async def run_safety_check(
    db: Database,
    device_id: str,
    device_name: str,
    metrics: DeviceMetrics,
    capabilities: DeviceCapabilities,
    adapter: MinerAdapter,
) -> None:
    temp = metrics.temp_c
    if temp is None:
        return

    if temp < settings.AUTOTUNE_HARD_CUTOFF_C:
        _breach_counts[device_id] = 0
        if device_id in _already_tripped and temp < settings.AUTOTUNE_HARD_CUTOFF_C - 5:
            # Temperature has recovered with a margin; clear the trip flag so
            # a *future* overheat can trigger a fresh protective pause. This
            # does not resume mining — that stays a manual, deliberate step.
            _already_tripped.discard(device_id)
        return

    _breach_counts[device_id] = _breach_counts.get(device_id, 0) + 1
    if _breach_counts[device_id] < _CONSECUTIVE_BREACHES_REQUIRED:
        return
    if device_id in _already_tripped:
        return

    if not capabilities.pause_resume:
        note = await queries.insert_notification(
            db, device_id, "overheat_warning",
            f"⚠️ {device_name} melebihi suhu aman ({temp:.0f}°C) dan perangkat ini tidak mendukung jeda "
            f"otomatis dari dasbor. Periksa pendinginan segera.",
        )
        await manager.broadcast({"type": "notification", "notification": _serialize(note)})
        _already_tripped.add(device_id)
        return

    try:
        await adapter.perform_action(MinerAction.pause)
        message = (
            f"🛑 {device_name} dijeda otomatis karena suhu mencapai {temp:.0f}°C "
            f"(ambang aman: {settings.AUTOTUNE_HARD_CUTOFF_C:.0f}°C). Periksa kipas/pendinginan, "
            f"lalu lanjutkan penambangan secara manual dari dasbor setelah aman."
        )
    except NotSupportedError:
        message = f"⚠️ {device_name} melebihi suhu aman ({temp:.0f}°C) tetapi gagal dijeda otomatis."
    except Exception as exc:  # adapter/network failure — still alert, never crash the poller
        logger.warning("Emergency pause failed for %s: %s", device_id, exc)
        message = f"⚠️ {device_name} melebihi suhu aman ({temp:.0f}°C) dan upaya jeda otomatis gagal: periksa segera."

    note = await queries.insert_notification(db, device_id, "overheat_pause", message)
    await manager.broadcast({"type": "notification", "notification": _serialize(note)})
    _already_tripped.add(device_id)


def _serialize(note: dict) -> dict:
    return {
        "id": note["id"],
        "device_id": note["device_id"],
        "kind": note["kind"],
        "message": note["message"],
        "ts": note["ts"],
        "read": bool(note.get("read", False)),
    }
