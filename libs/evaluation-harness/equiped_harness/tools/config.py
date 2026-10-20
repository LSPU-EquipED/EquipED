"""Explicit optional services supplied by the application boundary."""

from __future__ import annotations

from dataclasses import dataclass

from equiped_harness.tools.http import Transport


@dataclass(frozen=True, slots=True)
class ToolConfig:
    """Public-reference service configuration for ITSO adapter 3."""

    enabled: bool
    transport: Transport

    def __post_init__(self) -> None:
        if type(self.enabled) is not bool:
            raise TypeError("enabled must be bool")
        if self.transport is None or not callable(getattr(self.transport, "get", None)):
            raise TypeError("transport with async get(request, deadline) is required")
