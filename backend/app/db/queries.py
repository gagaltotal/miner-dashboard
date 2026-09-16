"""
All SQL lives here (see database.py's module docstring for why). Every
function takes plain Python values and passes them through as bound
parameters — nothing here ever formats a value into the SQL text.
"""
from __future__ import annotations

import json
import time
import uuid
from typing import Any, Iterable

from app.db.database import Database


# --- operator (single local user) ---------------------------------------

async def get_operator(db: Database) -> dict | None:
    cur = await db.conn.execute("SELECT * FROM operator WHERE id = 1")
    row = await cur.fetchone()
    return dict(row) if row else None


async def create_operator(db: Database, username: str, password_hash: str) -> None:
    async with db.transaction():
        await db.conn.execute(
            "INSERT INTO operator (id, username, password_hash, created_at) VALUES (1, ?, ?, ?)",
            (username, password_hash, time.time()),
        )


async def update_operator_password(db: Database, password_hash: str) -> None:
    async with db.transaction():
        await db.conn.execute(
            "UPDATE operator SET password_hash = ? WHERE id = 1", (password_hash,)
        )


# --- devices ---------------------------------------------------------------

def new_device_id() -> str:
    return uuid.uuid4().hex[:12]


async def insert_device(
    db: Database, kind: str, name: str, host: str, port: int, read_only: bool, extra: dict
) -> str:
    device_id = new_device_id()
    now = time.time()
    async with db.transaction():
        await db.conn.execute(
            """INSERT INTO devices (id, kind, name, host, port, read_only, created_at, updated_at, extra_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (device_id, kind, name, host, port, int(read_only), now, now, json.dumps(extra)),
        )
        await db.conn.execute(
            "INSERT OR IGNORE INTO device_state (device_id) VALUES (?)", (device_id,)
        )
        await db.conn.execute(
            "INSERT OR IGNORE INTO device_settings (device_id) VALUES (?)", (device_id,)
        )
    return device_id


async def list_devices(db: Database) -> list[dict]:
    cur = await db.conn.execute(
        """SELECT d.*, s.online, s.last_seen, s.last_error, s.latest_json, s.best_diff, s.blocks_found,
                  ds.autotune_enabled, ds.target_temp_c, ds.manual_fan_percent
           FROM devices d
           LEFT JOIN device_state s ON s.device_id = d.id
           LEFT JOIN device_settings ds ON ds.device_id = d.id
           ORDER BY d.created_at ASC"""
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def get_device(db: Database, device_id: str) -> dict | None:
    cur = await db.conn.execute(
        """SELECT d.*, s.online, s.last_seen, s.last_error, s.latest_json, s.best_diff, s.blocks_found,
                  ds.autotune_enabled, ds.target_temp_c, ds.manual_fan_percent
           FROM devices d
           LEFT JOIN device_state s ON s.device_id = d.id
           LEFT JOIN device_settings ds ON ds.device_id = d.id
           WHERE d.id = ?""",
        (device_id,),
    )
    row = await cur.fetchone()
    return dict(row) if row else None


async def rename_device(db: Database, device_id: str, name: str) -> None:
    async with db.transaction():
        await db.conn.execute(
            "UPDATE devices SET name = ?, updated_at = ? WHERE id = ?",
            (name, time.time(), device_id),
        )


async def delete_device(db: Database, device_id: str) -> None:
    async with db.transaction():
        await db.conn.execute("DELETE FROM devices WHERE id = ?", (device_id,))


async def update_device_settings(
    db: Database,
    device_id: str,
    autotune_enabled: bool | None = None,
    target_temp_c: float | None = None,
    manual_fan_percent: float | None = None,
) -> None:
    fields: list[str] = []
    params: list[Any] = []
    if autotune_enabled is not None:
        fields.append("autotune_enabled = ?")
        params.append(int(autotune_enabled))
    if target_temp_c is not None:
        fields.append("target_temp_c = ?")
        params.append(target_temp_c)
    if manual_fan_percent is not None:
        fields.append("manual_fan_percent = ?")
        params.append(manual_fan_percent)
    if not fields:
        return
    params.append(device_id)
    async with db.transaction():
        await db.conn.execute(
            f"UPDATE device_settings SET {', '.join(fields)} WHERE device_id = ?",  # noqa: S608 — fields are fixed literals above, never user input
            params,
        )


# --- device state / samples -------------------------------------------------

async def upsert_device_state(
    db: Database,
    device_id: str,
    online: bool,
    last_error: str | None,
    latest: dict | None,
    best_diff: float | None = None,
    blocks_found: int | None = None,
) -> None:
    now = time.time() if online else None
    async with db.transaction():
        cur = await db.conn.execute(
            "SELECT best_diff, blocks_found FROM device_state WHERE device_id = ?", (device_id,)
        )
        row = await cur.fetchone()
        current_best = row["best_diff"] if row else 0.0
        current_blocks = row["blocks_found"] if row else 0
        next_best = max(current_best, best_diff) if best_diff is not None else current_best
        next_blocks = blocks_found if blocks_found is not None else current_blocks
        await db.conn.execute(
            """INSERT INTO device_state (device_id, online, last_seen, last_error, latest_json, best_diff, blocks_found)
               VALUES (?, ?, COALESCE(?, (SELECT last_seen FROM device_state WHERE device_id = ?)), ?, ?, ?, ?)
               ON CONFLICT(device_id) DO UPDATE SET
                 online = excluded.online,
                 last_seen = COALESCE(?, device_state.last_seen),
                 last_error = excluded.last_error,
                 latest_json = excluded.latest_json,
                 best_diff = excluded.best_diff,
                 blocks_found = excluded.blocks_found""",
            (
                device_id,
                int(online),
                now,
                device_id,
                last_error,
                json.dumps(latest or {}),
                next_best,
                next_blocks,
                now,
            ),
        )


async def insert_sample(db: Database, device_id: str, sample: dict) -> None:
    async with db.transaction():
        await db.conn.execute(
            """INSERT INTO samples
               (device_id, ts, hashrate_ghs, temp_c, fan_percent, fan_rpm, power_w,
                shares_accepted, shares_rejected, best_diff, uptime_s)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                device_id,
                sample.get("ts", time.time()),
                sample.get("hashrate_ghs"),
                sample.get("temp_c"),
                sample.get("fan_percent"),
                sample.get("fan_rpm"),
                sample.get("power_w"),
                sample.get("shares_accepted"),
                sample.get("shares_rejected"),
                sample.get("best_diff"),
                sample.get("uptime_s"),
            ),
        )


