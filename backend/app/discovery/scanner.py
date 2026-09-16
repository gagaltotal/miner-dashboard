"""
LAN discovery: find candidate miners on the same network(s) the dashboard
host is connected to, and fingerprint what kind of device each one is
before ever asking the user to add it.

Scope of the scan is derived strictly from the local machine's own network
interfaces (via psutil) — never from a user-supplied range — and is capped
at /22 (1024 addresses) per interface so a misconfigured interface can't
turn "scan my LAN" into an accidental scan of a huge range. Every candidate
address is additionally a private-range address by construction (it comes
from an interface's own subnet), and adapters re-validate with
`netsafety.assert_safe_target` regardless, so this stays inside the same
SSRF-safe boundary as every other outbound connection in the app.
"""
from __future__ import annotations

import asyncio
import ipaddress
import json as _json
from dataclasses import dataclass

import httpx
import psutil

from app.adapters.cgminer_common import send_command
from app.config import settings
from app.models.schemas import DeviceKind

_HTTP_PORT = 80
_CGMINER_PORT = 4028
_MAX_HOSTS_PER_INTERFACE = 1024


@dataclass
class DiscoveryHit:
    kind: DeviceKind
    host: str
    port: int
    suggested_name: str
    fingerprint: dict


def _local_ipv4_networks() -> list[ipaddress.IPv4Network]:
    networks: list[ipaddress.IPv4Network] = []
    try:
        addrs = psutil.net_if_addrs()
    except Exception:
        return networks
    for interface_addrs in addrs.values():
        for addr in interface_addrs:
            if addr.family.name not in ("AF_INET",):
                continue
            if not addr.address or not addr.netmask:
                continue
            if addr.address.startswith("127."):
                continue
            try:
                net = ipaddress.ip_network(f"{addr.address}/{addr.netmask}", strict=False)
            except ValueError:
                continue
            if net.num_addresses > _MAX_HOSTS_PER_INTERFACE:
                # Skip absurdly large ranges (e.g. a misconfigured /8) rather
                # than trying to probe thousands of hosts.
                continue
            if net.is_private and net not in networks:
                networks.append(net)
    return networks


async def _port_open(host: str, port: int, timeout: float) -> bool:
    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=timeout)
    except (OSError, asyncio.TimeoutError):
        return False
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass
    return True


async def _fingerprint_http(host: str, timeout: float) -> DiscoveryHit | None:
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"http://{host}:{_HTTP_PORT}/api/system/info")
            if resp.status_code == 200:
                info = resp.json()
                if "hashRate" in info or "ASICModel" in info:
                    asic_count = info.get("asicCount") or 1
                    hostname = str(info.get("hostname") or "")
                    kind = (
                        DeviceKind.nerdqaxe
                        if (asic_count and asic_count > 1) or "nerd" in hostname.lower()
                        else DeviceKind.bitaxe
                    )
                    name = info.get("hostname") or f"{kind.value}-{host.split('.')[-1]}"
                    return DiscoveryHit(
                        kind=kind, host=host, port=_HTTP_PORT, suggested_name=name,
                        fingerprint={"ASICModel": info.get("ASICModel"), "version": info.get("version")},
                    )
    except Exception:
        pass

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(f"http://{host}:{_HTTP_PORT}/api/v1/version/")
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, dict) and "major" in data:
                    return DiscoveryHit(
                        kind=DeviceKind.braiins, host=host, port=_HTTP_PORT,
                        suggested_name=f"braiins-{host.split('.')[-1]}",
                        fingerprint={"api_version": data},
                    )
    except Exception:
        pass
    return None


async def _fingerprint_cgminer(host: str, timeout: float) -> DiscoveryHit | None:
    try:
        result = await send_command(host, _CGMINER_PORT, "version", timeout=timeout)
    except Exception:
        return None

    version_section = result.get("VERSION", {})
    status_section = result.get("STATUS", {})
    blob = _json.dumps(version_section).upper() + _json.dumps(status_section).upper()

    if "LUXMINER" in blob or "LUXOS" in blob:
        kind = DeviceKind.luxos
    elif "NANO" in blob:
        kind = DeviceKind.avalon_nano
    else:
        # Unknown cgminer-family device: default to Avalon Nano (the more
        # common home-mining case for this port) but keep the raw
        # fingerprint so the user can correct the kind before adding it.
        kind = DeviceKind.avalon_nano

    model = version_section.get("PROD") or version_section.get("MODEL") or kind.value
    return DiscoveryHit(
        kind=kind, host=host, port=_CGMINER_PORT, suggested_name=f"{model}-{host.split('.')[-1]}",
        fingerprint={"VERSION": version_section},
    )


async def _probe_host(host: str, timeout: float, sem: asyncio.Semaphore) -> DiscoveryHit | None:
    async with sem:
        http_open, cgminer_open = await asyncio.gather(
            _port_open(host, _HTTP_PORT, timeout), _port_open(host, _CGMINER_PORT, timeout)
        )
    if http_open:
        hit = await _fingerprint_http(host, timeout)
        if hit:
            return hit
    if cgminer_open:
        hit = await _fingerprint_cgminer(host, timeout)
        if hit:
            return hit
    return None


async def scan_lan() -> list[DiscoveryHit]:
    networks = _local_ipv4_networks()
    hosts: list[str] = []
    for net in networks:
        hosts.extend(str(ip) for ip in net.hosts())

    sem = asyncio.Semaphore(settings.DISCOVERY_CONCURRENCY)
    tasks = [_probe_host(h, settings.DISCOVERY_TIMEOUT_SECONDS, sem) for h in hosts]
    results = await asyncio.gather(*tasks, return_exceptions=False) if tasks else []
    return [r for r in results if r is not None]
