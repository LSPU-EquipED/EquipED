"""Persisted, OCR-aware SLM text extraction and evidence-page location.

``load_document_pages`` rebuilds deterministic per-page text from the
persisted ``DocumentChunk`` rows produced by Layer-1 ingestion -- never by
reopening the raw PDF. This is what makes scanned/OCR SLMs readable: OCR text
is already persisted as chunks, so there is no PDF reprocessing step that can
fail or degrade, and the text the pipeline consumes is exactly the text the
ingestion pipeline already validated.

Pages are ordered by (page_number, chunk_index, created_at) -- the same
deterministic order the documents module uses -- and grouped per page, so
prompt input, evidence grounding, and the reading pane all see identical page
text.

``select_pages_within_budget`` replaces arbitrary character head/tail cutting
with complete-page selection: a page is either sent whole or not at all, so
the LLM never sees a cut mid-sentence and coverage can be recorded honestly.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_WHITESPACE_RUN = re.compile(r"\s+")

#: Only SLM chunks are ever read here; non-SLM rows (policy, syllabus,
#: curriculum, ...) can never reach the LLM even if a stray row exists.
_SLM_SOURCE_TYPE = "slm"


@dataclass(frozen=True)
class DocumentPage:
    """One page of persisted, OCR-aware document text."""

    page_number: int
    text: str


def _normalize_whitespace(text: str) -> str:
    """Collapse any run of whitespace (including newlines) to a single space.

    PDFs wrap text with embedded newlines at each line break, but an LLM
    quoting that text back naturally flattens it into flowing prose (joining
    wrapped lines with a space instead of preserving the newline). Without
    this normalization, a substring check between the two would fail for
    almost every genuine quote, silently downgrading real matches to
    "not observed" (see find_evidence_page).
    """
    return _WHITESPACE_RUN.sub(" ", text).strip()


def load_document_pages(db: Any, document_id: uuid.UUID) -> list[DocumentPage]:
    """Build deterministic per-page text from persisted SLM chunks.

    Chunks are ordered by ``page_number`` then ``chunk_index`` (then
    ``created_at`` as a tiebreaker), and each page's text is the join of its
    chunks in that order. Chunks without a page number and non-SLM chunks are
    never used.

    Returns ``[]`` when the document has no usable persisted text -- the
    caller must fail honestly rather than fall back to raw PDF reopening.
    """
    from server.modules.documents.models import DocumentChunk

    rows = (
        db.query(DocumentChunk)
        .filter(
            DocumentChunk.document_id == document_id,
            DocumentChunk.source_type == _SLM_SOURCE_TYPE,
        )
        .order_by(
            DocumentChunk.page_number.asc().nullsfirst(),
            DocumentChunk.chunk_index.asc().nullsfirst(),
            DocumentChunk.created_at.asc(),
        )
        .all()
    )

    pages: list[DocumentPage] = []
    current_number: int | None = None
    current_parts: list[str] = []
    for chunk in rows:
        if chunk.page_number is None:
            continue
        text = (chunk.text or "").strip()
        if not text:
            continue
        if current_number is not None and chunk.page_number != current_number:
            pages.append(DocumentPage(current_number, "\n\n".join(current_parts)))
            current_parts = []
        current_number = chunk.page_number
        current_parts.append(text)
    if current_number is not None and current_parts:
        pages.append(DocumentPage(current_number, "\n\n".join(current_parts)))
    return pages


def find_evidence_page(pages: list[DocumentPage], quote: str) -> int | None:
    """Return the page number of the first evaluated page containing ``quote``.

    Returns ``None`` if the quote is empty or not found on any evaluated
    page. Used both to ground an LLM's evidence claim (substring check
    against evaluated pages only) and to give the frontend a page number to
    jump to.
    """
    normalized_quote = _normalize_whitespace(quote)
    if not normalized_quote:
        return None
    for page in pages:
        if normalized_quote in _normalize_whitespace(page.text):
            return page.page_number
    return None


def select_pages_within_budget(
    pages: list[DocumentPage],
    max_chars: int,
) -> tuple[list[DocumentPage], dict[str, Any]]:
    """Choose complete pages that fit within ``max_chars`` and report coverage.

    Pages are never cut mid-text: a page is included whole or not at all. If
    every page fits, the full set is returned with ``scope: full`` and
    strategy ``all_pages``. Otherwise a greedy prefix of complete pages is
    returned with ``scope: bounded`` and strategy ``prefix_pages``. If even
    the first page does not fit, the selection is empty and the caller must
    fail honestly.

    Returns ``(selected_pages, coverage)`` where ``coverage`` is the safe
    metadata block persisted alongside provenance -- it never contains
    document text or IDs.
    """
    total_chars = sum(len(page.text) for page in pages)
    if total_chars <= max_chars:
        return list(pages), {
            "scope": "full",
            "total_pages": len(pages),
            "evaluated_pages": len(pages),
            "total_chars": total_chars,
            "evaluated_chars": total_chars,
            "strategy": "all_pages",
        }

    selected: list[DocumentPage] = []
    used_chars = 0
    for page in pages:
        if used_chars + len(page.text) > max_chars:
            break
        selected.append(page)
        used_chars += len(page.text)

    return selected, {
        "scope": "bounded",
        "total_pages": len(pages),
        "evaluated_pages": len(selected),
        "total_chars": total_chars,
        "evaluated_chars": used_chars,
        "strategy": "prefix_pages",
    }


__all__ = [
    "DocumentPage",
    "load_document_pages",
    "find_evidence_page",
    "select_pages_within_budget",
]
