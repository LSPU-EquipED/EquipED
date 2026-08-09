"""Strict validation of the combined GAD extraction envelope."""

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from typing import Any

from ..exceptions import AgentExecutionError
from .grounding import MAX_INSTANCES_PER_CRITERION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1.1 — Extraction schema version (single source for envelope)
# Registry version lives in registry.REGISTRY_VERSION — DO NOT duplicate
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA_VERSION = "1.0.0"
"""Version of the combined extraction envelope schema."""


# ---------------------------------------------------------------------------
# Canonical section keys — the ONLY accepted top-level envelope keys.
# ---------------------------------------------------------------------------

CANONICAL_SECTION_KEYS: frozenset[str] = frozenset({
    "gad-01",
    "gad-02",
    "gad-03",
    "gad-04",
    "gad-05",
})

_INSTANCE_SECTION_KEYS: frozenset[str] = frozenset({
    "gad-01",
    "gad-03",
    "gad-04",
    "gad-05",
})

_BALANCE_SECTION_KEYS: frozenset[str] = frozenset({"gad-02"})

# ---------------------------------------------------------------------------
# Numeric-score blocklist — every known alias that assigns scores.
# ---------------------------------------------------------------------------

_SCORE_BLOCKLIST: frozenset[str] = frozenset({
    "score",
    "criterion_score",
    "numeric_score",
    "band",
    "score_band",
    "final_score",
    "subtotal",
    "rating",
    "grade",
    "mark",
    "points",
    "value",
    "result",
    "level",
})

# ---------------------------------------------------------------------------
# 1.2 — Strict combined response parsing with object_pairs_hook
# ---------------------------------------------------------------------------


def _hook_detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> OrderedDict:
    """``object_pairs_hook`` that raises on duplicate keys within the SAME
    JSON object (per-object scope, not global).
    """
    seen: dict[str, str] = {}
    for key, _val in pairs:
        lower = key.strip().lower()
        if lower in seen:
            raise ValueError(
                f"duplicate key (case-insensitive): '{key}' "
                f"(first occurrence as '{seen[lower]}')"
            )
        seen[lower] = key
    return OrderedDict(pairs)


