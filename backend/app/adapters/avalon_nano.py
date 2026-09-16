"""
Adapter for Canaan's Avalon Nano (Nano 3 / Nano 3S), which speaks the
cgminer-API family protocol on TCP port 4028 (confirmed against Canaan's own
"Avalon A10 API manual" for the `ascset`/`summary`/`pools`/`estats` command
family, and against a live-captured `version` response identifying a real
Nano3S unit).

Field-name caveat: Canaan's own published API manual documents the larger
rack-mount Avalon A-series, not the small single-board Nano specifically.
The `summary` command's fields (Elapsed/Accepted/Rejected/best share) are
part of the generic cgminer core and are stable across the whole product
line, so those are trustworthy. The extended `stats`/`estats` fields
(temperature/fan) are read defensively — we try several known key spellings
and fall back to `None` rather than raising, and the full raw response is
always kept on the metrics object so field names can be double-checked
against a specific unit's firmware from the dashboard's device-detail view.

Control surface: Canaan's documented `ascset` commands for this product
line cover reboot, LED, pool, and network settings — there is no documented
user-settable fan-speed command, so this adapter reports NO fan/autotune
capability. Presenting a control that silently does nothing would be worse
than not offering it.
"""
from __future__ import annotations

from typing import Any

from app.adapters.base import AdapterError, DeviceCapabilities, DeviceMetrics, MinerAdapter, NotSupportedError
from app.adapters.cgminer_common import as_float, as_int, send_command
from app.models.schemas import DeviceKind, MinerAction

_TEMP_KEYS = ("Temp", "TAvg", "Temperature", "Temp0")
_MAX_TEMP_KEYS = ("TMax",)
_FAN_PERCENT_KEYS = ("FanR", "Fan Percent")
_FAN_RPM_KEYS = ("Fan1", "FanSpeed1", "Fan Speed")


class AvalonNanoAdapter(MinerAdapter):
    kind = DeviceKind.avalon_nano

    def __init__(self, host: str, port: int = 4028, **kwargs: Any) -> None:
        super().__init__(host, port, **kwargs)

    async def _cmd(self, command: str, parameter: str | None = None) -> dict[str, Any]:
        return await send_command(self.host, self.port, command, parameter, timeout=self.timeout)

    async def fetch_metrics(self) -> DeviceMetrics:
        summary = (await self._cmd("summary")).get("SUMMARY", {})
        try:
            stats = (await self._cmd("stats")).get("STATS", {})
        except AdapterError:
            stats = {}
        try:
            pools = (await self._cmd("pools")).get("POOLS", {})
        except AdapterError:
            pools = {}

        hashrate_ghs = _first_num(summary, "GHS av", "GHS 5s") 
        if hashrate_ghs is None:
            mhs = _first_num(summary, "MHS av", "MHS 5s", "MHS 20s")
            hashrate_ghs = (mhs / 1000.0) if mhs is not None else None

        raw = {"SUMMARY": summary, "STATS": stats, "POOLS": pools}
        return DeviceMetrics(
            hashrate_ghs=hashrate_ghs,
            temp_c=_first_num(stats, *_TEMP_KEYS),
            temp_secondary_c=_first_num(stats, *_MAX_TEMP_KEYS),
            fan_percent=_first_percent(stats, *_FAN_PERCENT_KEYS),
            fan_rpm=_first_num(stats, *_FAN_RPM_KEYS),
            power_w=_first_num(stats, "Power", "PS"),
            shares_accepted=_first_num(summary, "Accepted"),
            shares_rejected=_first_num(summary, "Rejected"),
            best_diff=_first_num(summary, "Best Share", "BestShare"),
            uptime_s=_first_num(summary, "Elapsed"),
            pool_url=pools.get("URL") or pools.get("Stratum URL"),
            pool_user=pools.get("User"),
            firmware_version=None,
            model="Avalon Nano",
            raw=raw,
        )

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            fan_control=False,
            autotune=False,
            restart=True,
            pause_resume=False,
            identify=False,
        )

    async def perform_action(self, action: MinerAction) -> None:
        if action == MinerAction.restart:
            await self._cmd("ascset", "0,reboot,0")
        else:
            raise NotSupportedError(f"Avalon Nano does not support action: {action.value}")


def _first_num(section: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        val = as_float(section.get(key))
        if val is not None:
            return val
    return None


def _first_percent(section: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        raw = section.get(key)
        if raw is None:
            continue
        text = str(raw).replace("%", "").strip()
        val = as_float(text)
        if val is not None:
            return val
    return None
