"""ITSO response parsing and criterion conversion."""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from ..contracts import CriterionScore
from ..exceptions import AgentExecutionError


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")


ITSO_RESPONSE_SCHEMA_VERSION = "itso-response-v1"
ITSO_CRITERIA_TITLES = {
    "ITSO-01": "No IP Issue — absence of plagiarism indicators",
    "ITSO-02": "Proper References — sources properly acknowledged",
    "ITSO-03": "Faculty Ownership — intellectual property rights respected",
    "ITSO-04": "Student Confidentiality — student data protected",
    "ITSO-05": "Teacher and Student Rights — digital rights preserved",
}
ITSO_CRITERIA = tuple(ITSO_CRITERIA_TITLES)
ITSO_TEXT_MAX = 2000
ITSO_CHUNK_ID_MAX = 2000
ITSO_UNGROUNDED_REASON = (
    "model score provided without justification or evidence grounding"
)
ITSO_RESPONSE_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["summary", "criterion_scores"],
    "properties": {
        "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
        "criterion_scores": {
            "type": "array",
            "minItems": 5,
            "maxItems": 5,
            "prefixItems": [
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "criterion_id",
                        "criterion_title",
                        "score",
                        "justification",
                        "chunk_ids",
                        "evidence",
                    ],
                    "properties": {
                        "criterion_id": {"const": criterion_id},
                        "criterion_title": {"const": title},
                        "score": {"type": "integer", "minimum": 1, "maximum": 4},
                        "justification": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_TEXT_MAX,
                        },
                        "chunk_ids": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": ITSO_CHUNK_ID_MAX,
                            },
                        },
                        "evidence": {
                            "type": "array",
                            "maxItems": 8,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": ITSO_TEXT_MAX,
                            },
                        },
                    },
                }
                for criterion_id, title in ITSO_CRITERIA_TITLES.items()
            ],
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "criterion_id",
                    "criterion_title",
                    "score",
                    "justification",
                    "chunk_ids",
                    "evidence",
                ],
                "properties": {
                    "criterion_id": {"type": "string", "maxLength": 32},
                    "criterion_title": {"type": "string", "maxLength": 256},
                    "score": {"type": "integer", "minimum": 1, "maximum": 4},
                    "justification": {
                        "type": "string",
                        "minLength": 1,
                        "maxLength": ITSO_TEXT_MAX,
                    },
                    "chunk_ids": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_CHUNK_ID_MAX,
                        },
                    },
                    "evidence": {
                        "type": "array",
                        "maxItems": 8,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_TEXT_MAX,
                        },
                    },
                },
            },
            "unevaluatedItems": False,
        },
    },
}


def build_response_schema(known_chunk_ids: Iterable[str]) -> dict[str, Any]:
    """Build a bounded contract for the immutable chunk-id set of one task."""
    ids = tuple(dict.fromkeys(str(chunk_id) for chunk_id in known_chunk_ids))
    schema = json.loads(json.dumps(ITSO_RESPONSE_SCHEMA))
    chunk_schema = {
        "type": "array",
        "maxItems": 8 if ids else 0,
        "items": {"enum": list(ids)} if ids else False,
    }
    scores = schema["properties"]["criterion_scores"]
    for item in (*scores["prefixItems"], scores["items"]):
        item["properties"]["chunk_ids"] = chunk_schema
    return schema


