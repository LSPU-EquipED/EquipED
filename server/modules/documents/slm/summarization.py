"""SLM summary helpers."""

from __future__ import annotations

from collections.abc import Iterable


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


__all__ = ["build_document_summary", "build_section_summaries", "summarize_section"]
