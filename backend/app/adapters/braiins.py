"""
Adapter for Braiins OS+ using its official Public REST API
(developer.braiins-os.com — "Braiins OS Public REST API"), available since
Braiins OS 25.07 as a REST wrapper around the same gRPC service used by
older integrations. Requires Braiins OS 25.07+; older installs only expose
the gRPC/port-50051 interface and are out of scope for this adapter.

Confidence notes (read before changing field mappings):
- Auth (POST /api/v1/auth/login -> {token, timeout_s}), miner/details,
  cooling/state's `fans[].{position,rpm,target_speed_ratio}`, and
  pools/ -> `[].pools[].stats.{accepted_shares,rejected_shares,best_share}`
  are taken verbatim from the published OpenAPI spec — high confidence.
- `miner/stats` and the exact request body for *manual* cooling mode were
  not fully expanded in the spec we could retrieve (nested schemas were
  opaque placeholders). For those we deep-search the response for the
  unit-suffixed leaf keys Braiins uses consistently everywhere else in this
  API (`terahash_per_second`, `watt`, `degree_c`) rather than assuming an
  exact path — this is resilient to us not knowing the exact wrapper key
  Braiins nests them under. If a specific firmware build uses different
  nesting for manual fan control, fetch that unit's own live schema at
  `GET /api/v1/docs/openapi.json` and adjust `set_fan()` below.
"""
from __future__ import annotations

import time
from typing import Any

import httpx

from app.adapters.base import AdapterError, DeviceCapabilities, DeviceMetrics, MinerAdapter, NotSupportedError
from app.models.schemas import DeviceKind, FanMode, MinerAction
from app.security.netsafety import assert_safe_target