def parse_response(
    raw: str,
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    known_chunk_ids: Iterable[str] = (),
) -> dict[str, Any]:
    if not isinstance(raw, str):
        raise _failure("ITSOResponseTypeError", type(raw).__name__)
    payload = raw.strip()
    match = re.match(r"^```(?:json)?\s*(.*?)\s*```$", payload, flags=re.I | re.S)
    if match:
        payload = match.group(1).strip()
    elif not payload.startswith("{"):
        start = payload.find("{")
        end = payload.rfind("}")
        if start >= 0 and end > start:
            payload = payload[start : end + 1]
        else:
            raise _failure("ITSOInvalidJSON", raw)
    try:
        parsed = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise _failure("ITSOInvalidJSON", raw) from exc
    if not isinstance(parsed, dict):
        raise _failure("ITSOInvalidResponse", type(parsed).__name__)
    expected_ids_tuple = tuple(expected_ids)
    if "criterion_scores" not in parsed and any(
        k in expected_ids_tuple for k in parsed
    ):
        summary = str(parsed.pop("summary", "") or "")
        parsed = {"summary": summary, "criterion_scores": parsed}
    if parsed.get("summary") is None:
        parsed["summary"] = ""
    unknown = set(parsed) - {"summary", "criterion_scores"}
    if unknown:
        keys_str = ",".join(sorted(unknown))
        raise _failure("ITSOInvalidResponse", f"unknown_keys:{keys_str}")
    summary = parsed.get("summary")
    if not isinstance(summary, str) or not 0 <= len(summary) <= 2000:
        raise _failure("ITSOInvalidResponse", type(summary).__name__)
    if "criterion_scores" not in parsed or not isinstance(
        parsed.get("criterion_scores"), (list, dict)
    ):
        raise _failure(
            "ITSOInvalidCriterionScores", type(parsed.get("criterion_scores")).__name__
        )
    criterion_scores(
        parsed, expected_ids=expected_ids_tuple, known_chunk_ids=known_chunk_ids
    )
    return parsed


def criterion_scores(
    parsed: dict[str, Any],
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    known_chunk_ids: Iterable[str] = (),
) -> tuple[CriterionScore, ...]:
    raw = parsed["criterion_scores"]
    expected = tuple(expected_ids)
    known = set(known_chunk_ids)

    # Normalize dict format {"ITSO-01": 4, ...} or list of dicts to canonical entries
    entries_by_id: dict[str, dict[str, Any]] = {}
    if isinstance(raw, dict):
        for cid, val in raw.items():
            if not isinstance(cid, str) or cid not in expected:
                raise _failure("ITSOInvalidCriterion", cid)
            if isinstance(val, dict):
                entry = dict(val)
                entry["criterion_id"] = cid
                if set(entry) - {
                    "criterion_id",
                    "criterion_title",
                    "score",
                    "justification",
                    "chunk_ids",
                    "evidence",
                }:
                    raise _failure("ITSOInvalidCriterion", "extra_fields")
                entries_by_id[cid] = entry
            elif isinstance(val, int) and not isinstance(val, bool):
                entries_by_id[cid] = {"criterion_id": cid, "score": val}
            else:
                raise _failure("ITSOInvalidScore", cid)
    elif isinstance(raw, list):
        if len(raw) != len(expected):
            raise _failure("ITSOInvalidCriterionScores", "shape")
        for index, item in enumerate(raw):
            if not isinstance(item, dict):
                raise _failure("ITSOInvalidCriterion", index)
            cid = item.get("criterion_id")
            if not isinstance(cid, str) or cid not in expected or cid in entries_by_id:
                raise _failure("ITSOInvalidCriterion", cid or index)
            if set(item) - {
                "criterion_id",
                "criterion_title",
                "score",
                "justification",
                "chunk_ids",
                "evidence",
            }:
                raise _failure("ITSOInvalidCriterion", "extra_fields")
            entries_by_id[cid] = dict(item)
    else:
        raise _failure("ITSOInvalidCriterionScores", type(raw).__name__)

    if set(entries_by_id) != set(expected):
        raise _failure("ITSOInvalidCriterion", "missing_or_extra_ids")

    result = []
    for cid in expected:
        item = entries_by_id[cid]
        # Canonical title derived to be resilient against alterations or omissions
        title = ITSO_CRITERIA_TITLES[cid]

        score = item.get("score")
        if isinstance(score, bool) or not isinstance(score, int) or not 1 <= score <= 4:
            raise _failure("ITSOInvalidScore", cid)

        justification = item.get("justification", "")
        if not isinstance(justification, str):
            justification = ""
        if len(justification) > ITSO_TEXT_MAX:
            raise _failure("ITSOInvalidJustification", cid)

        raw_chunk_ids = item.get("chunk_ids")
        if raw_chunk_ids is None:
            norm_chunk_ids: tuple[str, ...] = ()
        elif isinstance(raw_chunk_ids, str):
            norm_chunk_ids = _normalize_text_tuple(
                [raw_chunk_ids] if raw_chunk_ids.strip() else [],
                ITSO_CHUNK_ID_MAX,
                known,
            )
        elif isinstance(raw_chunk_ids, (list, tuple)):
            norm_chunk_ids = _normalize_text_tuple(
                list(raw_chunk_ids), ITSO_CHUNK_ID_MAX, known
            )
        else:
            raise _failure("ITSOInvalidEvidence", "shape")

        raw_evidence = item.get("evidence")
        if raw_evidence is None:
            norm_evidence: tuple[str, ...] = ()
        elif isinstance(raw_evidence, str):
            norm_evidence = _normalize_text_tuple(
                [raw_evidence] if raw_evidence.strip() else [], ITSO_TEXT_MAX
            )
        elif isinstance(raw_evidence, (list, tuple)):
            norm_evidence = _normalize_text_tuple(list(raw_evidence), ITSO_TEXT_MAX)
        else:
            raise _failure("ITSOInvalidEvidence", "shape")

        result.append(
            CriterionScore(
                criterion_id=cid,
                criterion_title=title,
                score=score,
                justification=justification,
                chunk_ids=norm_chunk_ids,
                evidence=norm_evidence,
            )
        )

    return tuple(result)


