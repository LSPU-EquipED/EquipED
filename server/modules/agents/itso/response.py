"""ITSO response parsing and criterion conversion."""

from __future__ import annotations

import hashlib
import json
import re
import logging

logger = logging.getLogger(__name__)
from collections.abc import Iterable
from typing import Any

from ..contracts import AdvisoryOutput, CriterionScore, UngroundedCriterionAdvisory
from ..exceptions import AgentExecutionError


def _failure(category: str, value: Any) -> AgentExecutionError:
    reference = hashlib.sha256(str(value).encode()).hexdigest()[:16]
    return AgentExecutionError(f"{category} (reference: {reference})")

def _find_verbatim_substring(excerpt: str, source: str) -> str | None:
    """Locate excerpt in source, tolerating whitespace, quotes, dashes, and bullet variations."""
    if excerpt in source:
        return excerpt
    trans = str.maketrans({
        "“": '"', "”": '"', "‘": "'", "’": "'", "—": "-", "–": "-", "\xa0": " "
    })
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
            if end < len(source) and source[end] in ".?!;:" and excerpt.rstrip().endswith(source[end]):
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
                if end < len(source) and source[end] in ".?!;:" and excerpt.rstrip().endswith(source[end]):
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
                    if end < len(source) and source[end] in ".?!;:" and excerpt.rstrip().endswith(source[end]):
                        end += 1
                    return source[start:end]

    return None


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
ITSO_CHUNK_ID_MAX = 64
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
                            "uniqueItems": True,
                            "items": {
                                "type": "string",
                                "minLength": 1,
                                "maxLength": ITSO_CHUNK_ID_MAX,
                            },
                        },
                        "evidence": {
                            "type": "array",
                            "maxItems": 8,
                            "uniqueItems": True,
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
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_CHUNK_ID_MAX,
                        },
                    },
                    "evidence": {
                        "type": "array",
                        "maxItems": 8,
                        "uniqueItems": True,
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


def _unique_json_pairs_hook(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Decode JSON object while strictly rejecting duplicate keys."""
    res: dict[str, Any] = {}
    for key, val in pairs:
        if key in res:
            raise _failure("ITSODuplicateKey", key)
        res[key] = val
    return res


def build_response_schema(
    known_chunk_ids: Iterable[str],
    criteria_specs: tuple[tuple[str, str], ...] | None = None,
) -> dict[str, Any]:
    """Build a bounded contract for the immutable chunk-id set of one task."""
    ids = tuple(dict.fromkeys(str(chunk_id) for chunk_id in known_chunk_ids))
    chunk_schema = {
        "type": "array",
        "maxItems": 8 if ids else 0,
        "uniqueItems": True,
        "items": {"enum": list(ids)} if ids else False,
    }

    if criteria_specs is not None:
        prefix_items = [
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
                    "chunk_ids": chunk_schema,
                    "evidence": {
                        "type": "array",
                        "maxItems": 8,
                        "uniqueItems": True,
                        "items": {
                            "type": "string",
                            "minLength": 1,
                            "maxLength": ITSO_TEXT_MAX,
                        },
                    },
                },
            }
            for criterion_id, title in criteria_specs
        ]
        n_crit = len(criteria_specs)
        schema = {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "criterion_scores"],
            "properties": {
                "summary": {"type": "string", "minLength": 1, "maxLength": 2000},
                "criterion_scores": {
                    "type": "array",
                    "minItems": n_crit,
                    "maxItems": n_crit,
                    "prefixItems": prefix_items,
                    "items": False,
                    "unevaluatedItems": False,
                },
            },
        }
        return schema

    schema = json.loads(json.dumps(ITSO_RESPONSE_SCHEMA))
    scores = schema["properties"]["criterion_scores"]
    for item in (*scores["prefixItems"], scores["items"]):
        item["properties"]["chunk_ids"] = chunk_schema
    return schema


def parse_response(
    raw: str,
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    expected_titles: dict[str, str] | None = None,
    known_chunk_ids: Iterable[str] = (),
    packed_chunk_map: dict[str, str] | None = None,
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
        parsed = json.loads(payload, object_pairs_hook=_unique_json_pairs_hook)
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
        parsed,
        expected_ids=expected_ids_tuple,
        expected_titles=expected_titles,
        known_chunk_ids=known_chunk_ids,
        packed_chunk_map=packed_chunk_map,
    )
    return parsed


def criterion_scores(
    parsed: dict[str, Any],
    agent_name: str = "itso",
    *,
    expected_ids: Iterable[str] = ITSO_CRITERIA,
    expected_titles: dict[str, str] | None = None,
    known_chunk_ids: Iterable[str] = (),
    packed_chunk_map: dict[str, str] | None = None,
) -> tuple[CriterionScore, ...]:
    raw = parsed["criterion_scores"]
    expected = tuple(expected_ids)
    titles_map = (
        expected_titles if expected_titles is not None else ITSO_CRITERIA_TITLES
    )
    if set(titles_map) != set(expected):
        raise _failure("ITSOInvalidCriterionTitles", "missing_or_extra_ids")
    if packed_chunk_map is not None:
        known = set(packed_chunk_map.keys())
        if known_chunk_ids:
            known = known.intersection(set(known_chunk_ids))
    else:
        known = set(known_chunk_ids) if known_chunk_ids else None

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
            # For list format: require exact positional match expected_ids[index]
            if cid != expected[index]:
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
            entries_by_id[str(cid)] = dict(item)
    else:
        raise _failure("ITSOInvalidCriterionScores", type(raw).__name__)

    if set(entries_by_id) != set(expected):
        raise _failure("ITSOInvalidCriterion", "missing_or_extra_ids")

    result = []
    for cid in expected:
        item = entries_by_id[cid]
        # Canonical title derived from snapshot / expected_titles
        title = titles_map[cid]

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
        else:
            norm_chunk_ids = _normalize_chunk_ids(raw_chunk_ids, known=known)

        raw_evidence = item.get("evidence")
        if raw_evidence is None:
            norm_evidence: tuple[str, ...] = ()
        else:
            norm_evidence = _normalize_evidence(
                raw_evidence,
                chunk_ids=norm_chunk_ids,
                packed_chunk_map=packed_chunk_map,
            )

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
) -> tuple[UngroundedCriterionAdvisory, ...]:
    """Extract advisory output items for criteria scored without grounded evidence."""
    raw = parsed.get("criterion_scores")
    expected = tuple(expected_ids)
    ungrounded: list[UngroundedCriterionAdvisory] = []

    if isinstance(raw, dict):
        for cid in expected:
            val = raw.get(cid)
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                ungrounded.append(
                    UngroundedCriterionAdvisory(
                        criterion_id=cid,
                        reason=ITSO_UNGROUNDED_REASON,
                        advisory_only=True,
                    )
                )
            elif isinstance(val, dict):
                just = val.get("justification", "")
                chunks = val.get("chunk_ids", ())
                ev = val.get("evidence", ())
                if (not just or not str(just).strip()) or not chunks or not ev:
                    ungrounded.append(
                        UngroundedCriterionAdvisory(
                            criterion_id=cid,
                            reason=ITSO_UNGROUNDED_REASON,
                            advisory_only=True,
                        )
                    )
    elif isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                cid = item.get("criterion_id")
                if not isinstance(cid, str):
                    continue
                just = item.get("justification", "")
                chunks = item.get("chunk_ids", ())
                ev = item.get("evidence", ())
                if (not just or not str(just).strip()) or not chunks or not ev:
                    ungrounded.append(
                        UngroundedCriterionAdvisory(
                            criterion_id=cid,
                            reason=ITSO_UNGROUNDED_REASON,
                            advisory_only=True,
                        )
                    )

    return tuple(ungrounded)


def collect_advisory_outputs(
    parsed: dict[str, Any],
    expected_ids: Iterable[str] = ITSO_CRITERIA,
) -> AdvisoryOutput | None:
    """Collect advisory output items such as ungrounded criteria."""
    ungrounded = extract_ungrounded_criteria(parsed, expected_ids=expected_ids)
    if ungrounded:
        return AdvisoryOutput(ungrounded_criteria=ungrounded)
    return None


SYNTHETIC_OMISSION_MARKERS = (
    "...",
    "[...]",
    "…",
    "[omitted]",
    "[ellipsis]",
    "<omitted>",
    "(omitted)",
    "[deleted]",
    "[text omitted]",
)


def _contains_omission_marker(text: str) -> bool:
    trimmed = text.strip()
    if trimmed in SYNTHETIC_OMISSION_MARKERS:
        return True
    if any(
        marker in trimmed
        for marker in (
            "[...]",
            "[omitted]",
            "[ellipsis]",
            "<omitted>",
            "(omitted)",
            "[deleted]",
            "[text omitted]",
        )
    ):
        return True
    return False


def _normalize_chunk_ids(
    value: Any,
    known: set[str] | None = None,
) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        raise _failure("ITSOInvalidEvidence", "shape")
    if len(value) > 8:
        raise _failure("ITSOInvalidEvidence", "shape")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or not item.strip()
            or item != item.strip()
            or len(item) > ITSO_CHUNK_ID_MAX
        ):
            raise _failure("ITSOInvalidEvidence", "shape")
        if item in seen:
            raise _failure("ITSOInvalidEvidence", "duplicate_chunk_id")
        if known is not None and item not in known:
            raise _failure("ITSOUnknownChunk", "id")
        seen.add(item)
        normalized.append(item)
    return tuple(normalized)


def _normalize_evidence(
    value: Any,
    chunk_ids: tuple[str, ...],
    packed_chunk_map: dict[str, str] | None = None,
) -> tuple[str, ...]:
    if isinstance(value, str):
        value = [value]
    elif not isinstance(value, (list, tuple)):
        raise _failure("ITSOInvalidEvidence", "shape")
    if len(value) > 8:
        raise _failure("ITSOInvalidEvidence", "shape")
    normalized: list[str] = []
    seen: set[str] = set()
    for item in value:
        if (
            not isinstance(item, str)
            or not item
            or not item.strip()
            or item != item.strip()
            or len(item) > ITSO_TEXT_MAX
        ):
            raise _failure("ITSOInvalidEvidence", "shape")
        if _contains_omission_marker(item):
            raise _failure("ITSOInvalidEvidence", "omission_marker")
        if item in seen:
            raise _failure("ITSOInvalidEvidence", "duplicate_evidence")
        seen.add(item)
        normalized.append(item)

    if normalized:
        if not chunk_ids:
            raise _failure("ITSOInvalidEvidence", "evidence_without_chunk_id")
        if packed_chunk_map is not None:
            resolved_normalized: list[str] = []
            for ev in normalized:
                matched_chunk_ev = None
                for cid in chunk_ids:
                    if cid in packed_chunk_map:
                        matched = _find_verbatim_substring(ev, packed_chunk_map[cid])
                        if matched:
                            matched_chunk_ev = matched
                            break
                if not matched_chunk_ev:
                    for cid, text in packed_chunk_map.items():
                        matched = _find_verbatim_substring(ev, text)
                        if matched:
                            matched_chunk_ev = matched
                            break
                if not matched_chunk_ev:
                    logger.warning("ITSO_UNMATCHED_EVIDENCE: %r (chunk_ids=%r)", ev, chunk_ids)
                    raise _failure("ITSOInvalidEvidence", "ungrounded_evidence")
                resolved_normalized.append(matched_chunk_ev)
            normalized = resolved_normalized
    return tuple(normalized)
