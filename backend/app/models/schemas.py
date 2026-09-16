"""
Pydantic request/response models.

Every model sets `extra="forbid"`: an API request carrying a field we did
not declare is rejected outright rather than silently ignored (or worse,
silently mapped onto a column it should never touch — classic mass
assignment). Numeric controls (fan percent, target temperature) declare
explicit `ge`/`le` bounds so an out-of-range value is a 422 before any
adapter code ever sees it, regardless of what the UI would normally allow.
"""
from __future__ import annotations

import re
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-\.]{0,253}[a-zA-Z0-9])?$")


class DeviceKind(str, Enum):
    bitaxe = "bitaxe"
    nerdqaxe = "nerdqaxe"
    avalon_nano = "avalon_nano"
    braiins = "braiins"
    luxos = "luxos"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# --- Auth --------------------------------------------------------------

class SetupRequest(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=8, max_length=256)


class LoginRequest(Strict):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(Strict):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=8, max_length=256)


# --- Devices -------------------------------------------------------------

class DeviceCreate(Strict):
    kind: DeviceKind
    name: str = Field(min_length=1, max_length=80)
    host: str = Field(min_length=1, max_length=255)
    port: int | None = Field(default=None, ge=1, le=65535)
    username: str | None = Field(default=None, max_length=128)
    password: str | None = Field(default=None, max_length=256)

    @field_validator("host")
    @classmethod
    def validate_host(cls, v: str) -> str:
        v = v.strip()
        # Accept dotted IPv4/hostnames/.local mDNS names. Actual reachability
        # (private-range enforcement) is re-checked by netsafety at
        # connection time — this is just input shape validation.
        if not _HOSTNAME_RE.match(v):
            raise ValueError("Invalid host: use an IP address or hostname")
        return v

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name cannot be blank")
        return v


class DeviceRename(Strict):
    name: str = Field(min_length=1, max_length=80)


class DeviceOut(Strict):
    id: str
    kind: DeviceKind
    name: str
    host: str
    port: int
    read_only: bool
    online: bool
    last_seen: float | None
    last_error: str | None
    capabilities: dict[str, bool]
    metrics: dict[str, Any]
    autotune_enabled: bool
    target_temp_c: float | None
    manual_fan_percent: float | None
    best_diff: float
    blocks_found: int


# --- Controls ------------------------------------------------------------

class FanMode(str, Enum):
    auto = "auto"
    manual = "manual"


class FanControlRequest(Strict):
    mode: FanMode
    manual_percent: float | None = Field(default=None, ge=0, le=100)

    @field_validator("manual_percent")
    @classmethod
    def require_percent_for_manual(cls, v, info):
        if info.data.get("mode") == FanMode.manual and v is None:
            raise ValueError("manual_percent is required when mode is 'manual'")
        return v


class AutotuneRequest(Strict):
    enabled: bool
    target_temp_c: float | None = Field(default=None, ge=30, le=90)


class MinerAction(str, Enum):
    restart = "restart"
    pause = "pause"
    resume = "resume"
    identify = "identify"


class ActionRequest(Strict):
    action: MinerAction


# --- History / notifications --------------------------------------------

HistoryRange = Literal["1h", "24h", "7d", "30d"]


class NotificationOut(Strict):
    id: int
    device_id: str | None
    kind: str
    message: str
    ts: float
    read: bool


class MarkReadRequest(Strict):
    ids: list[int] = Field(max_length=500)


# --- Discovery / settings ---------------------------------------------

class DiscoveryStartRequest(Strict):
    pass


class DiscoveredDevice(Strict):
    kind: DeviceKind
    host: str
    port: int
    suggested_name: str
    fingerprint: dict[str, Any] = Field(default_factory=dict)


class GlobalSettingsOut(Strict):
    poll_interval_seconds: float
    history_retention_days: int
    allow_public_targets: bool


class GlobalSettingsUpdate(Strict):
    poll_interval_seconds: float | None = Field(default=None, ge=5, le=300)
    history_retention_days: int | None = Field(default=None, ge=1, le=365)
