"""Bounded, advisory SLM-topic to syllabus-course-content alignment."""

from __future__ import annotations

import json
import re
from typing import Any

_TOPIC_BATCH_SIZE = 8
_MAX_SEGMENT_CHARS = 1200
_MAX_TOPIC_LABEL_WORDS = 12
_COVERAGE_BATCH_SIZE = 4
_SYLLABUS_BATCH_SIZE = 12
_CLASSIFICATION_TOPIC_BATCH_SIZE = 12
_SENTENCE_LIKE_START = re.compile(
    r"^(?:this|the)\s+(?:module|lesson|section|chapter)\b|"
    r"^(?:students?|learners?|teachers?|instructors?|you|we)\b",
    re.IGNORECASE,
)
_OBJECTIVE_LANGUAGE = re.compile(
    r"\b(?:will|shall|should)\s+(?:be\s+able\s+to\s+)?(?:learn|understand|"
    r"explain|identify|describe|discuss|demonstrate|create|apply)\b",
    re.IGNORECASE,
)
_CLAUSE_LANGUAGE = re.compile(
    r"\b(?:is|are|was|were|involves?|includes?|refers?|enables?|allows?|"
    r"provides?|introduces?|explains?|describes?|covers?|directs?|helps?)\b",
    re.IGNORECASE,
)
_IMPERATIVE_START = re.compile(
    r"^(?:configure|create|explain|identify|describe|discuss|apply|analyze|"
    r"evaluate|understand|define|compare|demonstrate)\b",
    re.IGNORECASE,
)


def unavailable(reason: str, syllabus_document_id: Any | None = None) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "statement": f"Content-syllabus alignment is unavailable: {reason}",
        "syllabus_document_id": str(syllabus_document_id)
        if syllabus_document_id
        else None,
        "total_topics": 0,
        "aligned_topics": 0,
        "content_matches": [],
        "unmatched_topics": [],
        "advisory_only": True,
    }


def _detailed_statement(
    status: str,
    total: int,
    aligned_names: list[str],
    outside_names: list[str],
) -> str:
    level_summary = {
        "MEETS": "The SLM meets the selected syllabus course contents.",
        "PARTIALLY_MEETS": (
            "The SLM partially meets the selected syllabus course contents."
        ),
        "DOES_NOT_MEET": "The SLM does not meet the selected syllabus course contents.",
    }[status]
    details = [
        level_summary,
        f"{len(aligned_names)} of {total} substantial topics have supported "
        "syllabus matches.",
    ]
    if aligned_names:
        details.append(f"Aligned topics: {'; '.join(aligned_names)}.")
    if outside_names:
        details.append(f"Topics outside the syllabus: {'; '.join(outside_names)}.")
    return " ".join(details)


