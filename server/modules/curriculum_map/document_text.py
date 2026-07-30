"""SLM clean-text extraction and evidence-page location.

``extract_document_pages`` mirrors ``engine_scoring.py``'s
``_load_document_text`` (same fitz-based clean PDF extraction so this
pipeline sees identical input to the SME engine -- never joined/overlapping
DB chunks), but returns one entry per page instead of a single joined
string, so evidence quotes can be located to a specific page number for the
frontend's click-to-scroll link.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

logger = logging.getLogger(__name__)


def extract_document_pages(document_id: uuid.UUID) -> list[str]:
    """Return the SLM's clean per-page text via PyMuPDF, or ``[]`` on failure."""
    try:
        import fitz  # PyMuPDF
        from server.core.database import get_session_factory
        from server.modules.documents.models import Document

        session = get_session_factory()()
        try:
            document = session.get(Document, document_id)
            file_path = getattr(document, "file_path", None) if document else None
        finally:
            session.close()

        if not file_path:
            return []
        path = Path(str(file_path))
        if not path.is_file():
            logger.warning("Curriculum alignment: PDF not found at %s", path)
            return []

        pages: list[str] = []
        with fitz.open(path) as pdf:
            for page in pdf:
                pages.append(page.get_text() or "")
        return pages
    except Exception as exc:
        logger.warning(
            "Curriculum alignment: clean PDF extraction failed: %s",
            str(exc)[:200],
        )
        return []


def find_evidence_page(pages: list[str], quote: str) -> int | None:
    """Return the 1-indexed page number of the first page containing ``quote``.

    Returns ``None`` if the quote is empty or not found on any page. Used
    both to ground an LLM's evidence claim (substring check) and to give
    the frontend a page number to jump to.
    """
    if not quote.strip():
        return None
    for index, page_text in enumerate(pages, start=1):
        if quote in page_text:
            return index
    return None


__all__ = ["extract_document_pages", "find_evidence_page"]
