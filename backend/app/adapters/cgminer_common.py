"""
Shared client for the "cgminer API family" protocol used by Avalon Nano and
LuxOS (and, historically, most Bitmain/Whatsminer firmware): a bare TCP
socket on port 4028, one command per connection, JSON in and (usually) JSON
out.

Two real-world quirks this client works around, both confirmed against
vendor documentation and captured device output while building this
adapter:

1. Some firmwares terminate their response with a trailing NUL byte
   (`\\x00`) instead of just closing the socket cleanly, which trips up a
   naive `json.loads()`. We strip trailing NULs/whitespace before parsing.
2. Some older firmwares (notably Canaan's original cgminer fork) ignore a
   JSON-formatted request and reply with the *legacy* comma-separated
   `KEY=VALUE` text format instead of JSON, e.g.
   `STATUS=S,When=123,Code=7,Msg=...|POOL=0,URL=...,Accepted=1701,...`.
   We detect this (response does not start with `{`) and parse it into the
   same nested-dict shape a JSON response would have had, so adapters only
   ever deal with one data shape.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from app.security.netsafety import assert_safe_target, is_valid_port
from app.adapters.base import AdapterError


async def send_command(
    host: str, port: int, command: str, parameter: str | None = None, timeout: float = 4.0
) -> dict[str, Any]:
    safe_host = assert_safe_target(host)
    if not is_valid_port(port):
        raise AdapterError(f"Invalid port: {port}")

    payload: dict[str, Any] = {"command": command}
    if parameter is not None:
        payload["parameter"] = parameter
    request_bytes = json.dumps(payload).encode("utf-8")

    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(safe_host, port), timeout=timeout
        )
    except (OSError, asyncio.TimeoutError) as exc:
        raise AdapterError(f"Could not connect to {safe_host}:{port}: {exc}") from exc

    try:
        writer.write(request_bytes)
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        chunks: list[bytes] = []
        try:
            while True:
                chunk = await asyncio.wait_for(reader.read(4096), timeout=timeout)
                if not chunk:
                    break
                chunks.append(chunk)
        except asyncio.TimeoutError:
            if not chunks:
                raise AdapterError(f"Timed out waiting for {safe_host}:{port} to respond")
        raw = b"".join(chunks)
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

    text = raw.decode("utf-8", errors="ignore").strip().strip("\x00").strip()
    if not text:
        raise AdapterError(f"Empty response from {safe_host}:{port}")

    return _parse_response(text)


def _parse_response(text: str) -> dict[str, Any]:
    if text.lstrip().startswith("{") or text.lstrip().startswith("["):
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Some firmwares append trailing garbage after a valid JSON
            # object; raw_decode stops at the first complete object instead
            # of demanding the whole buffer be valid JSON.
            try:
                parsed, _ = json.JSONDecoder().raw_decode(text)
            except json.JSONDecodeError as exc:
                raise AdapterError(f"Could not parse JSON response: {exc}") from exc
        return _normalize_json_shape(parsed)
    return _parse_legacy_text(text)


def _normalize_json_shape(parsed: Any) -> dict[str, Any]:
    """
    cgminer-family JSON sometimes nests each section under a list (e.g.
    {"SUMMARY": [{...}]}) and sometimes flattens it (e.g. {"SUMMARY": {...}}).
    Normalize to always-a-dict-per-section so adapters have one shape to
    read.
    """
    if not isinstance(parsed, dict):
        return {"_raw": parsed}
    normalized: dict[str, Any] = {}
    for key, value in parsed.items():
        if key in ("", "\u0000"):
            continue
        if isinstance(value, list):
            normalized[key] = value[0] if len(value) == 1 and isinstance(value[0], dict) else value
        else:
            normalized[key] = value
    return normalized


def _parse_legacy_text(text: str) -> dict[str, Any]:
    """
    Parse the classic `SECTION,K=V,K=V|SECTION2,K=V,...` cgminer text
    format into {"SECTION": {"K": "V", ...}, ...}.
    """
    result: dict[str, Any] = {}
    for section in text.split("|"):
        section = section.strip()
        if not section:
            continue
        parts = section.split(",")
        section_name = parts[0].split("=")[0] if "=" in parts[0] else parts[0]
        fields: dict[str, str] = {}
        # If the very first token itself is a K=V pair (no bare section
        # name), keep it too.
        first = parts[0]
        rest = parts[1:]
        if "=" in first:
            k, _, v = first.partition("=")
            fields[k] = v
            rest = parts[1:]
        else:
            rest = parts[1:]
        for part in rest:
            if "=" not in part:
                continue
            k, _, v = part.partition("=")
            fields[k] = v
        result.setdefault(section_name, {}).update(fields)
    return result


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_int(value: Any) -> int | None:
    f = as_float(value)
    return int(f) if f is not None else None
