"""
Central configuration for the miner dashboard backend.

Design goals for this module specifically:
- A single source of truth for every tunable value (no magic numbers scattered
  around the codebase).
- Safe-by-default: if the operator does not configure anything, the app should
  still come up in a locked-down, local-only, auth-required state.
- No secret ever lives in source control. The session-signing secret is
  generated on first run and stored on disk with restrictive permissions.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


def _env_bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    try:
        return int(val)
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    val = os.environ.get(name)
    if val is None or not val.strip():
        return default
    try:
        return float(val)
    except ValueError:
        return default


class Settings:
    # --- Paths -------------------------------------------------------
    # Everything the app writes lives under DATA_DIR. Keeping it a single,
    # well-known directory makes the path-safety checks in main.py (SPA
    # static-file serving) and the DB layer easy to reason about.
    DATA_DIR: Path = Path(os.environ.get("MINER_DASH_DATA_DIR", str(Path.home() / ".miner-dashboard"))).resolve()
    DB_PATH: Path = DATA_DIR / "dashboard.sqlite3"
    SECRET_KEY_PATH: Path = DATA_DIR / "secret.key"
    FRONTEND_DIST: Path = Path(os.environ.get("MINER_DASH_FRONTEND_DIST", str(Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"))).resolve()

    # --- Network -------------------------------------------------------
    HOST: str = os.environ.get("MINER_DASH_HOST", "0.0.0.0")
    PORT: int = _env_int("MINER_DASH_PORT", 8420)
    ENABLE_TLS: bool = _env_bool("MINER_DASH_ENABLE_TLS", False)
    TLS_CERT_PATH: Path = DATA_DIR / "tls_cert.pem"
    TLS_KEY_PATH: Path = DATA_DIR / "tls_key.pem"

    # Allow devices outside RFC1918/loopback/link-local to be added. Off by
    # default: this is a home-LAN tool and outbound connections should never
    # leave the local network unless an operator explicitly opts in.
    ALLOW_PUBLIC_TARGETS: bool = _env_bool("MINER_DASH_ALLOW_PUBLIC_TARGETS", False)

    # --- Polling / retention --------------------------------------------
    POLL_INTERVAL_SECONDS: float = _env_float("MINER_DASH_POLL_INTERVAL", 15.0)
    DEVICE_TIMEOUT_SECONDS: float = _env_float("MINER_DASH_DEVICE_TIMEOUT", 4.0)
    DISCOVERY_CONCURRENCY: int = _env_int("MINER_DASH_DISCOVERY_CONCURRENCY", 64)
    DISCOVERY_TIMEOUT_SECONDS: float = _env_float("MINER_DASH_DISCOVERY_TIMEOUT", 0.35)
    HISTORY_RETENTION_DAYS: int = _env_int("MINER_DASH_RETENTION_DAYS", 30)

    # --- Auth / sessions --------------------------------------------------
    SESSION_TTL_SECONDS: int = _env_int("MINER_DASH_SESSION_TTL", 60 * 60 * 24 * 14)  # 14 days
    COOKIE_NAME: str = "miner_dash_session"
    CSRF_COOKIE_NAME: str = "miner_dash_csrf"
    CSRF_HEADER_NAME: str = "X-CSRF-Token"

    # --- Rate limiting ------------------------------------------------
    LOGIN_RATE_LIMIT_ATTEMPTS: int = _env_int("MINER_DASH_LOGIN_ATTEMPTS", 5)
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = _env_int("MINER_DASH_LOGIN_WINDOW", 60)
    LOGIN_LOCKOUT_SECONDS: int = _env_int("MINER_DASH_LOGIN_LOCKOUT", 15 * 60)
    API_RATE_LIMIT_REQUESTS: int = _env_int("MINER_DASH_API_RATE_LIMIT", 120)
    API_RATE_LIMIT_WINDOW_SECONDS: int = _env_int("MINER_DASH_API_RATE_WINDOW", 60)
    CONTROL_RATE_LIMIT_REQUESTS: int = _env_int("MINER_DASH_CONTROL_RATE_LIMIT", 20)
    CONTROL_RATE_LIMIT_WINDOW_SECONDS: int = _env_int("MINER_DASH_CONTROL_RATE_WINDOW", 60)
    MAX_BODY_BYTES: int = _env_int("MINER_DASH_MAX_BODY_BYTES", 64 * 1024)  # 64 KiB is generous for our JSON bodies

    # --- Autotune safety bounds (advisory only — see services/autotune.py) --
    AUTOTUNE_MIN_TARGET_C: float = _env_float("MINER_DASH_AUTOTUNE_MIN_C", 45.0)
    AUTOTUNE_MAX_TARGET_C: float = _env_float("MINER_DASH_AUTOTUNE_MAX_C", 75.0)
    AUTOTUNE_HARD_CUTOFF_C: float = _env_float("MINER_DASH_AUTOTUNE_HARD_CUTOFF_C", 88.0)

    def __init__(self) -> None:
        self.DATA_DIR.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(self.DATA_DIR, 0o700)
        except OSError:
            pass  # best-effort on platforms without POSIX permission bits

    @property
    def secret_key(self) -> bytes:
        """
        Return the HMAC signing secret used for session/CSRF tokens, creating
        it on first run. Stored with 0600 permissions so only the OS user
        running the dashboard can read it.
        """
        if not self.SECRET_KEY_PATH.exists():
            key = secrets.token_bytes(32)
            self.SECRET_KEY_PATH.write_bytes(key)
            try:
                os.chmod(self.SECRET_KEY_PATH, 0o600)
            except OSError:
                pass
            return key
        return self.SECRET_KEY_PATH.read_bytes()


settings = Settings()
