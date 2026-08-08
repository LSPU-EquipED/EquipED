"""SLM preprocessing orchestration."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from .key_facts import extract_key_facts
from .outline import build_outline
from .summarization import build_document_summary, build_section_summaries


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


__all__ = ["SlmProcessingResult", "normalize_text", "prepare_slm_package"]
