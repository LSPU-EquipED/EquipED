"""Sorting policy for document listings."""

from __future__ import annotations

from typing import Any

from sqlalchemy import func

from .models import Document

DOCUMENT_SORTS = (
    "uploaded-desc",
    "uploaded-asc",
    "title-asc",
    "title-desc",
    "course-asc",
    "pages-desc",
)
DEFAULT_DOCUMENT_SORT = "uploaded-desc"
DOCUMENT_SORT_PATTERN = "^(" + "|".join(DOCUMENT_SORTS) + ")$"


def validate_document_sort(sort: str) -> None:
    if sort not in DOCUMENT_SORTS:
        raise ValueError(
            f"Invalid document sort. Allowed values: {', '.join(DOCUMENT_SORTS)}."
        )


def document_ordering(sort: str) -> tuple[Any, ...]:
    """Build SQL ordering expressions, including the stable ID tie-breaker."""
    validate_document_sort(sort)
    primary_ordering = {
        "uploaded-desc": Document.uploaded_at.desc(),
        "uploaded-asc": Document.uploaded_at.asc(),
        "title-asc": func.lower(Document.title).asc(),
        "title-desc": func.lower(Document.title).desc(),
        "course-asc": (
            func.lower(
                func.coalesce(
                    func.nullif(func.trim(Document.course_code), ""),
                    func.nullif(func.trim(Document.course_title), ""),
                )
            )
            .asc()
            .nulls_last()
        ),
        "pages-desc": Document.page_count.desc().nulls_last(),
    }
    return primary_ordering[sort], Document.document_id.asc()


def document_sort_key(item: Any, sort: str) -> tuple[Any, ...]:
    """Return the established in-memory ordering key for a document."""
    document_id = str(item.document_id)
    if sort == "uploaded-desc":
        return (-item.uploaded_at.timestamp(), document_id)
    if sort == "uploaded-asc":
        return (item.uploaded_at.timestamp(), document_id)
    if sort == "title-asc":
        return ((item.title or "").casefold(), document_id)
    if sort == "title-desc":
        # The infinity terminator keeps longer prefixes before shorter strings.
        reverse_title = tuple(-ord(char) for char in (item.title or "").casefold())
        return (reverse_title + (float("inf"),), document_id)
    if sort == "course-asc":
        course_code = (item.course_code or "").strip()
        course_title = (item.course_title or "").strip()
        value = (course_code or course_title).casefold()
        return (not value, value, document_id)
    if sort == "pages-desc":
        return (item.page_count is None, -(item.page_count or 0), document_id)
    validate_document_sort(sort)
    raise AssertionError("validated sort has no in-memory key")
