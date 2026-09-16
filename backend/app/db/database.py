"""
SQLite connection management and schema.

SECURITY NOTE (read this before touching queries.py):
Every single SQL statement in this codebase — here and in queries.py — MUST
use `?` placeholders and pass values via the `parameters` argument. NEVER
build a query with an f-string, `.format()`, or `%` interpolation that
includes any value that originated from a request, a device response, or
user input. aiosqlite (like the stdlib sqlite3 it wraps) sends parameters to
SQLite separately from the query text, so a parameterized query cannot be
turned into a different query no matter what the value contains — this is
what actually prevents SQL injection, not "escaping".
"""
from __future__ import annotations

import contextlib
from pathlib import Path

import aiosqlite

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS operator (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    created_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS devices (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    name TEXT NOT NULL,
    host TEXT NOT NULL,
    port INTEGER NOT NULL,
    read_only INTEGER NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    extra_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS device_state (
    device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    online INTEGER NOT NULL DEFAULT 0,
    last_seen REAL,
    last_error TEXT,
    latest_json TEXT NOT NULL DEFAULT '{}',
    best_diff REAL NOT NULL DEFAULT 0,
    blocks_found INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT NOT NULL REFERENCES devices(id) ON DELETE CASCADE,
    ts REAL NOT NULL,
    hashrate_ghs REAL,
    temp_c REAL,
    fan_percent REAL,
    fan_rpm REAL,
    power_w REAL,
    shares_accepted REAL,
    shares_rejected REAL,
    best_diff REAL,
    uptime_s REAL
);
CREATE INDEX IF NOT EXISTS idx_samples_device_ts ON samples(device_id, ts);

CREATE TABLE IF NOT EXISTS notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id TEXT REFERENCES devices(id) ON DELETE CASCADE,
    kind TEXT NOT NULL,
    message TEXT NOT NULL,
    ts REAL NOT NULL,
    read INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_notifications_ts ON notifications(ts);

CREATE TABLE IF NOT EXISTS device_settings (
    device_id TEXT PRIMARY KEY REFERENCES devices(id) ON DELETE CASCADE,
    autotune_enabled INTEGER NOT NULL DEFAULT 0,
    target_temp_c REAL,
    manual_fan_percent REAL
);
"""


class Database:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(_SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected yet")
        return self._conn

    @contextlib.asynccontextmanager
    async def transaction(self):
        try:
            yield self.conn
            await self.conn.commit()
        except Exception:
            await self.conn.rollback()
            raise


db = Database(settings.DB_PATH)
