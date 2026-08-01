"""Bounded, advisory SLM-topic to syllabus-outcome alignment."""

from __future__ import annotations

import json
from typing import Any

from server.modules.embeddings.collections import COL_REFERENCE_ALL
from server.modules.embeddings.retrieval import retrieve_context

_MAX_TOPIC_CHUNKS = 24
_MAX_CHUNK_CHARS = 900
_CANDIDATES_PER_TOPIC = 3


def unavailable(reason: str, syllabus_document_id: Any | None = None) -> dict[str, Any]:
    return {
        "status": "UNAVAILABLE",
        "statement": f"Content-syllabus alignment is unavailable: {reason}",
        "syllabus_document_id": str(syllabus_document_id)
        if syllabus_document_id
        else None,
        "total_topics": 0,
        "aligned_topics": 0,
        "outcome_matches": [],
        "unmatched_topics": [],
        "advisory_only": True,
    }


def evaluate(
    client: Any,
    chunk_infos: list[dict[str, Any]],
    syllabus_document_id: Any | None,
) -> dict[str, Any]:
    if syllabus_document_id is None:
        return unavailable("no syllabus was selected")

    topics = _extract_topics(client, chunk_infos)
    if not topics:
        return unavailable(
            "no substantial SLM topics could be identified", syllabus_document_id
        )

    candidate_groups: list[dict[str, Any]] = []
    for topic in topics:
        candidates = retrieve_context(
            topic["topic"],
            COL_REFERENCE_ALL,
            n_results=_CANDIDATES_PER_TOPIC,
            document_id_filter=str(syllabus_document_id),
        )
        valid = [
            {
                "chunk_id": item.chunk_id,
                "outcome_code": (item.section_ref or "").split(":", 1)[-1],
                "outcome_text": item.text,
                "page_number": item.page_number,
            }
            for item in candidates
            if item.chunk_id
            and (item.section_ref or "").startswith("syllabus_outcome:")
        ]
        if not valid:
            return unavailable(
                "selected syllabus outcomes could not be retrieved",
                syllabus_document_id,
            )
        candidate_groups.append({"topic": topic, "candidates": valid})

    decisions = _classify(client, candidate_groups)
    matches: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    for group in candidate_groups:
        topic = group["topic"]
        decision = decisions.get(topic["topic_id"])
        offered = {
            candidate["chunk_id"]: candidate for candidate in group["candidates"]
        }
        chosen_id = decision.get("syllabus_chunk_id") if decision else None
        if decision and decision.get("status") == "ALIGNED" and chosen_id in offered:
            candidate = offered[chosen_id]
            matches.append(
                {
                    **topic,
                    **candidate,
                    "status": "ALIGNED",
                    "rationale": str(decision.get("rationale", "")).strip(),
                }
            )
        else:
            unmatched.append(
                {
                    **topic,
                    "status": "NOT_ALIGNED",
                    "rationale": str(
                        (decision or {}).get(
                            "rationale", "No supported outcome match was found."
                        )
                    ).strip(),
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
    statement = {
        "MEETS": (
            "The SLM content meets the listed syllabus outcomes; every "
            "substantial topic maps to at least one outcome."
        ),
        "PARTIALLY_MEETS": (
            "The SLM content partially meets the listed syllabus outcomes; "
            "some substantial topics are outside the demonstrated outcome scope."
        ),
        "DOES_NOT_MEET": (
            "The SLM content does not meet the listed syllabus outcomes; no "
            "substantial topic has a supported outcome match."
        ),
    }[status]
    return {
        "status": status,
        "statement": statement,
        "syllabus_document_id": str(syllabus_document_id),
        "total_topics": total,
        "aligned_topics": aligned,
        "outcome_matches": matches,
        "unmatched_topics": unmatched,
        "advisory_only": True,
    }


def _extract_topics(
    client: Any, chunk_infos: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    allowed: dict[str, dict[str, Any]] = {}
    packed = []
    for info in chunk_infos[:_MAX_TOPIC_CHUNKS]:
        chunk_id = str(info.get("chunk_id", ""))
        text = str(info.get("text", ""))[:_MAX_CHUNK_CHARS]
        if not chunk_id or not text.strip():
            continue
        allowed[chunk_id] = info
        packed.append(
            {"chunk_id": chunk_id, "page_number": info.get("page_number"), "text": text}
        )
    prompt = json.dumps(
        {
            "task": (
                "Identify the substantial instructional content topics in these "
                "SLM chunks. Exclude navigation, directions, boilerplate, grading "
                "mechanics, and references."
            ),
            "document_chunks": packed,
            "output": {
                "topics": [
                    {
                        "topic_id": "T1",
                        "topic": "concise topic",
                        "slm_chunk_id": "exact supplied id",
                        "slm_evidence": "exact quote from that chunk",
                    }
                ]
            },
            "instructions": (
                "Return JSON only. Merge duplicates. Every evidence quote must "
                "occur verbatim in its cited chunk."
            ),
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    topics = []
    seen: set[str] = set()
    for item in data.get("topics", []):
        chunk_id = str(item.get("slm_chunk_id", ""))
        evidence = str(item.get("slm_evidence", "")).strip()
        topic = str(item.get("topic", "")).strip()
        source = allowed.get(chunk_id)
        if (
            not source
            or not topic
            or not evidence
            or evidence not in str(source.get("text", ""))
        ):
            continue
        key = topic.casefold()
        if key in seen:
            continue
        seen.add(key)
        topics.append(
            {
                "topic_id": f"T{len(topics) + 1}",
                "topic": topic,
                "slm_chunk_id": chunk_id,
                "slm_page_number": source.get("page_number"),
                "slm_evidence": evidence,
            }
        )
    return topics


def _classify(client: Any, groups: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    prompt = json.dumps(
        {
            "task": (
                "For each SLM topic, decide whether one supplied syllabus outcome "
                "substantively includes it. Use only the supplied candidates; "
                "lexical similarity alone is insufficient."
            ),
            "topic_candidates": groups,
            "output": {
                "decisions": [
                    {
                        "topic_id": "T1",
                        "status": "ALIGNED or NOT_ALIGNED",
                        "syllabus_chunk_id": (
                            "required exact candidate id when aligned, otherwise null"
                        ),
                        "rationale": "concise evidence-based reason",
                    }
                ]
            },
            "instructions": "Return JSON only. Do not invent outcomes or identifiers.",
        },
        ensure_ascii=False,
    )
    data = _json_generate(client, prompt)
    return {
        str(item.get("topic_id")): item
        for item in data.get("decisions", [])
        if item.get("status") in {"ALIGNED", "NOT_ALIGNED"}
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