def evaluate(
    client: Any,
    chunk_infos: list[dict[str, Any]],
    syllabus_document_id: Any | None,
    syllabus_contents: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Check that every substantive SLM topic is allowed by the syllabus list."""
    if syllabus_document_id is None:
        return unavailable("no syllabus was selected")
    if not syllabus_contents:
        return unavailable(
            "selected syllabus course contents are unavailable",
            syllabus_document_id,
        )

    topics = _extract_topics(client, chunk_infos)
    if not topics:
        return unavailable(
            "no substantial SLM topics could be identified", syllabus_document_id
        )

    matches_by_topic = _classify_against_complete_syllabus(
        client,
        topics,
        syllabus_contents,
    )
    matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for topic in topics:
        match = matches_by_topic.get(topic["topic_id"])
        if match:
            matches.append(
                {
                    **topic,
                    **match["content"],
                    "status": "ALIGNED",
                    "rationale": match["rationale"],
                }
            )
        else:
            unmatched.append(
                {
                    **topic,
                    "status": "NOT_ALIGNED",
                    "rationale": (
                        "No item in the selected syllabus Course Contents list "
                        "explicitly includes or clearly encompasses this SLM topic."
                    ),
                }
            )

    total = len(topics)
    aligned = len(matches)
    status = (
        "MEETS"
        if aligned == total
        else "DOES_NOT_MEET"
        if aligned == 0
        else "PARTIALLY_MEETS"
    )
    aligned_names = [str(item["topic"]) for item in matches]
    outside_names = [str(item["topic"]) for item in unmatched]
    statement = _detailed_statement(status, total, aligned_names, outside_names)
    return {
        "status": status,
        "statement": statement,
        "syllabus_document_id": str(syllabus_document_id),
        "total_topics": total,
        "aligned_topics": aligned,
        "content_matches": matches,
        "unmatched_topics": unmatched,
        "advisory_only": True,
    }


def _extract_topics(
    client: Any, chunk_infos: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Extract grounded concept labels from every non-empty SLM chunk."""
    packed: list[dict[str, Any]] = []
    allowed: dict[str, dict[str, Any]] = {}
    for info in chunk_infos:
        chunk_id = str(info.get("chunk_id", ""))
        text = str(info.get("text", ""))
        if not chunk_id or not text.strip():
            continue
        segments = _split_chunk_text(text)
        for segment_index, segment in enumerate(segments, start=1):
            segment_id = (
                chunk_id if len(segments) == 1 else f"{chunk_id}#S{segment_index}"
            )
            packed_info = {
                "slm_segment_id": segment_id,
                "chunk_id": chunk_id,
                "page_number": info.get("page_number"),
                "text": segment,
            }
            packed.append(packed_info)
            allowed[segment_id] = packed_info

    candidates: list[dict[str, Any]] = []
    for start in range(0, len(packed), _TOPIC_BATCH_SIZE):
        batch = packed[start : start + _TOPIC_BATCH_SIZE]
        candidates.extend(_extract_topic_batch(client, batch, allowed, start))
    if not candidates:
        return []
    covered = _verify_substantive_coverage(client, candidates)
    if not covered:
        return []
    return _consolidate_topics(client, covered)


def _split_chunk_text(text: str) -> list[str]:
    """Split oversized chunks without dropping any SLM content."""
    remaining = text.strip()
    segments: list[str] = []
    while len(remaining) > _MAX_SEGMENT_CHARS:
        boundary = max(
            remaining.rfind("\n", 0, _MAX_SEGMENT_CHARS),
            remaining.rfind(". ", 0, _MAX_SEGMENT_CHARS),
            remaining.rfind("; ", 0, _MAX_SEGMENT_CHARS),
        )
        if boundary < _MAX_SEGMENT_CHARS // 2:
            boundary = _MAX_SEGMENT_CHARS
        elif remaining[boundary : boundary + 2] in {". ", "; "}:
            boundary += 1
        segment = remaining[:boundary].strip()
        if segment:
            segments.append(segment)
        remaining = remaining[boundary:].strip()
    if remaining:
        segments.append(remaining)
    return segments


def _extract_topic_batch(
    client: Any,
    batch: list[dict[str, Any]],
    allowed: dict[str, dict[str, Any]],
    offset: int,
) -> list[dict[str, Any]]:
    prompt = json.dumps(
        {
            "task": (
                "Identify the substantive instructional concepts actually covered "
                "in these SLM chunks. A concept is covered only when it is explained, "
                "demonstrated, practiced, or assessed; an incidental mention is not "
                "coverage. Exclude navigation, directions, learning-objective wording "
                "without supporting discussion, metadata, boilerplate, grading "
                "mechanics, and references."
            ),
            "document_chunks": batch,
            "output": {
                "topics": [
                    {
                        "topic": "canonical concept label, normally 1 to 8 words",
                        "slm_segment_id": "exact supplied segment id",
                        "slm_evidence": (
                            "short exact quote proving substantive coverage"
                        ),
                        "coverage_reason": "how the quote demonstrates coverage",
                    }
                ]
            },
            "instructions": (
                "Return JSON only. The topic must be a noun-style concept, subject, "
                "method, theory, or skill label, not a sentence, claim, direction, or "
                "learning objective. Split distinct concepts only when each is "
                "substantively covered. Every evidence quote must occur verbatim in "
                "its cited chunk."
            ),
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    valid: list[dict[str, Any]] = []
    repairable: list[dict[str, Any]] = []
    for index, item in enumerate(data.get("topics", [])):
        segment_id = str(
            item.get("slm_segment_id") or item.get("slm_chunk_id") or ""
        )
        evidence = str(item.get("slm_evidence", "")).strip()
        topic = _normalize_topic_label(str(item.get("topic", "")))
        source = allowed.get(segment_id)
        if (
            not source
            or not evidence
            or evidence not in str(source.get("text", ""))
        ):
            continue
        candidate = {
            "candidate_id": f"B{offset // _TOPIC_BATCH_SIZE + 1}C{index + 1}",
            "topic": topic,
            "slm_chunk_id": source["chunk_id"],
            "slm_page_number": source.get("page_number"),
            "slm_evidence": evidence,
            "slm_context": source["text"],
            "coverage_reason": " ".join(
                str(item.get("coverage_reason", "")).split()
            ).strip(),
        }
        if _is_valid_topic_label(topic, evidence):
            valid.append(candidate)
        else:
            repairable.append(candidate)
    if repairable:
        valid.extend(_repair_topic_labels(client, repairable))
    return valid


def _normalize_topic_label(value: str) -> str:
    value = " ".join(value.split()).strip()
    value = re.sub(r"^(?:[-*•]+|\d+[.)])\s*", "", value)
    return value.strip(" \t\r\n\"'“”")


def _topic_key(value: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", value.casefold()))


def _is_valid_topic_label(topic: str, evidence: str) -> bool:
    words = re.findall(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)?", topic)
    if not words or len(words) > _MAX_TOPIC_LABEL_WORDS:
        return False
    if "\n" in topic or re.search(r"[.!?;]$", topic):
        return False
    if _SENTENCE_LIKE_START.search(topic) or _OBJECTIVE_LANGUAGE.search(topic):
        return False
    if _CLAUSE_LANGUAGE.search(topic) or _IMPERATIVE_START.search(topic):
        return False
    evidence_words = re.findall(r"[A-Za-z0-9]+", evidence)
    if _topic_key(topic) == _topic_key(evidence) and (
        len(evidence_words) > _MAX_TOPIC_LABEL_WORDS
        or re.search(r"[.!?;]$", evidence)
        or _SENTENCE_LIKE_START.search(evidence)
    ):
        return False
    return True


def _repair_topic_labels(
    client: Any, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    prompt = json.dumps(
        {
            "task": (
                "Rewrite each invalid sentence-like label as a concise noun-style "
                "instructional concept. Preserve its meaning and do not change the "
                "candidate identifier or evidence."
            ),
            "candidates": [
                {
                    "candidate_id": item["candidate_id"],
                    "invalid_label": item["topic"],
                    "slm_evidence": item["slm_evidence"],
                }
                for item in candidates
            ],
            "output": {
                "repairs": [
                    {
                        "candidate_id": "exact supplied id",
                        "topic": "canonical concept label",
                    }
                ]
            },
            "instructions": "Return JSON only. Do not return sentences or objectives.",
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    by_id = {item["candidate_id"]: item for item in candidates}
    repaired: list[dict[str, Any]] = []
    for item in data.get("repairs", []):
        candidate = by_id.get(str(item.get("candidate_id", "")))
        if not candidate:
            continue
        topic = _normalize_topic_label(str(item.get("topic", "")))
        if not _is_valid_topic_label(topic, candidate["slm_evidence"]):
            continue
        repaired.append({**candidate, "topic": topic})
    return repaired


def _verify_substantive_coverage(
    client: Any, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Fail closed when a candidate is merely mentioned rather than taught."""
    covered: list[dict[str, Any]] = []
    for start in range(0, len(candidates), _COVERAGE_BATCH_SIZE):
        batch = candidates[start : start + _COVERAGE_BATCH_SIZE]
        prompt = json.dumps(
            {
                "task": (
                    "Verify whether each candidate concept is substantively covered "
                    "by its SLM context. SUBSTANTIVE means the concept is explained, "
                    "demonstrated, practiced, or assessed. A title-only reference, "
                    "list entry, navigation label, objective without supporting "
                    "content, or incidental mention is MENTION_ONLY."
                ),
                "candidates": [
                    {
                        "candidate_id": item["candidate_id"],
                        "topic": item["topic"],
                        "slm_evidence": item["slm_evidence"],
                        "slm_context": item["slm_context"],
                        "extraction_reason": item["coverage_reason"],
                    }
                    for item in batch
                ],
                "output": {
                    "decisions": [
                        {
                            "candidate_id": "exact supplied id",
                            "coverage": "SUBSTANTIVE or MENTION_ONLY",
                            "rationale": "context-grounded reason",
                        }
                    ]
                },
                "instructions": (
                    "Return JSON only. Use only the supplied context. When evidence "
                    "is ambiguous, classify it as MENTION_ONLY."
                ),
            },
            ensure_ascii=False,
        )
        data = _json_generate(client, prompt)
        by_id = {item["candidate_id"]: item for item in batch}
        for decision in data.get("decisions", []):
            candidate = by_id.get(str(decision.get("candidate_id", "")))
            if candidate and decision.get("coverage") == "SUBSTANTIVE":
                covered.append(candidate)
    return covered


def _consolidate_topics(
    client: Any, candidates: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    if len(candidates) == 1:
        candidate = candidates[0]
        return [_public_topic(candidate, 1)]
    prompt = json.dumps(
        {
            "task": (
                "Merge only candidate labels that represent the same instructional "
                "concept across SLM chunks. Keep related theories, methods, and "
                "subtopics separate when they have distinct instructional meaning."
            ),
            "candidates": [
                {
                    "candidate_id": item["candidate_id"],
                    "topic": item["topic"],
                    "slm_evidence": item["slm_evidence"],
                }
                for item in candidates
            ],
            "output": {
                "topics": [
                    {
                        "canonical_topic": "concise concept label",
                        "representative_candidate_id": "exact supplied id",
                        "merged_candidate_ids": ["all equivalent supplied ids"],
                    }
                ]
            },
            "instructions": (
                "Return JSON only. Every candidate should appear in exactly one "
                "group. Do not merge a broad concept with a distinct narrower theory "
                "or method merely because their words overlap."
            ),
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    by_id = {item["candidate_id"]: item for item in candidates}
    used: set[str] = set()
    consolidated: list[dict[str, Any]] = []
    for group in data.get("topics", []):
        representative_id = str(group.get("representative_candidate_id", ""))
        representative = by_id.get(representative_id)
        merged_ids = [
            str(value)
            for value in group.get("merged_candidate_ids", [])
            if str(value) in by_id
        ]
        if not representative or representative_id in used:
            continue
        canonical = _normalize_topic_label(str(group.get("canonical_topic", "")))
        if not _is_valid_topic_label(canonical, representative["slm_evidence"]):
            canonical = representative["topic"]
        consolidated.append({**representative, "topic": canonical})
        used.update(merged_ids or [representative_id])
    for candidate in candidates:
        if candidate["candidate_id"] not in used:
            consolidated.append(candidate)
    return [_public_topic(item, index) for index, item in enumerate(consolidated, 1)]


def _public_topic(item: dict[str, Any], index: int) -> dict[str, Any]:
    return {
        "topic_id": f"T{index}",
        "topic": item["topic"],
        "slm_chunk_id": item["slm_chunk_id"],
        "slm_page_number": item.get("slm_page_number"),
        "slm_evidence": item["slm_evidence"],
    }


def _classify_against_complete_syllabus(
    client: Any,
    topics: list[dict[str, Any]],
    syllabus_contents: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    normalized_contents = [
        {
            "chunk_id": str(item.get("chunk_id", "")),
            "content_ref": str(item.get("content_ref", "")),
            "content_text": str(item.get("content_text", "")).strip(),
            "page_number": item.get("page_number"),
        }
        for item in syllabus_contents
        if item.get("chunk_id") and str(item.get("content_text", "")).strip()
    ]
    unresolved = {topic["topic_id"]: topic for topic in topics}
    matches: dict[str, dict[str, Any]] = {}
    for start in range(0, len(normalized_contents), _SYLLABUS_BATCH_SIZE):
        if not unresolved:
            break
        syllabus_batch = normalized_contents[start : start + _SYLLABUS_BATCH_SIZE]
        offered = {item["chunk_id"]: item for item in syllabus_batch}
        pending_topics = list(unresolved.values())
        for topic_start in range(
            0,
            len(pending_topics),
            _CLASSIFICATION_TOPIC_BATCH_SIZE,
        ):
            topic_batch = [
                topic
                for topic in pending_topics[
                    topic_start : topic_start + _CLASSIFICATION_TOPIC_BATCH_SIZE
                ]
                if topic["topic_id"] in unresolved
            ]
            if not topic_batch:
                continue
            decisions = _classify_syllabus_batch(
                client,
                topic_batch,
                syllabus_batch,
            )
            for topic_id, decision in decisions.items():
                chosen_id = str(decision.get("syllabus_chunk_id") or "")
                if decision.get("status") != "ALIGNED" or chosen_id not in offered:
                    continue
                matches[topic_id] = {
                    "content": offered[chosen_id],
                    "rationale": str(decision.get("rationale", "")).strip()
                    or "The syllabus entry substantively encompasses this SLM topic.",
                }
                unresolved.pop(topic_id, None)
    return matches


def _classify_syllabus_batch(
    client: Any,
    topics: list[dict[str, Any]],
    syllabus_batch: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    prompt = json.dumps(
        {
            "task": (
                "Treat the complete selected syllabus Course Contents as an "
                "authoritative allow-list. For each substantive SLM topic, decide "
                "whether one item in the supplied batch explicitly lists it or "
                "clearly encompasses it. The "
                "comparison is one-way: syllabus items absent from the SLM do not "
                "matter. Shared keywords alone are insufficient."
            ),
            "slm_topics": [
                {
                    "topic_id": item["topic_id"],
                    "topic": item["topic"],
                    "slm_evidence": item["slm_evidence"],
                }
                for item in topics
            ],
            "syllabus_course_contents": syllabus_batch,
            "output": {
                "decisions": [
                    {
                        "topic_id": "exact supplied topic id",
                        "status": "ALIGNED or NOT_ALIGNED",
                        "syllabus_chunk_id": (
                            "exact supplied syllabus id when aligned, otherwise null"
                        ),
                        "rationale": "concise evidence-based scope explanation",
                    }
                ]
            },
            "instructions": (
                "Return JSON only. A narrower SLM topic may align to a broader "
                "syllabus item only when the educational containment is clear from "
                "the supplied text. Do not invent content or identifiers."
            ),
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    allowed_topic_ids = {item["topic_id"] for item in topics}
    return {
        str(item.get("topic_id")): item
        for item in data.get("decisions", [])
        if str(item.get("topic_id")) in allowed_topic_ids
        and item.get("status") in {"ALIGNED", "NOT_ALIGNED"}
    }


def _json_generate(client: Any, prompt: str) -> dict[str, Any]:
    raw = client.generate(prompt, temperature=0.0, max_new_tokens=1800).strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:]
    parsed = json.loads(raw.strip())
    if not isinstance(parsed, dict):
        raise ValueError("alignment response must be a JSON object")
    return parsed


__all__ = ["evaluate", "unavailable"]
