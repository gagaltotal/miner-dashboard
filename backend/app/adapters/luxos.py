"""
Adapter for LuxOS (Luxor's Avalon-based firmware), speaking the cgminer-API
family protocol (JSON over TCP port 4028), per docs.luxor.tech/firmware/api.

READ-ONLY BY DESIGN — this is a hard requirement from the project brief, not
just a UI toggle:
LuxOS documents two command families: "CGminer commands" (summary, stats,
estats, devs, edevs, pools, temps, fans, version, config, check, coin — all
inspection/read commands) and "LUXminer commands" (fanset, frequencyset,
autotunerset, curtail, disableboard/enableboard, poolopts, netset, power,
kill, ...) which change miner state and, per Luxor's own docs, often require
an authenticated `logon` session first.

This adapter's command allowlist below contains ONLY the CGminer read
commands. There is no method on this class that sends a LUXminer command,
no `logon` call, and `capabilities()` unconditionally reports every control
flag as disabled. This means read-only enforcement lives at the code level:
even if a future change to the API layer had a bug that tried to route a
control request to a LuxOS device, this class has no way to act on it.
"""
from __future__ import annotations

from typing import Any

from app.adapters.base import AdapterError, DeviceCapabilities, DeviceMetrics, MinerAdapter
from app.adapters.cgminer_common import as_float, send_command
from app.models.schemas import DeviceKind

_ALLOWED_READ_COMMANDS = frozenset({"summary", "stats", "estats", "devs", "edevs", "pools", "version", "temps", "fans"})


class LuxOSAdapter(MinerAdapter):
    kind = DeviceKind.luxos

    def __init__(self, host: str, port: int = 4028, **kwargs: Any) -> None:
        super().__init__(host, port, **kwargs)

    async def _read(self, command: str) -> dict[str, Any]:
        if command not in _ALLOWED_READ_COMMANDS:
            # Defense in depth: this branch should be unreachable since every
            # call site below passes a literal from the allowlist, but if
            # anyone ever adds a call with a dynamic command name, this stops
            # it from ever becoming a write.
            raise AdapterError(f"'{command}' is not an allowed read-only LuxOS command")
        return await send_command(self.host, self.port, command, timeout=self.timeout)

    async def fetch_metrics(self) -> DeviceMetrics:
        summary = (await self._read("summary")).get("SUMMARY", {})
        try:
            stats = (await self._read("stats")).get("STATS", {})
        except AdapterError:
            stats = {}
        try:
            pools = (await self._read("pools")).get("POOLS", {})
        except AdapterError:
            pools = {}
        try:
            temps = (await self._read("temps")).get("TEMPS", {})
        except AdapterError:
            temps = {}
        try:
            fans = (await self._read("fans")).get("FANS", {})
        except AdapterError:
            fans = {}

        hashrate_ghs = _first_num(summary, "GHS av", "GHS 5s")
        if hashrate_ghs is None:
            mhs = _first_num(summary, "MHS av", "MHS 5s")
            hashrate_ghs = (mhs / 1000.0) if mhs is not None else None

        raw = {"SUMMARY": summary, "STATS": stats, "POOLS": pools, "TEMPS": temps, "FANS": fans}
        return DeviceMetrics(
            hashrate_ghs=hashrate_ghs,
            temp_c=_first_num(temps, "Board", "Chip", "Temp") or _first_num(stats, "Temp", "TAvg"),
            temp_secondary_c=_first_num(temps, "TMax") or _first_num(stats, "TMax"),
            fan_percent=_first_num(fans, "RPMPercent", "Percent"),
            fan_rpm=_first_num(fans, "RPM"),
            shares_accepted=_first_num(summary, "Accepted"),
            shares_rejected=_first_num(summary, "Rejected"),
            best_diff=_first_num(summary, "Best Share", "BestShare"),
            uptime_s=_first_num(summary, "Elapsed"),
            pool_url=pools.get("URL") or pools.get("Stratum URL"),
            pool_user=pools.get("User"),
            model="LuxOS rig",
            raw=raw,
        )

    def capabilities(self) -> DeviceCapabilities:
        # Every flag is explicitly False: monitoring only, per the project
        # requirement. See the module docstring for why this can't drift.
        return DeviceCapabilities(
            fan_control=False,
            autotune=False,
            restart=False,
            pause_resume=False,
            identify=False,
        )


def _first_num(section: dict[str, Any], *keys: str) -> float | None:
    for key in keys:
        val = as_float(section.get(key))
        if val is not None:
            return val
    return None
