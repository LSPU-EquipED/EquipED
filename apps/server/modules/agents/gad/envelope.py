"""Strict validation of the combined GAD extraction envelope."""

from __future__ import annotations

import json
import logging
import re
from collections import OrderedDict
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    RatioBandConfig,
)
from server.modules.rubrics.snapshot_contracts import EvaluationFormSnapshotDTO

from ..exceptions import AgentExecutionError
from .grounding import MAX_INSTANCES_PER_CRITERION

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 1.1 — Extraction schema version (single source for envelope)
# Registry version lives in registry.REGISTRY_VERSION — DO NOT duplicate
# ---------------------------------------------------------------------------

EXTRACTION_SCHEMA_VERSION = "2.0.0"
"""Version of the combined extraction envelope schema."""


def extraction_schema(form_snapshot: EvaluationFormSnapshotDTO) -> dict[str, Any]:
    """Return the strict Draft 2020-12 transport JSON schema for snapshot criteria."""
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise TypeError("form_snapshot must be an EvaluationFormSnapshotDTO instance")

    criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
    properties: dict[str, Any] = {}

    for crit in criteria:
        section_key = crit.criterion_code.strip().casefold()
        config = crit.strategy_config
        if isinstance(config, RatioBandConfig):
            properties[section_key] = {
                "type": "object",
                "additionalProperties": False,
                "required": ["female_count", "male_count", "summary"],
                "properties": {
                    "female_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100000,
                    },
                    "male_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100000,
                    },
                    "summary": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 4000,
                    },
                },
            }
        elif isinstance(config, CountBandConfig):
            properties[section_key] = {
                "type": "object",
                "additionalProperties": False,
                "required": ["instance_count", "instances", "summary"],
                "properties": {
                    "instance_count": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 100000,
                    },
                    "instances": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "additionalProperties": False,
                            "required": ["excerpt", "chunk_id"],
                            "properties": {
                                "excerpt": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 4000,
                                },
                                "chunk_id": {
                                    "type": "string",
                                    "minLength": 1,
                                    "maxLength": 50,
                                },
                                "explanation": {
                                    "type": "string",
                                    "maxLength": 4000,
                                },
                                "location": {
                                    "type": "string",
                                    "maxLength": 200,
                                },
                            },
                        },
                    },
                    "summary": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": 4000,
                    },
                },
            }
        else:
            raise ValueError(
                f"Unsupported strategy config for criterion {crit.criterion_code}"
            )

    return {
        "type": "object",
        "additionalProperties": False,
        "required": list(properties.keys()),
        "properties": properties,
    }


# ---------------------------------------------------------------------------
# Numeric-score blocklist — every known alias that assigns scores.
# ---------------------------------------------------------------------------

_SCORE_BLOCKLIST: frozenset[str] = frozenset(
    {
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
    }
)

# ---------------------------------------------------------------------------
# 1.2 — Strict combined response parsing with object_pairs_hook
# ---------------------------------------------------------------------------


def _hook_detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> OrderedDict:
    """``object_pairs_hook`` that raises on duplicate keys within the SAME
    JSON object (per-object scope, not global).
    """
    seen: dict[str, str] = {}
    for key, _val in pairs:
        lower = key.strip().casefold()
        if lower in seen:
            raise ValueError(
                f"duplicate key (case-insensitive): '{key}' "
                f"(first occurrence as '{seen[lower]}')"
            )
        seen[lower] = key
    return OrderedDict(pairs)


