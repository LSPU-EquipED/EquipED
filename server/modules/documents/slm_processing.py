"""SLM preprocessing orchestration and extraction helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

SECTION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "course_overview": (
        "course overview",
        "course description",
        "module overview",
        "introduction",
    ),
    "learning_outcomes": (
        "learning outcomes",
        "course outcomes",
        "intended learning outcomes",
        "objectives",
    ),
    "weekly_topics": (
        "weekly topics",
        "course outline",
        "schedule",
        "lesson plan",
        "modules",
    ),
    "assessment": (
        "assessment",
        "grading",
        "evaluation",
        "rubric",
    ),
    "policies": (
        "policy",
        "data privacy",
        "privacy",
        "ip",
        "intellectual property",
        "gender",
        "inclusivity",
    ),
    "references": (
        "references",
        "bibliography",
        "sources",
    ),
}


def _detect_section_name(text: str) -> str:
    lowered = text.lower()
    for section_name, keywords in SECTION_KEYWORDS.items():
        if any(keyword in lowered for keyword in keywords):
            return section_name
    return "general"


def build_outline(chunks: Iterable[dict[str, object]]) -> list[dict[str, object]]:
    """Group chunk evidence into a lightweight outline."""

    outline: list[dict[str, object]] = []
    section_index: dict[str, dict[str, object]] = {}

    for chunk in chunks:
        text = str(chunk.get("text", "")).strip()
        if not text:
            continue

        section_name = _detect_section_name(text)
        section = section_index.get(section_name)
        if section is None:
            section = {
                "section_id": section_name,
                "title": section_name.replace("_", " ").title(),
                "pages": [],
                "chunk_ids": [],
                "evidence": [],
            }
            section_index[section_name] = section
            outline.append(section)

        page_number = chunk.get("page_number")
        if isinstance(page_number, int) and page_number not in section["pages"]:
            section["pages"].append(page_number)

        chunk_id = chunk.get("chunk_id")
        if chunk_id is not None:
            section["chunk_ids"].append(str(chunk_id))

        if len(section["evidence"]) < 3:
            section["evidence"].append(text[:240])

    if not outline:
        outline.append(
            {
                "section_id": "general",
                "title": "General",
                "pages": [],
                "chunk_ids": [],
                "evidence": [],
            }
        )

    return outline


def summarize_section(section: dict[str, object]) -> str:
    evidence = [
        str(item).strip() for item in section.get("evidence", []) if str(item).strip()
    ]
    if not evidence:
        return ""
    summary = evidence[0]
    if len(evidence) > 1:
        summary = f"{summary} {evidence[1]}"
    return summary[:360]


def build_section_summaries(
    outline: Iterable[dict[str, object]],
) -> list[dict[str, object]]:
    summaries: list[dict[str, object]] = []
    for section in outline:
        summary = summarize_section(section)
        summaries.append(
            {
                "section_id": section.get("section_id"),
                "title": section.get("title"),
                "pages": section.get("pages", []),
                "summary": summary,
            }
        )
    return summaries


def build_document_summary(
    *,
    title: str,
    outline: Iterable[dict[str, object]],
    key_facts: dict[str, object],
) -> str:
    section_titles = [
        str(section.get("title", "")).strip()
        for section in outline
        if section.get("title")
    ]
    highlights = []
    if key_facts.get("has_privacy_language"):
        highlights.append("privacy language present")
    else:
        highlights.append("privacy language missing or weak")
    if key_facts.get("has_ip_language"):
        highlights.append("IP language present")
    if key_facts.get("has_inclusivity_language"):
        highlights.append("inclusivity language present")

    summary_parts = [f"{title} covers {', '.join(section_titles[:4])}".strip()]
    if highlights:
        summary_parts.append(f"Key signals: {', '.join(highlights)}.")
    if key_facts.get("outcome_mentions"):
        summary_parts.append(f"Outcome markers found: {key_facts['outcome_mentions']}.")
    return " ".join(part for part in summary_parts if part).strip()


def extract_key_facts(
    chunks: Iterable[dict[str, object]],
    *,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
) -> dict[str, object]:
    texts = [
        str(chunk.get("text", ""))
        for chunk in chunks
        if str(chunk.get("text", "")).strip()
    ]
    corpus = "\n".join(texts).lower()

    page_numbers = [
        chunk.get("page_number")
        for chunk in chunks
        if isinstance(chunk.get("page_number"), int)
    ]

    outcome_hits = len(
        re.findall(r"learning outcomes?|course outcomes?|objective[s]?", corpus)
    )
    assessment_weights = re.findall(r"\b\d{1,3}\s*%\b", corpus)

    return {
        "title": title,
        "course_title": course_title,
        "lesson_title": lesson_title,
        "program": program,
        "page_count": len(set(page_numbers)),
        "chunk_count": len(texts),
        "outcome_mentions": outcome_hits,
        "assessment_weights": assessment_weights,
        "has_inclusivity_language": any(
            token in corpus for token in ("gender", "inclusiv", "inclusive", "equity")
        ),
        "has_privacy_language": any(
            token in corpus
            for token in ("data privacy", "privacy", "personal data", "ra 10173")
        ),
        "has_ip_language": any(
            token in corpus
            for token in ("intellectual property", "ip policy", "copyright")
        ),
        "has_references_section": any(
            token in corpus for token in ("references", "bibliography", "sources")
        ),
    }


@dataclass(slots=True)
class SlmProcessingResult:
    document_summary: str
    document_outline: list[dict[str, object]]
    section_summaries: list[dict[str, object]]
    key_facts: dict[str, object]
    warnings: list[str]
    readiness_status: str


def normalize_text(text: str) -> str:
    text = re.sub(r"\r\n?", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def prepare_slm_package(
    chunks: Iterable[dict[str, object]],
    *,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
) -> SlmProcessingResult:
    normalized_chunks: list[dict[str, object]] = []
    for chunk in chunks:
        text = normalize_text(str(chunk.get("text", "")))
        if not text:
            continue
        normalized_chunks.append({**chunk, "text": text})

    document_outline = build_outline(normalized_chunks)
    section_summaries = build_section_summaries(document_outline)
    key_facts = extract_key_facts(
        normalized_chunks,
        title=title,
        course_title=course_title,
        lesson_title=lesson_title,
        program=program,
    )
    document_summary = build_document_summary(
        title=title,
        outline=document_outline,
        key_facts=key_facts,
    )

    warnings: list[str] = []
    if not key_facts.get("has_privacy_language"):
        warnings.append("Privacy language was not detected in the uploaded SLM.")
    if not key_facts.get("has_inclusivity_language"):
        warnings.append("Inclusivity language was not detected in the uploaded SLM.")
    if not key_facts.get("has_ip_language"):
        warnings.append(
            "IP or copyright language was not detected in the uploaded SLM."
        )

    readiness_status = "READY" if not warnings else "NEEDS_REVIEW"
    return SlmProcessingResult(
        document_summary=document_summary,
        document_outline=document_outline,
        section_summaries=section_summaries,
        key_facts=key_facts,
        warnings=warnings,
        readiness_status=readiness_status,
    )


__all__ = [
    "SECTION_KEYWORDS",
    "SlmProcessingResult",
    "build_document_summary",
    "build_outline",
    "build_section_summaries",
    "extract_key_facts",
    "normalize_text",
    "prepare_slm_package",
    "summarize_section",
]
