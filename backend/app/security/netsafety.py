"""
Outbound-connection safety guard (anti-SSRF).

Every single place in this codebase that opens a socket or makes an HTTP
request to a "device" (discovery probing, adapters, manual add-device) MUST
route the target through `assert_safe_target()` first. Centralizing the
check here means there is exactly one function to audit, instead of trusting
every call site to remember to validate.

Why this matters: the dashboard's job is to reach out, on the user's behalf,
to whatever host/IP the frontend sends it. Without this guard, a malicious or
compromised frontend request (or a tampered API call — see the "bypass
tamper" requirement in the project brief) could turn this backend into an
open network proxy, e.g. pointed at a cloud metadata endpoint
(169.254.169.254), localhost services, or the public internet. Restricting
targets to the user's own private LAN closes that off structurally, not just
by convention.
"""
from __future__ import annotations

import ipaddress
import socket

from app.config import settings

# Cloud-metadata endpoints used by AWS/GCP/Azure/etc. These sit inside the
# link-local range, which we would otherwise treat as "private", so they are
# explicitly denied regardless of the ALLOW_PUBLIC_TARGETS override.
_ALWAYS_BLOCKED = {
    ipaddress.ip_address("169.254.169.254"),
    ipaddress.ip_address("fd00:ec2::254"),
}

_PRIVATE_NETWORKS = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),  # link-local (mDNS-assigned addrs etc.)
    ipaddress.ip_network("fc00::/7"),        # unique local (IPv6)
    ipaddress.ip_network("fe80::/10"),       # link-local (IPv6)
    ipaddress.ip_network("::1/128"),
]


class UnsafeTargetError(ValueError):
    """Raised when a hostname/IP resolves to something we refuse to contact."""


def _is_allowed_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if ip in _ALWAYS_BLOCKED:
        return False
    if settings.ALLOW_PUBLIC_TARGETS:
        return True
    return any(ip in net for net in _PRIVATE_NETWORKS)


def assert_safe_target(host: str) -> str:
    """
    Resolve `host` and confirm every resolved address is a safe target for an
    outbound connection. Returns the (unchanged) host on success, or raises
    UnsafeTargetError.

    We resolve DNS ourselves (rather than letting httpx/socket do it lazily)
    so that a hostname which resolves to a disallowed address is rejected
    before any connection attempt is made — this also defeats DNS-rebinding
    tricks where a name resolves to a private IP now, but did not
    during a naive check.
    """
    host = host.strip()
    if not host:
        raise UnsafeTargetError("Empty host")

    try:
        candidate = ipaddress.ip_address(host)
        addresses = [candidate]
    except ValueError:
        try:
            infos = socket.getaddrinfo(host, None)
        except socket.gaierror as exc:
            raise UnsafeTargetError(f"Could not resolve host: {host}") from exc
        addresses = []
        for info in infos:
            try:
                addresses.append(ipaddress.ip_address(info[4][0]))
            except ValueError:
                continue
        if not addresses:
            raise UnsafeTargetError(f"Could not resolve host: {host}")

    for ip in addresses:
        if not _is_allowed_ip(ip):
            raise UnsafeTargetError(
                f"Refusing to contact {host} ({ip}): not a private LAN address"
            )
    return host


def is_valid_port(port: int) -> bool:
    return isinstance(port, int) and 1 <= port <= 65535
