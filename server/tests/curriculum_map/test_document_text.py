"""Unit tests for the pure evidence-page locator.

``extract_document_pages`` needs a real PDF + DB row to exercise fully, so
it is covered indirectly by the service-layer tests (Task 6) via monkeypatch.
This file covers ``find_evidence_page``, which is pure and fully
unit-testable in isolation.
"""

from __future__ import annotations

from server.modules.curriculum_map.document_text import find_evidence_page


def test_finds_page_containing_exact_quote() -> None:
    pages = ["Intro text.", "Students design a linked list from scratch.", "Summary."]
    assert find_evidence_page(pages, "design a linked list") == 2


def test_returns_none_when_quote_not_found() -> None:
    pages = ["Intro text.", "Body text."]
    assert find_evidence_page(pages, "nonexistent quote") is None


def test_returns_none_for_empty_quote() -> None:
    pages = ["Intro text."]
    assert find_evidence_page(pages, "") is None


def test_returns_first_matching_page_when_quote_repeats() -> None:
    pages = ["First mention of teamwork.", "Second mention of teamwork."]
    assert find_evidence_page(pages, "teamwork") == 1
