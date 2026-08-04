"""Focused limiter tests for curriculum-alignment rate limiting."""

from __future__ import annotations

import concurrent.futures
import threading
import time

import pytest
from server.modules.curriculum_map.exceptions import AlignmentCheckRateLimitError
from server.modules.curriculum_map.limiter import AlignmentCheckLimiter


def test_limiter_releases_slot_after_successful_check() -> None:
    limiter = AlignmentCheckLimiter(max_global=1, max_per_user=1, wait_seconds=0.0)
    with limiter.acquire("user"):
        pass

    with limiter.acquire("user"):
        pass


def test_limiter_releases_slot_after_exception() -> None:
    limiter = AlignmentCheckLimiter(max_global=1, max_per_user=1, wait_seconds=0.0)

    with pytest.raises(RuntimeError):
        with limiter.acquire("user"):
            raise RuntimeError("boom")

    with limiter.acquire("user"):
        pass


def test_limiter_enforces_per_user_single_flight() -> None:
    limiter = AlignmentCheckLimiter(max_global=2, max_per_user=1, wait_seconds=0.0)

    with limiter.acquire("user"):
        with pytest.raises(AlignmentCheckRateLimitError):
            limiter.acquire("user")


def test_limiter_enforces_global_cap_with_concurrent_checks() -> None:
    limiter = AlignmentCheckLimiter(max_global=1, max_per_user=2, wait_seconds=0.0)
    results: dict[str, str] = {}
    release = threading.Event()
    acquired = threading.Event()

    def holder() -> None:
        try:
            with limiter.acquire("user-1"):
                results["holder"] = "acquired"
                acquired.set()
                release.wait(0.2)
        except AlignmentCheckRateLimitError:
            results["holder"] = "denied"

    def waiter() -> None:
        try:
            with limiter.acquire("user-2"):
                results["waiter"] = "acquired"
        except AlignmentCheckRateLimitError:
            results["waiter"] = "denied"

    thread_h = threading.Thread(target=holder, daemon=True)

    thread_h.start()
    acquired.wait(1)

    thread_w = threading.Thread(target=waiter, daemon=True)
    thread_w.start()
    thread_h.join(0.05)

    release.set()
    thread_h.join()
    thread_w.join()

    assert results["holder"] == "acquired"
    assert results["waiter"] == "denied"


def test_limiter_does_not_block_other_user_when_one_user_saturated() -> None:
    limiter = AlignmentCheckLimiter(max_global=2, max_per_user=1, wait_seconds=0.0)

    with limiter.acquire("user-1"):
        # Different user should still obtain the second global slot.
        with limiter.acquire("user-2"):
            pass

        # But same user remains blocked by per-user cap.
        with pytest.raises(AlignmentCheckRateLimitError):
            limiter.acquire("user-1")


def test_limiter_saturation_returns_retry_after() -> None:
    limiter = AlignmentCheckLimiter(max_global=1, max_per_user=1, wait_seconds=0.25)
    with limiter.acquire("user-1"):
        with pytest.raises(AlignmentCheckRateLimitError) as exc:
            limiter.acquire("user-2")

    assert exc.value.retry_after_seconds >= 1


def test_limiter_contention_bounded_wait_releases_threadpool() -> None:
    """Under same-user contention, only per-user slots are granted."""
    worker_count = 5
    max_per_user = 1
    wait_seconds = 0.5
    limiter = AlignmentCheckLimiter(
        max_global=worker_count,
        max_per_user=max_per_user,
        wait_seconds=wait_seconds,
    )

    barrier = threading.Barrier(worker_count)
    release_holder = threading.Event()
    in_flight = {"current": 0, "max": 0}
    state_lock = threading.Lock()

    def _attempt(_index: int) -> tuple[str, float, int | None]:
        start = time.monotonic()
        barrier.wait()
        try:
            with limiter.acquire("same-user"):
                with state_lock:
                    in_flight["current"] += 1
                    in_flight["max"] = max(in_flight["max"], in_flight["current"])
                # Hold slot slightly beyond the wait window so others are denied.
                release_holder.wait(wait_seconds + 0.2)
                with state_lock:
                    in_flight["current"] -= 1
                return "acquired", time.monotonic() - start, None
        except AlignmentCheckRateLimitError as exc:
            return "denied", time.monotonic() - start, exc.retry_after_seconds

    started = time.monotonic()
    with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as pool:
        futures = [pool.submit(_attempt, i) for i in range(worker_count)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    wall = time.monotonic() - started

    release_holder.set()

    granted = [outcome for outcome in results if outcome[0] == "acquired"]
    denied = [outcome for outcome in results if outcome[0] == "denied"]

    assert len(granted) == max_per_user
    assert len(denied) == worker_count - max_per_user
    assert all(
        retry_after is not None and retry_after > 0
        for _, __, retry_after in denied
    )
    assert all(
        isinstance(retry_after, int) and retry_after > 0
        for _, __, retry_after in denied
    )
    with state_lock:
        assert in_flight["max"] <= max_per_user

    assert wall < 1.0
    assert max(item[1] for item in denied) < 1.0
