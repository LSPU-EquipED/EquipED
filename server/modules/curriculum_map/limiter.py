"""Concurrency limiter for on-demand curriculum alignment checks.

This module enforces rate limits **within a single process** and is therefore
only fully contract-correct under the repo's single-process modular monolith
deployment contract. If ``WEB_CONCURRENCY > 1`` is used, each worker maintains
its own counters so global throughput/cooldown guarantees are advisory only.

The limiter enforces:
* global in-flight cap
* per-user in-flight cap
* bounded, non-blocking wait using a small queue wait budget

On exhaustion, the caller gets :class:`AlignmentCheckRateLimitError` with a
retry-after value suitable for a 429 response.
"""

from __future__ import annotations

import logging
import math
import threading
import time
from collections import deque
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from .exceptions import AlignmentCheckRateLimitError

logger = logging.getLogger(__name__)

_LOG_CAT_SLOT_ACQUIRE = "curriculum_alignment_limiter.acquire"
_LOG_CAT_SLOT_RELEASE = "curriculum_alignment_limiter.release"
_LOG_CAT_SLOT_WAIT = "curriculum_alignment_limiter.wait"
_LOG_CAT_SLOT_DENY = "curriculum_alignment_limiter.denied"

_WAIT_TIMEOUT_SECONDS_DEFAULT = 0.5


@dataclass
class _QueuedRequest:
    user_id: str
    deadline: float
    granted: bool = False


class _AlignmentSlot:
    """Reference counted slot handle.

    Always release in ``__exit__`` so route-level exception paths are safely
    cleaned up.
    """

    def __init__(self, limiter: AlignmentCheckLimiter, user_id: str) -> None:
        self._limiter = limiter
        self._user_id = user_id
        self._released = False

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._limiter._release(self._user_id)

    def __enter__(self) -> _AlignmentSlot:
        return self

    def __exit__(self, *_exc_info: object) -> None:
        self.release()


class AlignmentCheckLimiter:
    """Per-process limiter state for concurrent alignment checks."""

    def __init__(
        self,
        *,
        max_global: int,
        max_per_user: int,
        wait_seconds: float = _WAIT_TIMEOUT_SECONDS_DEFAULT,
    ) -> None:
        self._max_global = max_global
        self._max_per_user = max_per_user
        self._wait_seconds = max(wait_seconds, 0.0)
        self._global_inflight = 0
        self._per_user_inflight: dict[str, int] = {}
        self._waiting: deque[_QueuedRequest] = deque()
        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    @property
    def max_global(self) -> int:
        return self._max_global

    @property
    def max_per_user(self) -> int:
        return self._max_per_user

    def acquire(self, user_id: UUID | str) -> _AlignmentSlot:
        user_key = str(user_id)
        deadline = time.monotonic() + self._wait_seconds
        with self._cond:
            if self._try_allocate_locked(user_key):
                self._allocate_locked(user_key)
                self._log_acquire(user_key)
                return _AlignmentSlot(self, user_key)

            request = _QueuedRequest(user_id=user_key, deadline=deadline)
            self._waiting.append(request)
            self._log_wait(user_key)

            while True:
                if request.granted:
                    self._log_acquire(user_key)
                    return _AlignmentSlot(self, user_key)

                timeout = request.deadline - time.monotonic()
                if timeout <= 0:
                    self._remove_waiter(request)
                    self._log_deny(user_key)
                    retry_after = max(1, math.ceil(self._wait_seconds))
                    raise AlignmentCheckRateLimitError(
                        "alignment check request limit reached; retry later",
                        retry_after_seconds=retry_after,
                    )

                self._cond.wait(timeout=timeout)

    def _release(self, user_key: str) -> None:
        with self._cond:
            current_user_inflight = self._per_user_inflight.get(user_key, 0)
            if current_user_inflight <= 0:
                return

            self._global_inflight -= 1
            if current_user_inflight <= 1:
                self._per_user_inflight.pop(user_key, None)
            else:
                self._per_user_inflight[user_key] = current_user_inflight - 1
            self._log_release(user_key)
            self._drain_waiters_locked()
            self._cond.notify_all()

    def _try_allocate_locked(self, user_key: str) -> bool:
        return (
            self._global_inflight < self._max_global
            and self._per_user_inflight.get(user_key, 0) < self._max_per_user
        )

    def _allocate_locked(self, user_key: str) -> None:
        self._global_inflight += 1
        self._per_user_inflight[user_key] = (
            self._per_user_inflight.get(user_key, 0) + 1
        )

    def _drain_waiters_locked(self) -> None:
        # Best effort: grant earliest-compatible waiters until no capacity remains
        # or no waiter can satisfy both global and per-user caps.
        while self._global_inflight < self._max_global:
            granted_one = False
            for request in list(self._waiting):
                if self._try_allocate_locked(request.user_id):
                    self._waiting.remove(request)
                    self._allocate_locked(request.user_id)
                    request.granted = True
                    granted_one = True
                    self._cond.notify_all()
                    break
            if not granted_one:
                return

    def _remove_waiter(self, request: _QueuedRequest) -> None:
        try:
            self._waiting.remove(request)
        except ValueError:
            # Already granted/removed by another path.
            return

    def _log_acquire(self, _user_key: str) -> None:
        logger.info("limit slot acquired", extra={"category": _LOG_CAT_SLOT_ACQUIRE})

    def _log_wait(self, _user_key: str) -> None:
        logger.warning("limit slot wait", extra={"category": _LOG_CAT_SLOT_WAIT})

    def _log_release(self, _user_key: str) -> None:
        logger.debug("limit slot released", extra={"category": _LOG_CAT_SLOT_RELEASE})

    def _log_deny(self, _user_key: str) -> None:
        logger.warning("limit slot denied", extra={"category": _LOG_CAT_SLOT_DENY})


_GLOBAL_LOCK = threading.Lock()
_ACTIVE_LIMITER: AlignmentCheckLimiter | None = None
_ACTIVE_LIMITER_KEY: tuple[int, int] | None = None


def get_alignment_check_limiter(
    *, max_global: int, max_per_user: int
) -> AlignmentCheckLimiter:
    """Return the process-global limiter for the active limits.

    Keeping the limiter at module scope preserves per-process single-flight
    guarantees while allowing deterministic test reset by changing limits.
    """

    global _ACTIVE_LIMITER
    global _ACTIVE_LIMITER_KEY
    with _GLOBAL_LOCK:
        key = (max_global, max_per_user)
        if _ACTIVE_LIMITER is None or _ACTIVE_LIMITER_KEY != key:
            _ACTIVE_LIMITER = AlignmentCheckLimiter(
                max_global=max_global,
                max_per_user=max_per_user,
                wait_seconds=_WAIT_TIMEOUT_SECONDS_DEFAULT,
            )
            _ACTIVE_LIMITER_KEY = key
    return _ACTIVE_LIMITER


@contextmanager
def alignment_check_slot_context(
    *, user_id: UUID | str, max_global: int, max_per_user: int
) -> Iterator[None]:
    limiter = get_alignment_check_limiter(
        max_global=max_global,
        max_per_user=max_per_user,
    )
    slot = limiter.acquire(str(user_id))
    try:
        yield
    finally:
        slot.release()


__all__ = [
    "AlignmentCheckLimiter",
    "alignment_check_slot_context",
    "get_alignment_check_limiter",
]
