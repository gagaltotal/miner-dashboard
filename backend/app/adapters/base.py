"""
Common adapter interface every miner integration implements.

Design note on the read-only enforcement the project requires for LuxOS:
capability flags below are *reported by the adapter class itself*, not
stored as a client-editable device setting. The API layer (api/routes/devices.py)
checks `capabilities().fan_control` etc. before allowing any control call —
so even a tampered request that tries to invoke a control endpoint against a
LuxOS-kind device is rejected server-side, because the LuxOS adapter simply
never reports (or implements) those capabilities. There is no flag anywhere
that flips a LuxOS device into "controllable".
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from app.models.schemas import DeviceKind, FanMode, MinerAction


class AdapterError(Exception):
    """Raised for any adapter-level failure (network, parse, unsupported)."""


class NotSupportedError(AdapterError):
    """Raised when a control is invoked against a device that cannot do it."""


@dataclass
class DeviceMetrics:
    hashrate_ghs: float | None = None
    temp_c: float | None = None
    temp_secondary_c: float | None = None
    fan_percent: float | None = None
    fan_rpm: float | None = None
    fan_rpm_secondary: float | None = None
    power_w: float | None = None
    voltage_v: float | None = None
    shares_accepted: float | None = None
    shares_rejected: float | None = None
    best_diff: float | None = None
    best_session_diff: float | None = None
    uptime_s: float | None = None
    blocks_found: int | None = None
    pool_url: str | None = None
    pool_user: str | None = None
    firmware_version: str | None = None
    model: str | None = None
    autofan_enabled: bool | None = None
    target_temp_c: float | None = None
    mining_paused: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def efficiency_j_th(self) -> float | None:
        """Joules per terahash — power_w / (hashrate in TH/s)."""
        if not self.power_w or not self.hashrate_ghs:
            return None
        th_s = self.hashrate_ghs / 1000.0
        if th_s <= 0:
            return None
        return round(self.power_w / th_s, 2)


@dataclass
class DeviceCapabilities:
    fan_control: bool = False
    autotune: bool = False
    restart: bool = False
    pause_resume: bool = False
    identify: bool = False


class MinerAdapter(ABC):
    kind: DeviceKind

    def __init__(self, host: str, port: int, *, username: str | None = None,
                 password: str | None = None, timeout: float = 4.0) -> None:
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.timeout = timeout

    @abstractmethod
    async def fetch_metrics(self) -> DeviceMetrics:
        """Poll the device and return a normalized metrics snapshot."""

    @abstractmethod
    def capabilities(self) -> DeviceCapabilities:
        """Static per-adapter-class capability flags (see module docstring)."""

    async def set_fan(self, mode: FanMode, manual_percent: float | None) -> None:
        raise NotSupportedError(f"{self.kind.value} does not support fan control")

    async def set_autotune(self, enabled: bool, target_temp_c: float | None) -> None:
        raise NotSupportedError(f"{self.kind.value} does not support automatic temperature control")

    async def perform_action(self, action: MinerAction) -> None:
        raise NotSupportedError(f"{self.kind.value} does not support this action")

    async def aclose(self) -> None:
        """Release any held connections/clients. Override if needed."""
        return None
