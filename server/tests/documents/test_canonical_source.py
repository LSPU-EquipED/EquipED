from pathlib import Path

import pytest
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.ingestion.pipeline import (
    ExtractedPage,
    prepare_canonical_source,
)


def test_prepare_canonical_source_joins_pages_without_persistence(monkeypatch) -> None:
    calls: list[str] = []

    def extract(path: str) -> list[ExtractedPage]:
        calls.append(path)
        return [
            ExtractedPage(1, "first page", False),
            ExtractedPage(2, "second page", True),
        ]

    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline._extract_pages", extract
    )

    result = prepare_canonical_source("/owned/uploads/document.pdf")

    assert result == "first page\n\nsecond page"
    assert calls == ["/owned/uploads/document.pdf"]
    assert isinstance(result, str)


def test_prepare_canonical_source_fails_closed_for_empty_pdf(monkeypatch) -> None:
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline._extract_pages", lambda _: []
    )

    with pytest.raises(ExtractionFailedError, match="No extractable text"):
        prepare_canonical_source("empty.pdf")


def test_prepare_canonical_source_propagates_missing_pdf(monkeypatch) -> None:
    def extract(path: str) -> list[ExtractedPage]:
        raise ExtractionFailedError(f"File not found: {Path(path)}")

    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline._extract_pages", extract
    )

    with pytest.raises(ExtractionFailedError, match="File not found"):
        prepare_canonical_source("missing.pdf")
