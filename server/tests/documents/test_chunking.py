"""Unit tests for deterministic document chunking."""

from __future__ import annotations

import uuid

import pytest
from server.modules.documents.ingestion.chunking import (
    _DEFAULT_CHUNK_OVERLAP,
    _MAX_CHUNK_TOKENS,
    _MIN_MERGE_THRESHOLD,
    _build_overlap_seed,
    _chunk_page_text,
    _ChunkDraft,
    _hard_split,
    _looks_weak_structure,
    _merge_tiny_chunks,
    _split_sentence_units,
)
from server.modules.documents.ingestion.pipeline import ExtractedPage, ingest_document


def test_chunker_prefers_blank_line_structures() -> None:
    heading = "Heading"
    paragraph_a = " ".join([f"alpha{i}" for i in range(240)])
    paragraph_b = " ".join([f"beta{i}" for i in range(240)])
    text = f"{heading}\n\n{paragraph_a}\n\n{paragraph_b}"

    chunks = _chunk_page_text(text)

    assert len(chunks) == 2
    assert chunks[0].startswith(heading)
    assert paragraph_b.split()[0] in chunks[1]


def test_chunker_falls_back_on_weak_structure() -> None:
    text = " ".join([f"sentence{i}." for i in range(520)])

    assert _looks_weak_structure(text) is True
    sentence_units = _split_sentence_units(text)
    assert len(sentence_units) >= 2

    chunks = _chunk_page_text(text)

    assert len(chunks) >= 1
    assert all("sentence" in chunk for chunk in chunks)


def test_overlap_prefers_structure_then_sentence_then_words() -> None:
    short_unit = "one two three four"
    assert _build_overlap_seed([short_unit]) == short_unit

    sentence_unit = " ".join([f"word{i}" for i in range(20)]) + "."
    assert _build_overlap_seed([sentence_unit]) == sentence_unit

    long_unit = " ".join([f"word{i}" for i in range(90)])
    overlap = _build_overlap_seed([long_unit])
    assert overlap.split() == long_unit.split()[-_DEFAULT_CHUNK_OVERLAP:]


def test_ingest_document_keeps_chunks_page_bounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [
        ExtractedPage(
            page_number=1,
            text="page one\n\n" + " ".join(["a"] * 260),
            is_ocr=False,
        ),
        ExtractedPage(
            page_number=2,
            text="page two\n\n" + " ".join(["b"] * 260),
            is_ocr=False,
        ),
    ]
    monkeypatch.setattr(
        "server.modules.documents.ingestion.pipeline._extract_pages",
        lambda _: pages,
    )

    chunks = ingest_document("/tmp/example.pdf", "slm", str(uuid.uuid4()))

    assert {chunk.page_number for chunk in chunks} == {1, 2}
    assert chunks[0].page_number == 1
    assert chunks[-1].page_number == 2


def test_oversized_text_is_hard_split_deterministically() -> None:
    oversized = " ".join([f"token{i}" for i in range(_MAX_CHUNK_TOKENS + 180)])

    chunks = _hard_split(oversized, _MAX_CHUNK_TOKENS, _DEFAULT_CHUNK_OVERLAP)

    assert len(chunks) == 2
    assert len(chunks[0].split()) <= _MAX_CHUNK_TOKENS
    assert len(chunks[1].split()) <= _MAX_CHUNK_TOKENS
    assert (
        chunks[1].split()[:_DEFAULT_CHUNK_OVERLAP]
        == chunks[0].split()[-_DEFAULT_CHUNK_OVERLAP:]
    )


def test_tiny_fragments_merge_when_safe() -> None:
    large = _ChunkDraft(" ".join([f"big{i}" for i in range(280)]), ["large"], 280)
    tiny = _ChunkDraft(" ".join([f"small{i}" for i in range(40)]), ["tiny"], 40)

    merged = _merge_tiny_chunks([large, tiny])

    assert len(merged) == 1
    assert merged[0].token_count == 320
    assert merged[0].token_count >= _MIN_MERGE_THRESHOLD


def test_tiny_fragments_do_not_merge_when_too_large() -> None:
    large = _ChunkDraft(" ".join([f"big{i}" for i in range(1980)]), ["large"], 1980)
    tiny = _ChunkDraft(" ".join([f"small{i}" for i in range(80)]), ["tiny"], 80)

    merged = _merge_tiny_chunks([large, tiny])

    assert len(merged) == 2
