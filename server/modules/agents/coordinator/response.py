"""Strict JSON schema and parser for Coordinator evaluation envelopes."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    CurriculumAlignmentConfig,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)

from ..exceptions import AgentExecutionError
from .slicing import GAP_MARKER

COORD_TEXT_MAX = 2000


def _optional_string_schema(max_length: int) -> dict[str, Any]:
    return {
        "anyOf": [
            {"type": "string", "minLength": 1, "maxLength": max_length},
            {"type": "null"},
        ]
    }


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


def _criterion_schema(criterion: CriterionDefinition) -> dict[str, Any]:
    config = criterion.strategy_config
    if isinstance(config, LlmRubricGuidanceConfig):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["criterion_id", "criterion_title", "score", "evidence"],
            "properties": {
                "criterion_id": {"const": criterion.criterion_code},
                "criterion_title": {"const": criterion.title},
                "score": {"type": "integer", "minimum": 1, "maximum": 4},
                "evidence": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": COORD_TEXT_MAX,
                },
                "reasoning": _optional_string_schema(COORD_TEXT_MAX),
            },
        }
    elif isinstance(config, CountBandConfig):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["criterion_id", "criterion_title", "instances"],
            "properties": {
                "criterion_id": {"const": criterion.criterion_code},
                "criterion_title": {"const": criterion.title},
                "instances": {
                    "type": "array",
                    "maxItems": 64,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["excerpt"],
                        "properties": {
                            "excerpt": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": COORD_TEXT_MAX,
                            },
                            "explanation": _optional_string_schema(COORD_TEXT_MAX),
                            "location": _optional_string_schema(100),
                        },
                    },
                },
                "summary": _optional_string_schema(COORD_TEXT_MAX),
            },
        }
    elif isinstance(config, RatioBandConfig):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "criterion_id",
                "criterion_title",
                "total_units",
                "qualifying_unit_ids",
                "has_measurable_content",
            ],
            "properties": {
                "criterion_id": {"const": criterion.criterion_code},
                "criterion_title": {"const": criterion.title},
                "total_units": {
                    "type": "array",
                    "maxItems": 64,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["unit_id", "evidence"],
                        "properties": {
                            "unit_id": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": 50,
                            },
                            "evidence": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": COORD_TEXT_MAX,
                            },
                            "label": _optional_string_schema(200),
                            "location": _optional_string_schema(100),
                        },
                    },
                },
                "qualifying_unit_ids": {
                    "type": "array",
                    "maxItems": 64,
                    "items": {"type": "string", "minLength": 1, "maxLength": 50},
                },
                "has_measurable_content": {"type": "boolean"},
                "summary": _optional_string_schema(COORD_TEXT_MAX),
            },
        }
    elif isinstance(config, CurriculumAlignmentConfig):
        return {
            "type": "object",
            "additionalProperties": False,
            "required": ["criterion_id", "criterion_title", "alignments"],
            "properties": {
                "criterion_id": {"const": criterion.criterion_code},
                "criterion_title": {"const": criterion.title},
                "alignments": {
                    "type": "array",
                    "maxItems": 100,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["objective_text", "is_aligned"],
                        "properties": {
                            "objective_text": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": COORD_TEXT_MAX,
                            },
                            "is_aligned": {"type": "boolean"},
                            "assessment_excerpt": {
                                "anyOf": [
                                    {
                                        "type": "string",
                                        "minLength": 1,
                                        "maxLength": COORD_TEXT_MAX,
                                    },
                                    {"type": "null"},
                                ]
                            },
                            "reasoning": _optional_string_schema(COORD_TEXT_MAX),
                        },
                    },
                },
                "summary": _optional_string_schema(COORD_TEXT_MAX),
            },
        }
    raise TypeError(f"unsupported Coordinator strategy config: {type(config).__name__}")


def build_envelope_schema(criteria: tuple[CriterionDefinition, ...]) -> dict[str, Any]:
    """Build dynamic strict JSON schema with exact positional criterion order."""
    item_schemas = [_criterion_schema(c) for c in criteria]
    return {
        "type": "object",
        "additionalProperties": False,
        "required": ["summary", "criterion_measurements"],
        "properties": {
            "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
            "criterion_measurements": {
                "type": "array",
                "minItems": len(criteria),
                "maxItems": len(criteria),
                "prefixItems": item_schemas,
                "items": False,
            },
        },
    }


def _hook_detect_duplicate_keys(pairs: list[tuple[str, Any]]) -> OrderedDict:
    """Per-object duplicate key detector for json.loads."""
    seen: dict[str, str] = {}
    for key, _val in pairs:
        lower = key.strip().casefold()
        if lower in seen:
            raise ValueError(
                f"duplicate key (case-insensitive): '{key}' "
                f"(first seen as '{seen[lower]}')"
            )
        seen[lower] = key
    return OrderedDict(pairs)


def _reject_score_fields(obj: Any, path: str = "") -> None:
    if isinstance(obj, (dict, OrderedDict)):
        for key, val in obj.items():
            if key.strip().casefold() in _SCORE_BLOCKLIST:
                raise AgentExecutionError(
                    f"Prohibited numeric-score field '{key}' at {path or 'root'}"
                )
            _reject_score_fields(val, f"{path}.{key}" if path else key)
    elif isinstance(obj, list):
        for idx, item in enumerate(obj):
            _reject_score_fields(item, f"{path}[{idx}]")


def parse_and_validate_envelope_response(
    raw_response: str,
    criteria: tuple[CriterionDefinition, ...],
    source_packet: str,
    curriculum_context: str,
) -> dict[str, Any]:
    """Strictly parse, validate, and ground a Coordinator envelope response.

    Raises AgentExecutionError on any schema, order, grounding, or constraint violation.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise AgentExecutionError("Coordinator response is empty or non-string")

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
        raise AgentExecutionError(
            f"Coordinator response is invalid JSON: {exc}"
        ) from exc

    if not isinstance(parsed, (dict, OrderedDict)):
        raise AgentExecutionError("Coordinator response must be a JSON object")

    if set(parsed) != {"summary", "criterion_measurements"}:
        raise AgentExecutionError(
            "Coordinator top-level keys must be exactly 'summary' and "
            f"'criterion_measurements', got {sorted(parsed)}"
        )

    summary = parsed.get("summary")
    if (
        not isinstance(summary, str)
        or not summary.strip()
        or summary != summary.strip()
        or len(summary) > 2000
    ):
        raise AgentExecutionError(
            "Coordinator response requires non-empty summary string (max 2000 chars)"
        )

    measurements = parsed.get("criterion_measurements")
    if not isinstance(measurements, list) or len(measurements) != len(criteria):
        got_len = (
            len(measurements)
            if isinstance(measurements, list)
            else type(measurements).__name__
        )
        raise AgentExecutionError(
            "Coordinator 'criterion_measurements' must have exactly "
            f"{len(criteria)} items, got {got_len}"
        )

    validated_measurements: list[dict[str, Any]] = []

    for idx, (m, crit) in enumerate(zip(measurements, criteria, strict=True)):
        if not isinstance(m, (dict, OrderedDict)):
            raise AgentExecutionError(
                f"Measurement at index {idx} must be a JSON object"
            )

        cid = m.get("criterion_id")
        if cid != crit.criterion_code:
            raise AgentExecutionError(
                f"Measurement at index {idx} has criterion_id '{cid}', "
                f"expected '{crit.criterion_code}'"
            )

        title = m.get("criterion_title")
        if title != crit.title:
            raise AgentExecutionError(
                f"Measurement at index {idx} has criterion_title '{title}', "
                f"expected '{crit.title}'"
            )

        config = crit.strategy_config
        if isinstance(config, LlmRubricGuidanceConfig):
            allowed_keys = {
                "criterion_id",
                "criterion_title",
                "score",
                "evidence",
                "reasoning",
            }
            extra = set(m) - allowed_keys
            if extra:
                raise AgentExecutionError(
                    f"Measurement '{cid}' has unexpected keys: {sorted(extra)}"
                )
            score = m.get("score")
            if (
                isinstance(score, bool)
                or not isinstance(score, int)
                or not (1 <= score <= 4)
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'score' must be integer 1..4, "
                    f"got {score!r}"
                )
            evidence = m.get("evidence")
            if (
                not isinstance(evidence, str)
                or not evidence.strip()
                or evidence != evidence.strip()
                or len(evidence) > COORD_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' requires non-empty string 'evidence' "
                    f"(max {COORD_TEXT_MAX} chars)"
                )
            if GAP_MARKER.strip() in evidence or evidence not in source_packet:
                raise AgentExecutionError(
                    f"Measurement '{cid}' evidence is not an exact substring of "
                    "source text"
                )
            reasoning = m.get("reasoning")
            if reasoning is not None and not _is_strict_optional_text(
                reasoning, COORD_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'reasoning' must be string "
                    f"(max {COORD_TEXT_MAX} chars)"
                )

        elif isinstance(config, CountBandConfig):
            _reject_score_fields(m, path=f"criterion_measurements[{idx}]")
            allowed_keys = {"criterion_id", "criterion_title", "instances", "summary"}
            extra = set(m) - allowed_keys
            if extra:
                raise AgentExecutionError(
                    f"Measurement '{cid}' has unexpected keys: {sorted(extra)}"
                )
            instances = m.get("instances")
            if not isinstance(instances, list) or len(instances) > 64:
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'instances' must be a list "
                    "(max 64 items)"
                )
            allowed_inst_keys = {"excerpt", "explanation", "location"}
            seen_excerpts: set[str] = set()
            for inst_idx, inst in enumerate(instances):
                if not isinstance(inst, (dict, OrderedDict)):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] must be a "
                        "JSON object"
                    )
                inst_extra = set(inst) - allowed_inst_keys
                if inst_extra:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] has unexpected "
                        f"keys: {sorted(inst_extra)}"
                    )
                excerpt = inst.get("excerpt")
                if (
                    not isinstance(excerpt, str)
                    or not excerpt.strip()
                    or excerpt != excerpt.strip()
                    or len(excerpt) > COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] requires "
                        "non-empty string 'excerpt'"
                    )
                if GAP_MARKER.strip() in excerpt or excerpt not in source_packet:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] excerpt is not "
                        "an exact substring of source text"
                    )
                norm_excerpt = " ".join(excerpt.split()).casefold()
                if norm_excerpt in seen_excerpts:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' contains duplicate instance excerpt"
                    )
                seen_excerpts.add(norm_excerpt)
                explanation = inst.get("explanation")
                if explanation is not None and not _is_strict_optional_text(
                    explanation, COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] explanation "
                        "must be string"
                    )
                loc = inst.get("location")
                if loc is not None and not _is_strict_optional_text(loc, 100):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] location "
                        "must be string <= 100 chars"
                    )
            count_summary = m.get("summary")
            if count_summary is not None and not _is_strict_optional_text(
                count_summary, COORD_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'summary' must be a nonblank, "
                    f"trimmed string (max {COORD_TEXT_MAX} chars)"
                )

        elif isinstance(config, RatioBandConfig):
            _reject_score_fields(m, path=f"criterion_measurements[{idx}]")
            allowed_keys = {
                "criterion_id",
                "criterion_title",
                "total_units",
                "qualifying_unit_ids",
                "has_measurable_content",
                "summary",
            }
            required_keys = {
                "criterion_id",
                "criterion_title",
                "total_units",
                "qualifying_unit_ids",
                "has_measurable_content",
            }
            missing_req = required_keys - set(m)
            if missing_req:
                raise AgentExecutionError(
                    f"Measurement '{cid}' missing required keys: {sorted(missing_req)}"
                )
            extra = set(m) - allowed_keys
            if extra:
                raise AgentExecutionError(
                    f"Measurement '{cid}' has unexpected keys: {sorted(extra)}"
                )

            has_measurable = m.get("has_measurable_content")
            if not isinstance(has_measurable, bool):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'has_measurable_content' must "
                    "be a boolean"
                )

            total_units = m.get("total_units")
            if not isinstance(total_units, list) or len(total_units) > 64:
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'total_units' must be a list "
                    "(max 64 items)"
                )

            qualifying_ids = m.get("qualifying_unit_ids")
            if not isinstance(qualifying_ids, list) or len(qualifying_ids) > 64:
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'qualifying_unit_ids' must be a list"
                )

            if not has_measurable and (len(total_units) > 0 or len(qualifying_ids) > 0):
                raise AgentExecutionError(
                    f"Measurement '{cid}' has_measurable_content=False requires "
                    "empty total_units and qualifying_unit_ids"
                )

            allowed_unit_keys = {"unit_id", "evidence", "label", "location"}
            seen_uids: set[str] = set()
            seen_evidences: set[str] = set()

            for unit_idx, unit in enumerate(total_units):
                if not isinstance(unit, (dict, OrderedDict)):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] must be a JSON object"
                    )
                unit_extra = set(unit) - allowed_unit_keys
                if unit_extra:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] has unexpected keys: "
                        f"{sorted(unit_extra)}"
                    )
                uid = unit.get("unit_id")
                if (
                    not isinstance(uid, str)
                    or not uid.strip()
                    or uid != uid.strip()
                    or len(uid) > 50
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] requires non-empty "
                        "string 'unit_id'"
                    )
                if uid in seen_uids:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' has duplicate unit_id '{uid}' "
                        "in total_units"
                    )
                seen_uids.add(uid)

                evidence = unit.get("evidence")
                if (
                    not isinstance(evidence, str)
                    or not evidence.strip()
                    or evidence != evidence.strip()
                    or len(evidence) > COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] requires non-empty "
                        f"string 'evidence'"
                    )
                if GAP_MARKER.strip() in evidence or evidence not in source_packet:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] evidence is not "
                        "an exact substring of source text"
                    )
                norm_ev = " ".join(evidence.split()).casefold()
                if norm_ev in seen_evidences:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' contains duplicate unit evidence "
                        "in total_units"
                    )
                seen_evidences.add(norm_ev)

                label = unit.get("label")
                if label is not None and not _is_strict_optional_text(label, 200):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] label must be a "
                        "nonblank, trimmed string <= 200 chars"
                    )
                location = unit.get("location")
                if location is not None and not _is_strict_optional_text(location, 100):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] location must be a "
                        "nonblank, trimmed string <= 100 chars"
                    )

            seen_qids: set[str] = set()
            for qid in qualifying_ids:
                if (
                    not isinstance(qid, str)
                    or not qid.strip()
                    or qid != qid.strip()
                    or len(qid) > 50
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' qualifying_unit_ids must contain "
                        "non-empty strings"
                    )
                if qid in seen_qids:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' contains duplicate qualifying_unit_id "
                        f"'{qid}'"
                    )
                if qid not in seen_uids:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' qualifying_unit_id '{qid}' does not "
                        "exist in total_units"
                    )
                seen_qids.add(qid)

            ratio_summary = m.get("summary")
            if ratio_summary is not None and not _is_strict_optional_text(
                ratio_summary, COORD_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'summary' must be a nonblank, "
                    f"trimmed string (max {COORD_TEXT_MAX} chars)"
                )

        elif isinstance(config, CurriculumAlignmentConfig):
            _reject_score_fields(m, path=f"criterion_measurements[{idx}]")
            allowed_keys = {
                "criterion_id",
                "criterion_title",
                "alignments",
                "summary",
            }
            extra = set(m) - allowed_keys
            if extra:
                raise AgentExecutionError(
                    f"Measurement '{cid}' has unexpected keys: {sorted(extra)}"
                )
            alignments = m.get("alignments")
            if not isinstance(alignments, list) or len(alignments) > 100:
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'alignments' must be a list "
                    "(max 100 items)"
                )
            allowed_row_keys = {
                "objective_text",
                "is_aligned",
                "assessment_excerpt",
                "reasoning",
            }
            rejected = 0
            for row_idx, row in enumerate(alignments):
                if not isinstance(row, (dict, OrderedDict)):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] must be a "
                        "JSON object"
                    )
                row_extra = set(row) - allowed_row_keys
                if row_extra:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] has unexpected "
                        f"keys: {sorted(row_extra)}"
                    )
                if "objective_text" not in row or "is_aligned" not in row:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] requires "
                        "'objective_text' and 'is_aligned'"
                    )
                objective_text = row.get("objective_text")
                if (
                    not isinstance(objective_text, str)
                    or not objective_text.strip()
                    or objective_text != objective_text.strip()
                    or len(objective_text) > COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] requires "
                        "non-empty string 'objective_text'"
                    )
                if (
                    GAP_MARKER.strip() in objective_text
                    or objective_text not in source_packet
                ):
                    raise AgentExecutionError(
                        f"Coordinator '{cid}' objective_text is not an exact "
                        "substring of source text"
                    )
                is_aligned = row.get("is_aligned")
                if not isinstance(is_aligned, bool):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] field "
                        "'is_aligned' must be a boolean"
                    )
                excerpt = row.get("assessment_excerpt")
                if excerpt is not None and not _is_strict_optional_text(
                    excerpt, COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] field "
                        "'assessment_excerpt' must be a nonblank, trimmed string"
                    )
                reasoning = row.get("reasoning")
                if reasoning is not None and not _is_strict_optional_text(
                    reasoning, COORD_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' alignment[{row_idx}] field "
                        "'reasoning' must be a string"
                    )
                if is_aligned is True:
                    if (
                        isinstance(excerpt, str)
                        and excerpt.strip()
                        and excerpt.strip() in curriculum_context
                    ):
                        pass
                    else:
                        row["is_aligned"] = False
                        row["assessment_excerpt"] = None
                        rejected += 1
                else:
                    row["assessment_excerpt"] = None
            curriculum_summary = m.get("summary")
            if curriculum_summary is not None and not _is_strict_optional_text(
                curriculum_summary, COORD_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'summary' must be a nonblank, "
                    f"trimmed string (max {COORD_TEXT_MAX} chars)"
                )
            m["_grounding_rejected_count"] = rejected

        validated_measurements.append(dict(m))

    return {
        "summary": str(summary),
        "criterion_measurements": validated_measurements,
    }


def _is_strict_optional_text(value: Any, max_length: int) -> bool:
    return (
        isinstance(value, str)
        and bool(value.strip())
        and value == value.strip()
        and len(value) <= max_length
    )


__all__ = [
    "build_envelope_schema",
    "parse_and_validate_envelope_response",
]