class BraiinsAdapter(MinerAdapter):
    kind = DeviceKind.braiins

    def __init__(self, host: str, port: int = 80, **kwargs: Any) -> None:
        super().__init__(host, port, **kwargs)
        self._client: httpx.AsyncClient | None = None
        self._token: str | None = None
        self._token_expires_at: float = 0.0

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

    async def _ensure_token(self, client: httpx.AsyncClient) -> str:
        if self._token and time.time() < self._token_expires_at - 30:
            return self._token
        if not self.username or not self.password:
            raise AdapterError("Braiins OS+ requires a username and password to be configured for this device")
        try:
            resp = await client.post(
                "/api/v1/auth/login", json={"username": self.username, "password": self.password}
            )
            resp.raise_for_status()
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise AdapterError(f"Braiins OS+ login failed: {exc}") from exc
        self._token = data.get("token")
        timeout_s = data.get("timeout_s") or 3600
        self._token_expires_at = time.time() + float(timeout_s)
        if not self._token:
            raise AdapterError("Braiins OS+ login response did not include a token")
        return self._token

    async def _request(self, method: str, path: str, *, json_body: Any = None, retry: bool = True) -> Any:
        client = await self._get_client()
        token = await self._ensure_token(client)
        try:
            resp = await client.request(method, path, json=json_body, headers={"Authorization": token})
        except httpx.HTTPError as exc:
            raise AdapterError(f"Braiins OS+ request to {path} failed: {exc}") from exc

        if resp.status_code == 401 and retry:
            # Token may have been invalidated server-side; force one re-login.
            self._token = None
            return await self._request(method, path, json_body=json_body, retry=False)

        try:
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise AdapterError(f"Braiins OS+ request to {path} failed: {exc}") from exc

        if resp.status_code == 204 or not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return None

    async def fetch_metrics(self) -> DeviceMetrics:
        details = await self._request("GET", "/api/v1/miner/details") or {}
        try:
            stats = await self._request("GET", "/api/v1/miner/stats") or {}
        except AdapterError:
            stats = {}
        try:
            cooling = await self._request("GET", "/api/v1/cooling/state") or {}
        except AdapterError:
            cooling = {}
        try:
            pool_groups = await self._request("GET", "/api/v1/pools/") or []
        except AdapterError:
            pool_groups = []

        pool_url = pool_user = None
        accepted = rejected = best_share = None
        for group in pool_groups:
            for pool in group.get("pools", []):
                if pool.get("active"):
                    pool_url = pool.get("url")
                    pool_user = pool.get("user")
                    pstats = pool.get("stats", {})
                    accepted = pstats.get("accepted_shares")
                    rejected = pstats.get("rejected_shares")
                    best_share = pstats.get("best_share")
                    break
            if pool_url:
                break

        fans = cooling.get("fans", []) or []
        fan_rpm = fans[0].get("rpm") if fans else None
        fan_ratio = fans[0].get("target_speed_ratio") if fans else None
        fan_percent = (fan_ratio * 100.0) if isinstance(fan_ratio, (int, float)) and fan_ratio <= 1.5 else fan_ratio

        raw = {"details": details, "stats": stats, "cooling": cooling, "pools": pool_groups}
        return DeviceMetrics(
            hashrate_ghs=_first_leaf(stats, "terahash_per_second", scale=1000.0)
            or _first_leaf(stats, "gigahash_per_second"),
            temp_c=_first_leaf(cooling.get("highest_temperature"), "degree_c") or _first_leaf(cooling, "degree_c"),
            fan_percent=fan_percent,
            fan_rpm=fan_rpm,
            power_w=_first_leaf(stats, "watt"),
            shares_accepted=accepted,
            shares_rejected=rejected,
            best_diff=best_share,
            uptime_s=details.get("system_uptime_s"),
            pool_url=pool_url,
            pool_user=pool_user,
            firmware_version=_first_leaf(details.get("bos_version"), "semver") or str(details.get("bos_version") or "") or None,
            model=details.get("hostname"),
            raw=raw,
        )

    def capabilities(self) -> DeviceCapabilities:
        return DeviceCapabilities(
            fan_control=True,
            autotune=True,
            restart=True,
            pause_resume=True,
            identify=False,
        )

    async def set_fan(self, mode: FanMode, manual_percent: float | None) -> None:
        if mode == FanMode.auto:
            # Keep current target temperature if we have no better value —
            # the API requires one, so fall back to a conservative default.
            await self._request(
                "PUT", "/api/v1/cooling/mode", json_body={"auto": {"target_temperature": {"degree_c": 60}}}
            )
        else:
            if manual_percent is None:
                raise AdapterError("manual_percent is required for manual fan mode")
            ratio = max(0.0, min(1.0, manual_percent / 100.0))
            await self._request(
                "PUT", "/api/v1/cooling/mode", json_body={"manual": {"fan_speed": {"target_speed_ratio": ratio}}}
            )

    async def set_autotune(self, enabled: bool, target_temp_c: float | None) -> None:
        if not enabled:
            raise NotSupportedError(
                "Braiins OS+ always runs a cooling mode; switch to manual fan control instead of disabling autotune"
            )
        temp = target_temp_c if target_temp_c is not None else 60
        await self._request(
            "PUT", "/api/v1/cooling/mode", json_body={"auto": {"target_temperature": {"degree_c": temp}}}
        )

    async def perform_action(self, action: MinerAction) -> None:
        if action == MinerAction.restart:
            await self._request("PUT", "/api/v1/actions/reboot")
        elif action == MinerAction.pause:
            await self._request("PUT", "/api/v1/actions/pause")
        elif action == MinerAction.resume:
            await self._request("PUT", "/api/v1/actions/resume")
        else:
            raise NotSupportedError(f"Braiins OS+ does not support action: {action.value}")


def _first_leaf(obj: Any, key: str, scale: float = 1.0, _depth: int = 0) -> float | None:
    """Depth-first search for the first occurrence of `key` anywhere in a
    nested dict/list structure, returning it scaled by `scale`. See the
    module docstring for why this is used instead of a fixed path."""
    if _depth > 6 or obj is None:
        return None
    if isinstance(obj, dict):
        if key in obj and isinstance(obj[key], (int, float)):
            return float(obj[key]) * scale
        for value in obj.values():
            found = _first_leaf(value, key, scale, _depth + 1)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _first_leaf(item, key, scale, _depth + 1)
            if found is not None:
                return found
    return None
