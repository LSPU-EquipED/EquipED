"""SLM key-fact extraction helpers."""

from __future__ import annotations

import re
from collections.abc import Iterable


def extract_key_facts(
    chunks: Iterable[dict[str, object]],
    *,
    title: str,
    course_title: str | None,
    lesson_title: str | None,
    program: str | None,
) -> dict[str, object]:
    texts = [str(chunk.get("text", "")) for chunk in chunks if str(chunk.get("text", "")).strip()]
    corpus = "\n".join(texts).lower()

    page_numbers = [
        chunk.get("page_number")
        for chunk in chunks
        if isinstance(chunk.get("page_number"), int)
    ]

    outcome_hits = len(re.findall(r"learning outcomes?|course outcomes?|objective[s]?", corpus))
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
            token in corpus for token in ("data privacy", "privacy", "personal data", "ra 10173")
        ),
        "has_ip_language": any(
            token in corpus for token in ("intellectual property", "ip policy", "copyright")
        ),
        "has_references_section": any(
            token in corpus for token in ("references", "bibliography", "sources")
        ),
    }


__all__ = ["extract_key_facts"]