def parse_combined_response(raw_response: str) -> dict[str, Any]:
    """Parse and strictly validate the combined GAD extraction envelope.

    * Uses ``object_pairs_hook`` to catch exact/case-insensitive duplicates
      **before** JSON construction.
    * Normalises all keys to canonical lower-case (``gad-01``…``gad-05``).
    * Rejects **any** key not in ``CANONICAL_SECTION_KEYS``.
    * Rejects any section containing a numeric-score blocklist field.
    * Validates each section's strict schema (field types, presence,
      non-empty summaries, prohibition of cross-type fields).
    * Returns a dict with exactly the five canonical keys.

    Raises ``AgentExecutionError`` on any violation — never defaults ``{}``.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise AgentExecutionError("GAD combined response is empty or non-string")

    payload = raw_response.strip()
    fenced = re.match(
        r"^```(?:json)?\s*(.*?)\s*```$",
        payload,
        flags=re.IGNORECASE | re.DOTALL,
    )
    if fenced:
        payload = fenced.group(1).strip()
    elif not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]

    try:
        parsed = json.loads(payload, object_pairs_hook=_hook_detect_duplicate_keys)
    except (json.JSONDecodeError, ValueError) as exc:
        msg = str(exc)
        if "duplicate key" in msg.lower():
            raise AgentExecutionError(
                f"GAD combined response has {msg}"
            ) from exc
        raise AgentExecutionError(
            f"GAD combined response is invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, (dict, OrderedDict)):
        raise AgentExecutionError("GAD combined response must be a JSON object")

    # --- Normalise keys to canonical lower-case ---
    normalised: dict[str, Any] = {}
    for raw_key, val in parsed.items():
        canonical_key = raw_key.strip().lower()
        normalised[canonical_key] = val

    # --- Reject unknown sections ---
    unknown = set(normalised) - CANONICAL_SECTION_KEYS
    if unknown:
        raise AgentExecutionError(
            f"GAD combined response contains unknown section(s): "
            f"{sorted(unknown)}"
        )

    # --- Reject missing required sections ---
    missing = CANONICAL_SECTION_KEYS - set(normalised)
    if missing:
        raise AgentExecutionError(
            f"GAD combined response missing required sections: {sorted(missing)}"
        )

    # --- Reject numeric-score fields at every level ---
    _reject_score_fields(normalised)

    # --- Validate each section's strict schema ---
    for section_key in CANONICAL_SECTION_KEYS:
        section_val = normalised[section_key]
        if not isinstance(section_val, dict):
            raise AgentExecutionError(
                f"GAD section '{section_key}' must be a JSON object, "
                f"got {type(section_val).__name__}"
            )
        _validate_section(section_key, section_val)

    return normalised


# ---------------------------------------------------------------------------
# Recursive score-field rejection
# ---------------------------------------------------------------------------


def _reject_score_fields(obj: Any, path: str = "") -> None:
    """Recursively reject any dict containing a blocklisted numeric-score key.

    Raises ``AgentExecutionError`` immediately on first prohibited field.
    """
    if isinstance(obj, dict):
        for key, val in obj.items():
            lower_key = key.strip().lower()
            if lower_key in _SCORE_BLOCKLIST:
                raise AgentExecutionError(
                    f"GAD combined response contains prohibited numeric-score "
                    f"field '{key}' at {path or 'root'}"
                )
            _reject_score_fields(val, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _reject_score_fields(item, f"{path}[{idx}]")


# ---------------------------------------------------------------------------
# Per-section strict schema validation
# ---------------------------------------------------------------------------

_ALLOWED_BALANCE_FIELDS: frozenset[str] = frozenset({
    "criterion",
    "female_count",
    "male_count",
    "summary",
})

_ALLOWED_INSTANCE_FIELDS: frozenset[str] = frozenset({
    "criterion",
    "instance_count",
    "instances",
    "summary",
})

_ALLOWED_INSTANCE_ITEM_FIELDS: frozenset[str] = frozenset({
    "excerpt",
    "chunk_id",
    "explanation",
})


def _validate_section(section_key: str, section_val: dict[str, Any]) -> None:
    """Validate a single criterion section's structure, field types, and allowlist."""
    lower_key = section_key.strip().lower()

    if lower_key in _BALANCE_SECTION_KEYS:
        # GAD-02: female_count, male_count, summary — reject any extra field
        extra = set(section_val) - _ALLOWED_BALANCE_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): "
                f"{sorted(extra)}"
            )
        for field in ("female_count", "male_count"):
            val = section_val.get(field)
            if not isinstance(val, int) or isinstance(val, bool) or val < 0:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' field '{field}' must be "
                    f"a non-negative integer, got {type(val).__name__}: {val}"
                )
        summary = section_val.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary"
            )
        # Reject instance-specific fields
        for banned in ("instances", "instance_count"):
            if banned in section_val:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' (balance) must not contain "
                    f"field '{banned}'"
                )

    elif lower_key in _INSTANCE_SECTION_KEYS:
        # GAD-01/03/04/05: instance_count, instances, summary — reject extra fields
        extra = set(section_val) - _ALLOWED_INSTANCE_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): "
                f"{sorted(extra)}"
            )
        instance_count = section_val.get("instance_count")
        if not isinstance(instance_count, int) or isinstance(
            instance_count, bool
        ) or instance_count < 0:
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instance_count' must be "
                f"a non-negative integer"
            )
        raw_instances = section_val.get("instances", [])
        if not isinstance(raw_instances, list):
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instances' must be a list"
            )
        summary = section_val.get("summary", "")
        if not isinstance(summary, str) or not summary.strip():
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary"
            )
        max_instances = MAX_INSTANCES_PER_CRITERION
        if len(raw_instances) > max_instances:
            logger.info(
                "GAD section '%s' returned %d instances, capping at %d",
                section_key,
                len(raw_instances),
                max_instances,
            )
        for idx, inst in enumerate(raw_instances[:max_instances]):
            if not isinstance(inst, dict):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] must be a JSON object"
                )
            extra_inst = set(inst) - _ALLOWED_INSTANCE_ITEM_FIELDS
            if extra_inst:
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] has unapproved "
                    f"field(s): {sorted(extra_inst)}"
                )
            excerpt = inst.get("excerpt", "")
            if not isinstance(excerpt, str) or not excerpt.strip():
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'excerpt'"
                )
            chunk_id = inst.get("chunk_id", "")
            if not isinstance(chunk_id, str) or not chunk_id.strip():
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'chunk_id'"
                )


