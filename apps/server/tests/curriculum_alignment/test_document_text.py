"""Unit tests for persisted, OCR-aware page text loading, the pure
evidence-page locator, and complete-page budget selection.

``load_document_pages`` reads persisted ``DocumentChunk`` rows only -- it
never reopens a raw PDF -- so scanned/OCR SLMs work purely off persisted text.
"""

from __future__ import annotations

import uuid

from server.modules.alignment.curriculum.document_text import (
    DocumentPage,
    find_evidence_page,
    load_document_pages,
    select_pages_within_budget,
)
from server.modules.documents.models import Document, DocumentChunk


def _make_document(db_session) -> Document:
    document = Document(
        title="Sample SLM",
        source_type="slm",
        file_path="/tmp/does-not-exist.pdf",
        uploaded_by=uuid.uuid4(),
    )
    db_session.add(document)
    db_session.commit()
    return document


def _add_chunk(
    db_session,
    document_id: uuid.UUID,
    *,
    text: str,
    page_number: int | None = 1,
    chunk_index: int | None = 0,
    source_type: str = "slm",
) -> None:
    db_session.add(
        DocumentChunk(
            document_id=document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=page_number,
            chunk_index=chunk_index,
            text=text,
        )
    )
    db_session.commit()


def test_load_document_pages_returns_empty_without_chunks(db_session) -> None:
    document = _make_document(db_session)
    assert load_document_pages(db_session, document.document_id) == []


def test_load_document_pages_groups_chunks_into_deterministic_pages(
    db_session,
) -> None:
    document = _make_document(db_session)
    # Inserted out of order on purpose: the loader must sort by
    # (page_number, chunk_index), not insertion order.
    _add_chunk(
        db_session, document.document_id, text="p2a", page_number=2, chunk_index=1
    )
    _add_chunk(
        db_session, document.document_id, text="p1b", page_number=1, chunk_index=1
    )
    _add_chunk(
        db_session, document.document_id, text="p1a", page_number=1, chunk_index=0
    )
    _add_chunk(
        db_session, document.document_id, text="p2b", page_number=2, chunk_index=2
    )

    pages = load_document_pages(db_session, document.document_id)

    assert [p.page_number for p in pages] == [1, 2]
    assert pages[0].text == "p1a\n\np1b"
    assert pages[1].text == "p2a\n\np2b"


def test_load_document_pages_skips_chunks_without_page_number(db_session) -> None:
    document = _make_document(db_session)
    _add_chunk(db_session, document.document_id, text="orphan", page_number=None)
    _add_chunk(
        db_session, document.document_id, text="real", page_number=1, chunk_index=1
    )

    pages = load_document_pages(db_session, document.document_id)

    assert [p.page_number for p in pages] == [1]
    assert "orphan" not in pages[0].text


def test_load_document_pages_never_reads_non_slm_chunks(db_session) -> None:
    document = _make_document(db_session)
    _add_chunk(
        db_session,
        document.document_id,
        text="POLICY-SECRET-CONTENT",
        page_number=1,
        chunk_index=0,
        source_type="policy",
    )
    _add_chunk(
        db_session,
        document.document_id,
        text="slm",
        page_number=1,
        chunk_index=1,
    )

    pages = load_document_pages(db_session, document.document_id)

    assert len(pages) == 1
    assert "POLICY-SECRET-CONTENT" not in pages[0].text
    assert pages[0].text == "slm"


def test_finds_page_containing_exact_quote() -> None:
    pages = [
        DocumentPage(1, "Intro text."),
        DocumentPage(2, "Students design a linked list from scratch."),
        DocumentPage(3, "Summary."),
    ]
    assert find_evidence_page(pages, "design a linked list") == 2


def test_returns_none_when_quote_not_found() -> None:
    pages = [DocumentPage(1, "Intro text."), DocumentPage(2, "Body text.")]
    assert find_evidence_page(pages, "nonexistent quote") is None


def test_returns_none_for_empty_quote() -> None:
    pages = [DocumentPage(1, "Intro text.")]
    assert find_evidence_page(pages, "") is None


def test_returns_first_matching_page_when_quote_repeats() -> None:
    pages = [
        DocumentPage(1, "First mention of teamwork."),
        DocumentPage(2, "Second mention of teamwork."),
    ]
    assert find_evidence_page(pages, "teamwork") == 1


def test_returns_real_page_number_not_list_position() -> None:
    # Page numbers need not be contiguous (OCR/empty pages are simply absent).
    pages = [DocumentPage(3, "content here."), DocumentPage(7, "more content.")]
    assert find_evidence_page(pages, "content here") == 3


def test_matches_quote_across_a_pdf_line_wrap() -> None:
    """Regression test: PDFs wrap text with embedded newlines at each line
    break, but an LLM quoting that text back naturally flattens it into
    flowing prose (joining wrapped lines with a space). A naive exact
    substring check fails here and silently downgrades a real match to
    "not observed" -- this must match despite the differing whitespace.
    """
    pages = [
        DocumentPage(
            1, "Students are introduced to clear instructions\nwhen working with teams."
        )
    ]
    assert find_evidence_page(pages, "clear instructions when working with teams") == 1


def test_matches_quote_with_collapsed_whitespace_variants() -> None:
    pages = [DocumentPage(1, "Line one.\n\nLine   two   has  extra   spaces.")]
    assert find_evidence_page(pages, "Line two has extra spaces.") == 1


def test_select_full_scope_when_everything_fits() -> None:
    pages = [DocumentPage(1, "a" * 100), DocumentPage(2, "b" * 100)]
    selected, coverage = select_pages_within_budget(pages, 500)

    assert [p.page_number for p in selected] == [1, 2]
    assert coverage == {
        "scope": "full",
        "total_pages": 2,
        "evaluated_pages": 2,
        "total_chars": 200,
        "evaluated_chars": 200,
        "strategy": "all_pages",
    }


def test_select_bounded_scope_keeps_only_complete_pages() -> None:
    pages = [
        DocumentPage(1, "a" * 3000),
        DocumentPage(2, "b" * 3000),
        DocumentPage(3, "c" * 3000),
    ]
    selected, coverage = select_pages_within_budget(pages, 6000)

    assert [p.page_number for p in selected] == [1, 2]
    assert coverage["scope"] == "bounded"
    assert coverage["total_pages"] == 3
    assert coverage["evaluated_pages"] == 2
    assert coverage["total_chars"] == 9000
    assert coverage["evaluated_chars"] == 6000
    assert coverage["strategy"] == "prefix_pages"


def test_select_bounded_scope_never_splits_a_page() -> None:
    # A page is all-or-nothing: the oversized page 2 is dropped whole even
    # though part of it would fit in the remaining budget.
    pages = [DocumentPage(1, "a" * 100), DocumentPage(2, "b" * 1000)]
    selected, coverage = select_pages_within_budget(pages, 500)

    assert [p.page_number for p in selected] == [1]
    assert coverage["scope"] == "bounded"
    assert coverage["evaluated_chars"] == 100


def test_select_returns_empty_when_first_page_too_large() -> None:
    pages = [DocumentPage(1, "x" * 100)]
    selected, coverage = select_pages_within_budget(pages, 50)

    assert selected == []
    assert coverage["scope"] == "bounded"
    assert coverage["evaluated_pages"] == 0
