"""
Adapter for AxeOS-family firmware: Bitaxe (bitaxeorg/ESP-Miner) and NerdQaxe
/ NerdQaxe+ (shufps/ESP-Miner-NerdQAxePlus). NerdQaxe is a fork of the same
firmware and — per its own README ("Nerdaxe uses the same bitaxe API
functions") and release notes ("the classic v1 /api/system/info endpoint
stays exactly as it was") — exposes the identical v1 HTTP JSON API, so one
adapter class safely covers both device families.

Field names below are taken directly from ESP-Miner's published
`main/http_server/openapi.yaml` SystemInfo/Settings schemas, not guessed.
Every read uses `.get()` with a safe default: firmware versions add/rename
fields over time, and a missing field should degrade to "unknown", never
crash the poller.
"""
from __future__ import annotations

from typing import Any

import httpx

from app.adapters.base import AdapterError, DeviceCapabilities, DeviceMetrics, MinerAdapter, NotSupportedError
from app.models.schemas import DeviceKind, FanMode, MinerAction
from app.security.netsafety import assert_safe_target


class AxeOSAdapter(MinerAdapter):
    """Covers both `bitaxe` and `nerdqaxe` DeviceKind values."""

    def __init__(self, host: str, port: int = 80, **kwargs: Any) -> None:
        super().__init__(host, port, **kwargs)
        self._client: httpx.AsyncClient | None = None

    def _base_url(self) -> str:
        safe_host = assert_safe_target(self.host)
        return f"http://{safe_host}:{self.port}"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(base_url=self._base_url(), timeout=self.timeout)
        return self._client

    async def aclose(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def _get(self, path: str) -> dict[str, Any]:
        client = await self._get_client()
        try:
            resp = await client.get(path)
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"AxeOS request to {path} failed: {exc}") from exc

    async def _patch(self, path: str, body: dict[str, Any]) -> None:
        client = await self._get_client()
        try:
            resp = await client.patch(path, json=body)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterError(f"AxeOS control request to {path} failed: {exc}") from exc

    async def _post(self, path: str) -> None:
        client = await self._get_client()
        try:
            resp = await client.post(path)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise AdapterError(f"AxeOS action request to {path} failed: {exc}") from exc

    async def fetch_metrics(self) -> DeviceMetrics:
        info = await self._get("/api/system/info")
        pools = info.get("pools") or []
        primary_pool = pools[0] if pools else {}
        return DeviceMetrics(
            hashrate_ghs=_num(info.get("hashRate")),
            temp_c=_num(info.get("temp")),
            temp_secondary_c=_num(info.get("temp2")) or _num(info.get("vrTemp")),
            fan_percent=_num(info.get("fanspeed")),
            fan_rpm=_num(info.get("fanrpm")),
            fan_rpm_secondary=_num(info.get("fan2rpm")),
            power_w=_num(info.get("power")),
            voltage_v=_millivolts_to_volts(info.get("voltage")),
            shares_accepted=_num(info.get("sharesAccepted")),
            shares_rejected=_num(info.get("sharesRejected")),
            best_diff=_parse_diff(info.get("bestDiff")),
            best_session_diff=_parse_diff(info.get("bestSessionDiff")),
            uptime_s=_num(info.get("uptimeSeconds")),
            blocks_found=_int(info.get("blockFound")),
            pool_url=info.get("stratumURL") or primary_pool.get("stratumURL"),
            pool_user=info.get("stratumUser") or primary_pool.get("stratumUser"),
            firmware_version=info.get("axeOSVersion") or info.get("version"),
            model=info.get("ASICModel"),
            autofan_enabled=bool(info.get("autofanspeed")),
            target_temp_c=_num(info.get("temptarget")),
            mining_paused=bool(info.get("miningPaused")) if "miningPaused" in info else None,
            raw=info,
        )

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            fan_control=True,
            autotune=True,
            restart=True,
            pause_resume=True,
            identify=True,
        )

    async def set_fan(self, mode: FanMode, manual_percent: float | None) -> None:
        if mode == FanMode.auto:
            await self._patch("/api/system", {"autofanspeed": 1})
        else:
            if manual_percent is None:
                raise AdapterError("manual_percent is required for manual fan mode")
            await self._patch("/api/system", {"autofanspeed": 0, "fanspeed": int(round(manual_percent))})

    async def set_autotune(self, enabled: bool, target_temp_c: float | None) -> None:
        body: dict[str, Any] = {"autofanspeed": 1 if enabled else 0}
        if enabled and target_temp_c is not None:
            body["temptarget"] = int(round(target_temp_c))
        await self._patch("/api/system", body)

    async def perform_action(self, action: MinerAction) -> None:
        if action == MinerAction.restart:
            await self._post("/api/system/restart")
        elif action == MinerAction.pause:
            await self._post("/api/system/pause")
        elif action == MinerAction.resume:
            await self._post("/api/system/resume")
        elif action == MinerAction.identify:
            await self._post("/api/system/identify")
        else:
            raise NotSupportedError(f"Unsupported action: {action}")


def _num(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    n = _num(value)
    return int(n) if n is not None else None


def _millivolts_to_volts(value: Any) -> float | None:
    n = _num(value)
    if n is None:
        return None
    # AxeOS reports input voltage in volts already on most firmware builds,
    # but some report millivolts. Values above 100 are almost certainly mV
    # for a 5V-class board.
    return round(n / 1000.0, 3) if n > 100 else n


def _parse_diff(value: Any) -> float | None:
    """
    AxeOS reports bestDiff either as a plain number or a compact string like
    "150K" / "2.1M" / "3.4G". Normalize both to a plain float.
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().upper()
    if not text:
        return None
    multipliers = {"K": 1_000, "M": 1_000_000, "G": 1_000_000_000, "T": 1_000_000_000_000}
    suffix = text[-1]
    if suffix in multipliers:
        try:
            return float(text[:-1]) * multipliers[suffix]
        except ValueError:
            return None
    try:
        return float(text)
    except ValueError:
        return None


class BitaxeAdapter(AxeOSAdapter):
    kind = DeviceKind.bitaxe


class NerdQaxeAdapter(AxeOSAdapter):
    kind = DeviceKind.nerdqaxe