async def get_history(db: Database, device_id: str, since_ts: float, max_points: int = 500) -> list[dict]:
    """
    Return up to `max_points` samples for `device_id` since `since_ts`,
    bucketed/averaged evenly across the window so old, dense data does not
    overwhelm the chart or the response payload.
    """
    cur = await db.conn.execute(
        "SELECT COUNT(*) AS n FROM samples WHERE device_id = ? AND ts >= ?",
        (device_id, since_ts),
    )
    row = await cur.fetchone()
    total = row["n"] if row else 0
    if total == 0:
        return []

    bucket_size = max(1, total // max_points)
    cur = await db.conn.execute(
        """
        SELECT
            CAST(rn / ? AS INTEGER) AS bucket,
            AVG(ts) AS ts,
            AVG(hashrate_ghs) AS hashrate_ghs,
            AVG(temp_c) AS temp_c,
            AVG(fan_percent) AS fan_percent,
            AVG(fan_rpm) AS fan_rpm,
            AVG(power_w) AS power_w,
            MAX(shares_accepted) AS shares_accepted,
            MAX(shares_rejected) AS shares_rejected,
            MAX(best_diff) AS best_diff
        FROM (
            SELECT *, ROW_NUMBER() OVER (ORDER BY ts) - 1 AS rn
            FROM samples
            WHERE device_id = ? AND ts >= ?
        )
        GROUP BY bucket
        ORDER BY bucket ASC
        """,
        (bucket_size, device_id, since_ts),
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def prune_old_samples(db: Database, older_than_ts: float) -> int:
    async with db.transaction():
        cur = await db.conn.execute("DELETE FROM samples WHERE ts < ?", (older_than_ts,))
        return cur.rowcount


# --- notifications -----------------------------------------------------------

async def insert_notification(db: Database, device_id: str | None, kind: str, message: str) -> dict:
    now = time.time()
    async with db.transaction():
        cur = await db.conn.execute(
            "INSERT INTO notifications (device_id, kind, message, ts, read) VALUES (?, ?, ?, ?, 0)",
            (device_id, kind, message, now),
        )
        return {"id": cur.lastrowid, "device_id": device_id, "kind": kind, "message": message, "ts": now, "read": False}


async def list_notifications(db: Database, limit: int = 100) -> list[dict]:
    cur = await db.conn.execute(
        "SELECT * FROM notifications ORDER BY ts DESC LIMIT ?", (limit,)
    )
    rows = await cur.fetchall()
    return [dict(r) for r in rows]


async def mark_notifications_read(db: Database, ids: Iterable[int]) -> None:
    ids = list(ids)
    if not ids:
        return
    placeholders = ",".join("?" for _ in ids)
    async with db.transaction():
        await db.conn.execute(
            f"UPDATE notifications SET read = 1 WHERE id IN ({placeholders})",  # noqa: S608 — placeholders only, values bound below
            ids,
        )
