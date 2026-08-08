"""SLM outline detection helpers."""

from __future__ import annotations

from collections.abc import Iterable

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


__all__ = ["SECTION_KEYWORDS", "build_outline"]
