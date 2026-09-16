"""
Fixed dispatch table from DeviceKind to adapter class.

Deliberately a plain dict literal, not `importlib.import_module(user_input)`
or `getattr(module, user_supplied_name)`. The device "kind" a request can
supply is already constrained to the `DeviceKind` enum by Pydantic before it
ever reaches this module, so there is no code path where a string from a
request selects which class gets instantiated beyond this closed, five-entry
table — closing off the class of RCE bugs that comes from dynamic
import-by-name.
"""
from __future__ import annotations

from app.adapters.avalon_nano import AvalonNanoAdapter
from app.adapters.base import MinerAdapter
from app.adapters.bitaxe import BitaxeAdapter, NerdQaxeAdapter
from app.adapters.braiins import BraiinsAdapter
from app.adapters.luxos import LuxOSAdapter
from app.models.schemas import DeviceKind

_REGISTRY: dict[DeviceKind, type[MinerAdapter]] = {
    DeviceKind.bitaxe: BitaxeAdapter,
    DeviceKind.nerdqaxe: NerdQaxeAdapter,
    DeviceKind.avalon_nano: AvalonNanoAdapter,
    DeviceKind.braiins: BraiinsAdapter,
    DeviceKind.luxos: LuxOSAdapter,
}

_DEFAULT_PORTS: dict[DeviceKind, int] = {
    DeviceKind.bitaxe: 80,
    DeviceKind.nerdqaxe: 80,
    DeviceKind.avalon_nano: 4028,
    DeviceKind.braiins: 80,
    DeviceKind.luxos: 4028,
}

# Kinds whose adapter never implements any control method — used by the API
# layer to reject control requests before even instantiating an adapter.
READ_ONLY_KINDS = frozenset({DeviceKind.luxos})


def default_port(kind: DeviceKind) -> int:
    return _DEFAULT_PORTS[kind]


def build_adapter(
    kind: DeviceKind,
    host: str,
    port: int,
    *,
    username: str | None = None,
    password: str | None = None,
    timeout: float = 4.0,
) -> MinerAdapter:
    adapter_cls = _REGISTRY[kind]
    return adapter_cls(host, port, username=username, password=password, timeout=timeout)
