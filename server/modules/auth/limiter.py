"""Limiter for authentication and registration endpoints.

Thread-safe, process-local rate limiter using a sliding-window model with
bounded memory (LRU eviction).
Enforces independent client IP and hashed identity/token limits (no raw PII in
keys or logs).
"""

from __future__ import annotations

import collections
import hashlib
import logging
import threading
import time
from typing import NamedTuple

logger = logging.getLogger(__name__)

# Max keys in memory per limiter instance to prevent unbounded memory growth.
_MAX_ENTRIES = 10_000


class RateLimitResult(NamedTuple):
    allowed: bool
    retry_after: int


class AuthRateLimiter:
    """Thread-safe sliding-window rate limiter with bounded memory."""

    def __init__(
        self,
        *,
        max_requests: int,
        window_seconds: float,
        max_entries: int = _MAX_ENTRIES,
    ) -> None:
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._history: collections.OrderedDict[str, list[float]] = (
            collections.OrderedDict()
        )

    def check_and_record(self, key: str) -> RateLimitResult:
        """Check if request under `key` is allowed; if allowed, records it."""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            if key in self._history:
                self._history.move_to_end(key)
                timestamps = [t for t in self._history[key] if t > cutoff]
            else:
                timestamps = []
                if len(self._history) >= self._max_entries:
                    self._history.popitem(last=False)

            if len(timestamps) >= self._max_requests:
                oldest_in_window = timestamps[0]
                retry_after = max(
                    1, int((oldest_in_window + self._window_seconds) - now + 0.999)
                )
                self._history[key] = timestamps
                return RateLimitResult(allowed=False, retry_after=retry_after)

            timestamps.append(now)
            self._history[key] = timestamps
            return RateLimitResult(allowed=True, retry_after=0)

    def peek(self, key: str) -> RateLimitResult:
        """Check if request under `key` would be allowed without recording."""
        now = time.monotonic()
        cutoff = now - self._window_seconds

        with self._lock:
            if key in self._history:
                self._history.move_to_end(key)
                timestamps = [t for t in self._history[key] if t > cutoff]
            else:
                timestamps = []

            if len(timestamps) >= self._max_requests:
                oldest_in_window = timestamps[0]
                retry_after = max(
                    1, int((oldest_in_window + self._window_seconds) - now + 0.999)
                )
                return RateLimitResult(allowed=False, retry_after=retry_after)

            return RateLimitResult(allowed=True, retry_after=0)

    def reset(self) -> None:
        with self._lock:
            self._history.clear()


# Conservative process-local defaults per endpoint and dimension
# Shared registration cooldown (1 request / 60s per identity; DB is authoritative)
_shared_registration_cooldown = AuthRateLimiter(max_requests=1, window_seconds=60.0)

# Registration start/resend burst limiters (independent IP and identity dimensions)
_reg_flow_ip_limiter = AuthRateLimiter(max_requests=10, window_seconds=300.0)
_reg_flow_id_limiter = AuthRateLimiter(max_requests=5, window_seconds=300.0)

# OTP Verification limiters (independent IP and token dimensions)
_reg_verify_ip_limiter = AuthRateLimiter(max_requests=20, window_seconds=300.0)
_reg_verify_token_limiter = AuthRateLimiter(max_requests=10, window_seconds=300.0)

# Login rate limiters (independent IP and email dimensions)
_login_ip_limiter = AuthRateLimiter(max_requests=20, window_seconds=60.0)
_login_email_limiter = AuthRateLimiter(max_requests=5, window_seconds=60.0)


def hash_identifier(identifier: str) -> str:
    """Hash an identifier to avoid raw PII in cache keys and logs."""
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()[:16]


def get_client_ip(request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "127.0.0.1"


def _enforce_dual_limits(
    limiter_a: AuthRateLimiter,
    key_a: str,
    limiter_b: AuthRateLimiter,
    key_b: str,
) -> RateLimitResult:
    """Enforce two independent limits atomically with respect to consumption."""
    # Peek both first to avoid consuming from A if B is already exhausted
    peek_a = limiter_a.peek(key_a)
    if not peek_a.allowed:
        return peek_a
    peek_b = limiter_b.peek(key_b)
    if not peek_b.allowed:
        return peek_b

    # Both allowed, record both
    res_a = limiter_a.check_and_record(key_a)
    if not res_a.allowed:
        return res_a
    res_b = limiter_b.check_and_record(key_b)
    if not res_b.allowed:
        return res_b

    return RateLimitResult(allowed=True, retry_after=0)


def check_registration_start_limit(ip: str, email: str) -> RateLimitResult:
    key_email = hash_identifier(email)
    cooldown_key = f"reg_cooldown:{key_email}"

    # Check shared 60s cooldown per email identity first
    cooldown_res = _shared_registration_cooldown.check_and_record(cooldown_key)
    if not cooldown_res.allowed:
        return cooldown_res

    return _enforce_dual_limits(
        _reg_flow_ip_limiter,
        f"reg_start_ip:{ip}",
        _reg_flow_id_limiter,
        f"reg_start_id:{key_email}",
    )


def check_registration_resend_limit(ip: str, token: str) -> RateLimitResult:
    token_key = hash_identifier(token)
    cooldown_key = f"reg_cooldown_token:{token_key}"

    # Check shared 60s cooldown per token identity first
    cooldown_res = _shared_registration_cooldown.check_and_record(cooldown_key)
    if not cooldown_res.allowed:
        return cooldown_res

    return _enforce_dual_limits(
        _reg_flow_ip_limiter,
        f"reg_resend_ip:{ip}",
        _reg_flow_id_limiter,
        f"reg_resend_id:{token_key}",
    )


def check_registration_verify_limit(ip: str, token: str) -> RateLimitResult:
    token_key = hash_identifier(token)
    return _enforce_dual_limits(
        _reg_verify_ip_limiter,
        f"reg_verify_ip:{ip}",
        _reg_verify_token_limiter,
        f"reg_verify_id:{token_key}",
    )


def check_login_limit(ip: str, email: str) -> RateLimitResult:
    email_key = hash_identifier(email)
    return _enforce_dual_limits(
        _login_ip_limiter,
        f"login_ip:{ip}",
        _login_email_limiter,
        f"login_email:{email_key}",
    )


def reset_auth_limiters() -> None:
    """Deterministic reset for test fixtures."""
    _shared_registration_cooldown.reset()
    _reg_flow_ip_limiter.reset()
    _reg_flow_id_limiter.reset()
    _reg_verify_ip_limiter.reset()
    _reg_verify_token_limiter.reset()
    _login_ip_limiter.reset()
    _login_email_limiter.reset()
