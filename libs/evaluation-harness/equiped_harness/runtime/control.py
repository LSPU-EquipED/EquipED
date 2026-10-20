"""Cooperative cancellation for synchronous harness work."""

from __future__ import annotations

from threading import Event


class ExecutionCancelledError(RuntimeError):
    """Raised at a cooperative checkpoint after cancellation is requested."""


class ExecutionControl:
    def __init__(self, cancel_event: Event | None = None) -> None:
        self.cancel_event = cancel_event or Event()

    def cancel(self) -> None:
        self.cancel_event.set()

    def check(self) -> None:
        if self.cancel_event.is_set():
            raise ExecutionCancelledError("Evaluation cancelled")