def extract_ungrounded_criteria(
    parsed: dict[str, Any],
    expected_ids: Iterable[str] = ITSO_CRITERIA,
) -> list[dict[str, Any]]:
    """Extract advisory output items for criteria scored without grounded evidence."""
    raw = parsed.get("criterion_scores")
    expected = tuple(expected_ids)
    ungrounded: list[dict[str, Any]] = []

    if isinstance(raw, dict):
        for cid in expected:
            val = raw.get(cid)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                ungrounded.append(
                    {
                        "criterion_id": cid,
                        "reason": ITSO_UNGROUNDED_REASON,
                        "advisory_only": True,
                    }
                )
            elif isinstance(val, dict):
                just = val.get("justification", "")
                chunks = val.get("chunk_ids", ())
                ev = val.get("evidence", ())
                if (not just or not str(just).strip()) or not chunks or not ev:
                    ungrounded.append(
                        {
                            "criterion_id": cid,
                            "reason": ITSO_UNGROUNDED_REASON,
                            "advisory_only": True,
                        }
                    )
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                cid = item.get("criterion_id")
                just = item.get("justification", "")
                chunks = item.get("chunk_ids", ())
                ev = item.get("evidence", ())
                if (not just or not str(just).strip()) or not chunks or not ev:
                    ungrounded.append(
                        {
                            "criterion_id": cid,
                            "reason": ITSO_UNGROUNDED_REASON,
                            "advisory_only": True,
                        }
                    )

    return ungrounded


def collect_advisory_outputs(
    parsed: dict[str, Any],
    expected_ids: Iterable[str] = ITSO_CRITERIA,
) -> dict[str, Any] | None:
    """Collect advisory output items such as ungrounded criteria."""
    ungrounded = extract_ungrounded_criteria(parsed, expected_ids=expected_ids)
    if ungrounded:
        return {"ungrounded_criteria": ungrounded}
    return None


def _normalize_text_tuple(
    value: Any, max_length: int, known: set[str] | None = None
) -> tuple[str, ...]:
    if (
        not isinstance(value, list)
        or len(value) > 8
        or any(
            not isinstance(item, str) or not item or len(item) > max_length
            for item in value
        )
    ):
        raise _failure("ITSOInvalidEvidence", "shape")
    result = tuple(value)
    if known is not None and any(item not in known for item in result):
        raise _failure("ITSOUnknownChunk", "id")
    return result
