"""Strict JSON schema and parser for SME evaluation envelopes."""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from typing import Any

from server.modules.rubrics.contracts import (
    CountBandConfig,
    CriterionDefinition,
    LlmRubricGuidanceConfig,
    RatioBandConfig,
)

from ..exceptions import AgentExecutionError
from .slicing import GAP_MARKER

SME_TEXT_MAX = 2000


def _find_verbatim_substring(excerpt: str, source: str) -> str | None:
    """Locate excerpt in source.

    Tolerates whitespace, quotes, dashes, and bullet variations.
    """
    if excerpt in source:
        return excerpt
    trans = str.maketrans(
        {"“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "\xa0": " "}
    )
    c_source = source.translate(trans)
    c_excerpt = excerpt.translate(trans)

    words = c_excerpt.split()
    if not words:
        return None
    pattern_simple = r"\s+".join(re.escape(w) for w in words)
    match_simple = re.search(pattern_simple, c_source, flags=re.IGNORECASE)
    if match_simple:
        return source[match_simple.start() : match_simple.end()]

    token_words = re.findall(r"\b\w+\b", c_excerpt)
    if not token_words:
        return None

    if len(token_words) >= 2:
        pattern_words = r"[\s\W_]+".join(re.escape(w) for w in token_words)
        match_words = re.search(pattern_words, c_source, flags=re.IGNORECASE)
        if match_words:
            start, end = match_words.start(), match_words.end()
            if (
                end < len(source)
                and source[end] in ".?!;:"
                and excerpt.rstrip().endswith(source[end])
            ):
                end += 1
            return source[start:end]

    if len(token_words) == 1:
        pattern_one = r"\b" + re.escape(token_words[0]) + r"\b"
        match_one = re.search(pattern_one, c_source, flags=re.IGNORECASE)
        if match_one:
            return source[match_one.start() : match_one.end()]

    if ":" in c_excerpt:
        sub = c_excerpt.split(":", 1)[1].strip()
        sub_tokens = re.findall(r"\b\w+\b", sub)
        if sub_tokens:
            p_sub = (
                r"\b" + re.escape(sub_tokens[0]) + r"\b"
                if len(sub_tokens) == 1
                else r"[\s\W_]+".join(re.escape(w) for w in sub_tokens)
            )
            match_sub = re.search(p_sub, c_source, flags=re.IGNORECASE)
            if match_sub:
                start, end = match_sub.start(), match_sub.end()
                if (
                    end < len(source)
                    and source[end] in ".?!;:"
                    and excerpt.rstrip().endswith(source[end])
                ):
                    end += 1
                return source[start:end]

    if len(token_words) >= 4:
        for window_size in range(len(token_words) - 1, 2, -1):
            for i in range(len(token_words) - window_size + 1):
                sub_tokens = token_words[i : i + window_size]
                p_window = r"[\s\W_]+".join(re.escape(w) for w in sub_tokens)
                m_window = re.search(p_window, c_source, flags=re.IGNORECASE)
                if m_window:
                    start, end = m_window.start(), m_window.end()
                    if (
                        end < len(source)
                        and source[end] in ".?!;:"
                        and excerpt.rstrip().endswith(source[end])
                    ):
                        end += 1
                    return source[start:end]

    return None


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
                    "maxLength": SME_TEXT_MAX,
                },
                "reasoning": _optional_string_schema(SME_TEXT_MAX),
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
                                "maxLength": SME_TEXT_MAX,
                            },
                            "explanation": _optional_string_schema(SME_TEXT_MAX),
                            "location": _optional_string_schema(100),
                        },
                    },
                },
                "summary": _optional_string_schema(SME_TEXT_MAX),
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
                                "maxLength": SME_TEXT_MAX,
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
                "summary": _optional_string_schema(SME_TEXT_MAX),
            },
        }
    raise TypeError(f"unsupported SME strategy config: {type(config).__name__}")


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
) -> dict[str, Any]:
    """Strictly parse, validate, and ground an SME envelope response.

    Raises AgentExecutionError on any schema, order, grounding, or constraint violation.
    """
    if not isinstance(raw_response, str) or not raw_response.strip():
        raise AgentExecutionError("SME response is empty or non-string")

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
        raise AgentExecutionError(f"SME response is invalid JSON: {exc}") from exc

    if not isinstance(parsed, (dict, OrderedDict)):
        raise AgentExecutionError("SME response must be a JSON object")

    if set(parsed) != {"summary", "criterion_measurements"}:
        raise AgentExecutionError(
            "SME top-level keys must be exactly 'summary' and "
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
            "SME response requires non-empty summary string (max 2000 chars)"
        )

    measurements = parsed.get("criterion_measurements")
    if not isinstance(measurements, list) or len(measurements) != len(criteria):
        got_len = (
            len(measurements)
            if isinstance(measurements, list)
            else type(measurements).__name__
        )
        raise AgentExecutionError(
            f"SME 'criterion_measurements' must have exactly {len(criteria)} items, "
            f"got {got_len}"
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

        m["criterion_title"] = crit.title

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
                or len(evidence) > SME_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' requires non-empty string 'evidence' "
                    f"(max {SME_TEXT_MAX} chars)"
                )
            matched_ev = _find_verbatim_substring(evidence, source_packet)
            if matched_ev is None or GAP_MARKER.strip() in matched_ev:
                raise AgentExecutionError(
                    f"Measurement '{cid}' evidence is not an exact substring of "
                    "source text"
                )
            m["evidence"] = matched_ev
            evidence = matched_ev
            reasoning = m.get("reasoning")
            if reasoning is not None and not _is_strict_optional_text(
                reasoning, SME_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'reasoning' must be string "
                    f"(max {SME_TEXT_MAX} chars)"
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
                    or len(excerpt) > SME_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] requires "
                        "non-empty string 'excerpt'"
                    )
                matched_excerpt = _find_verbatim_substring(excerpt, source_packet)
                if matched_excerpt is None or GAP_MARKER.strip() in matched_excerpt:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' instance[{inst_idx}] excerpt is not "
                        "an exact substring of source text"
                    )
                inst["excerpt"] = matched_excerpt
                excerpt = matched_excerpt
                norm_excerpt = " ".join(excerpt.split()).casefold()
                if norm_excerpt in seen_excerpts:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' contains duplicate instance excerpt"
                    )
                seen_excerpts.add(norm_excerpt)
                explanation = inst.get("explanation")
                if explanation is not None and not _is_strict_optional_text(
                    explanation, SME_TEXT_MAX
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
                count_summary, SME_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'summary' must be a nonblank, "
                    f"trimmed string (max {SME_TEXT_MAX} chars)"
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
                    or len(evidence) > SME_TEXT_MAX
                ):
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] requires non-empty "
                        f"string 'evidence'"
                    )
                matched_ev = _find_verbatim_substring(evidence, source_packet)
                if matched_ev is None or GAP_MARKER.strip() in matched_ev:
                    raise AgentExecutionError(
                        f"Measurement '{cid}' unit[{unit_idx}] evidence is not "
                        "an exact substring of source text"
                    )
                unit["evidence"] = matched_ev
                evidence = matched_ev
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
                ratio_summary, SME_TEXT_MAX
            ):
                raise AgentExecutionError(
                    f"Measurement '{cid}' field 'summary' must be a nonblank, "
                    f"trimmed string (max {SME_TEXT_MAX} chars)"
                )

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
