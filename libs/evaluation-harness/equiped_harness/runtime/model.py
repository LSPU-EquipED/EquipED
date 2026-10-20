"""Pure model boundary; transport, retries and security belong to the caller."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Protocol

from equiped_harness.runtime.context import _freeze


@dataclass(frozen=True, slots=True)
class ResponseContract:
    """Immutable response-format contract supplied for one completion."""

    mode: str
    schema_name: str | None = None
    schema: Mapping | None = None

    @classmethod
    def json_object(cls) -> ResponseContract:
        return cls("json_object")

    @classmethod
    def json_schema(cls, schema, name: str = "agent_response") -> ResponseContract:
        if not isinstance(schema, Mapping) or not schema:
            raise ValueError("Invalid bounded JSON Schema contract")
        if (
            not isinstance(name, str)
            or not 1 <= len(name) <= 64
            or not name.replace("_", "a").isalnum()
        ):
            raise ValueError("Invalid bounded JSON Schema contract")
        return cls("json_schema", name, _freeze(schema))  # type: ignore[arg-type]

    def __post_init__(self) -> None:
        if self.mode not in {"json_object", "json_schema"}:
            raise ValueError("Invalid response contract")
        if self.mode == "json_object":
            if self.schema_name is not None or self.schema is not None:
                raise ValueError("Invalid response contract")
            return
        if (
            not isinstance(self.schema_name, str)
            or not 1 <= len(self.schema_name) <= 64
            or not self.schema_name.replace("_", "a").isalnum()
            or not isinstance(self.schema, Mapping)
            or not self.schema
        ):
            raise ValueError("Invalid response contract")
        object.__setattr__(self, "schema", _freeze(self.schema))


@dataclass(frozen=True, slots=True)
class CompletionResult:
    """Deeply immutable, bounded completion metadata."""

    content: str
    served_model: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    finish_reason: str | None = None
    wall_seconds: float | None = None
    provider_seconds: float | None = None
    attempts: int = 1
    requested_max_tokens: int | None = None
    rate_fields: MappingProxyType | None = None
    output_cap_hit: bool = False
    response_format_downgraded: bool = False


def parse_json_payload(raw: str) -> dict[str, Any]:
    """Parse JSON from LLM responses, stripping code fences or preambles."""
    if not isinstance(raw, str):
        raise ValueError("raw response must be a string")
    payload = raw.strip()
    match = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.IGNORECASE | re.DOTALL
    )
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{") and not payload.startswith("["):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError(f"expected JSON object, got {type(parsed).__name__}")
    return parsed


class ModelClient(Protocol):
    model: str

    def generate_result(
        self,
        prompt: Any,
        *,
        temperature: float,
        max_new_tokens: int,
        deadline: float | None = None,
        response_contract: ResponseContract | None = None,
    ) -> CompletionResult: ...
