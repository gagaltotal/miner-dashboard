"""
In-memory sliding-window rate limiter.

Deliberately dependency-free: a home dashboard is a single process, so we do
not need Redis or any shared store — a small `dict[str, deque]` guarded by an
`asyncio.Lock` is both correct and easy to audit. Every limiter instance is
keyed by an identity string the caller provides (usually the client IP,
sometimes "IP:username" for login) so different endpoints keep independent
budgets.

Trust boundary note: the "bypass rate limit" concern in the project brief
usually means an attacker spoofing `X-Forwarded-For` to reset their bucket.
We never trust that header — `request.client.host` is the actual TCP peer
address as seen by the ASGI server, which cannot be forged by the client.
"""
from __future__ import annotations

import asyncio
import time
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    def __init__(self, max_events: int, window_seconds: float) -> None:
        self.max_events = max_events
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str) -> bool:
        """Record an attempt for `key` and return whether it is within budget."""
        now = time.monotonic()
        async with self._lock:
            bucket = self._events[key]
            cutoff = now - self.window_seconds
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= self.max_events:
                return False
            bucket.append(now)
            return True

    async def retry_after(self, key: str) -> float:
        """Seconds until the oldest event in the current window expires."""
        now = time.monotonic()
        async with self._lock:
            bucket = self._events.get(key)
            if not bucket:
                return 0.0
            return max(0.0, self.window_seconds - (now - bucket[0]))

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._events.pop(key, None)


class LockoutTracker:
    """
    Tracks consecutive login failures per key and enforces a cooldown once a
    threshold is hit, independent of the sliding-window limiter above. This
    catches a slow-and-low brute force that stays under the per-minute rate
    limit but keeps guessing indefinitely.
    """

    def __init__(self, max_failures: int, lockout_seconds: float) -> None:
        self.max_failures = max_failures
        self.lockout_seconds = lockout_seconds
        self._failures: dict[str, int] = defaultdict(int)
        self._locked_until: dict[str, float] = {}
        self._lock = asyncio.Lock()

    async def is_locked(self, key: str) -> float:
        """Return remaining lockout seconds (0 if not locked)."""
        async with self._lock:
            until = self._locked_until.get(key)
            if until is None:
                return 0.0
            remaining = until - time.monotonic()
            if remaining <= 0:
                self._locked_until.pop(key, None)
                self._failures.pop(key, None)
                return 0.0
            return remaining

    async def record_failure(self, key: str) -> None:
        async with self._lock:
            self._failures[key] += 1
            if self._failures[key] >= self.max_failures:
                self._locked_until[key] = time.monotonic() + self.lockout_seconds

    async def record_success(self, key: str) -> None:
        async with self._lock:
            self._failures.pop(key, None)
            self._locked_until.pop(key, None)