def parse_combined_response(
    raw_response: str,
    form_snapshot: EvaluationFormSnapshotDTO,
) -> dict[str, Any]:
    """Parse and strictly validate combined response against snapshot criteria.

    * Uses ``object_pairs_hook`` to catch exact/case-insensitive duplicates
      **before** JSON construction.
    * Normalises all keys to canonical lower-case via ``casefold()``.
    * Rejects **any** key not in snapshot section keys.
    * Rejects any section containing a numeric-score blocklist field.
    * Validates each section's strict schema based on its strategy shape.
    * Returns a dict with exactly the snapshot canonical keys.

    Raises ``AgentExecutionError`` on any violation — never defaults ``{}``.
    """
    if not isinstance(form_snapshot, EvaluationFormSnapshotDTO):
        raise TypeError("form_snapshot must be an EvaluationFormSnapshotDTO instance")

    if not isinstance(raw_response, str) or not raw_response.strip():
        raise AgentExecutionError("GAD combined response is empty or non-string")

    criteria = [c for d in form_snapshot.form.domains for c in d.criteria]
    expected_by_key: dict[str, CriterionDefinition] = {
        c.criterion_code.strip().casefold(): c for c in criteria
    }
    expected_section_keys = set(expected_by_key)

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
            raise AgentExecutionError(f"GAD combined response has {msg}") from exc
        raise AgentExecutionError(
            f"GAD combined response is invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, (dict, OrderedDict)):
        raise AgentExecutionError("GAD combined response must be a JSON object")

    # --- Normalise keys to canonical casefolded form ---
    normalised: dict[str, Any] = {}
    for raw_key, val in parsed.items():
        canonical_key = raw_key.strip().casefold()
        normalised[canonical_key] = val

    # --- Reject unknown sections ---
    unknown = set(normalised) - expected_section_keys
    if unknown:
        raise AgentExecutionError(
            f"GAD combined response contains unknown section(s): {sorted(unknown)}"
        )

    # --- Reject missing required sections ---
    missing = expected_section_keys - set(normalised)
    if missing:
        raise AgentExecutionError(
            f"GAD combined response missing required sections: {sorted(missing)}"
        )

    # --- Reject numeric-score fields at every level ---
    _reject_score_fields(normalised)

    # --- Validate each section's strict schema ---
    for section_key, crit_def in expected_by_key.items():
        section_val = normalised[section_key]
        if not isinstance(section_val, dict):
            raise AgentExecutionError(
                f"GAD section '{section_key}' must be a JSON object, "
                f"got {type(section_val).__name__}"
            )
        _validate_section_for_criterion(section_key, section_val, crit_def)

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
            lower_key = key.strip().casefold()
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

_ALLOWED_RATIO_FIELDS: frozenset[str] = frozenset(
    {
        "female_count",
        "male_count",
        "summary",
    }
)

_ALLOWED_COUNT_FIELDS: frozenset[str] = frozenset(
    {
        "instance_count",
        "instances",
        "summary",
    }
)

_ALLOWED_INSTANCE_ITEM_FIELDS: frozenset[str] = frozenset(
    {
        "excerpt",
        "chunk_id",
        "explanation",
        "location",
    }
)


def _validate_section_for_criterion(
    section_key: str,
    section_val: dict[str, Any],
    crit_def: CriterionDefinition,
) -> None:
    """Validate criterion section structure and field types based on strategy."""
    config = crit_def.strategy_config

    if isinstance(config, RatioBandConfig):
        extra = set(section_val) - _ALLOWED_RATIO_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): {sorted(extra)}"
            )
        for field in ("female_count", "male_count"):
            val = section_val.get(field)
            if (
                not isinstance(val, int)
                or isinstance(val, bool)
                or not 0 <= val <= 100000
            ):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' field '{field}' must be "
                    f"a non-negative integer, got {type(val).__name__}: {val}"
                )
        summary = section_val.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary "
                f"(max 4000 chars)"
            )
    elif isinstance(config, CountBandConfig):
        extra = set(section_val) - _ALLOWED_COUNT_FIELDS
        if extra:
            raise AgentExecutionError(
                f"GAD section '{section_key}' has unapproved field(s): {sorted(extra)}"
            )
        instance_count = section_val.get("instance_count")
        if (
            not isinstance(instance_count, int)
            or isinstance(instance_count, bool)
            or not 0 <= instance_count <= 100000
        ):
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instance_count' must be "
                f"a non-negative integer"
            )
        raw_instances = section_val.get("instances")
        if not isinstance(raw_instances, list):
            raise AgentExecutionError(
                f"GAD section '{section_key}' field 'instances' must be a list"
            )
        summary = section_val.get("summary")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 4000:
            raise AgentExecutionError(
                f"GAD section '{section_key}' requires a non-empty summary "
                f"(max 4000 chars)"
            )

        for idx, inst in enumerate(raw_instances):
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
            excerpt = inst.get("excerpt")
            if (
                not isinstance(excerpt, str)
                or not excerpt.strip()
                or len(excerpt) > 4000
            ):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'excerpt' (max 4000 chars)"
                )
            chunk_id = inst.get("chunk_id")
            if (
                not isinstance(chunk_id, str)
                or not chunk_id.strip()
                or len(chunk_id) > 50
            ):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] requires "
                    f"a non-empty 'chunk_id' (max 50 chars)"
                )
            explanation = inst.get("explanation")
            if explanation is not None and (
                not isinstance(explanation, str) or len(explanation) > 4000
            ):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] field 'explanation' "
                    f"must be a string (max 4000 chars)"
                )
            location = inst.get("location")
            if location is not None and (
                not isinstance(location, str) or len(location) > 200
            ):
                raise AgentExecutionError(
                    f"GAD section '{section_key}' instance[{idx}] field 'location' "
                    f"must be a string (max 200 chars)"
                )

        if len(raw_instances) > MAX_INSTANCES_PER_CRITERION:
            logger.info(
                "GAD section '%s' returned %d instances; applying max %d",
                section_key,
                len(raw_instances),
                MAX_INSTANCES_PER_CRITERION,
            )
            section_val["instances"] = raw_instances[:MAX_INSTANCES_PER_CRITERION]
    else:
        raise AgentExecutionError(
            f"Unsupported strategy config for criterion {crit_def.criterion_code}"
        )


__all__ = [
    "EXTRACTION_SCHEMA_VERSION",
    "extraction_schema",
    "parse_combined_response",
]
