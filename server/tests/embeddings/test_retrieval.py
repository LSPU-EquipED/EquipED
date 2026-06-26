"""Tests for embeddings.retrieval module — Chroma delegation and failure observability."""

from __future__ import annotations

import logging

from server.modules.embeddings.retrieval import (
    retrieve_context,
    retrieve_context_with_embedding,
)


def test_retrieve_context_with_embedding_delegates(monkeypatch) -> None:
    """retrieve_context_with_embedding should call Chroma with the embedding."""
    captured_embedding = None
    captured_collection = None

    class FakeCollection:
        def query(self, query_embeddings, n_results, where, include):
            nonlocal captured_embedding, captured_collection
            captured_embedding = query_embeddings
            return {
                "documents": [["chunk text"]],
                "metadatas": [[{"source_type": "test"}]],
                "distances": [[0.1]],
            }

    class FakeChroma:
        def get_collection(self, name):
            nonlocal captured_collection
            captured_collection = name
            return FakeCollection()

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.get_chroma_client",
        lambda: FakeChroma(),
    )

    embedding = [0.1, 0.2, 0.3]
    results = retrieve_context_with_embedding(
        embedding, "test_collection", n_results=3,
    )

    assert len(results) == 1
    assert results[0].text == "chunk text"
    assert captured_embedding == [embedding]
    assert captured_collection == "test_collection"


def test_retrieve_context_with_embedding_empty_returns_empty() -> None:
    """retrieve_context_with_embedding should return [] for empty embedding."""
    assert retrieve_context_with_embedding([], "test") == []
    assert retrieve_context_with_embedding(None, "test") == []  # type: ignore[arg-type]


def test_retrieve_context_logs_warning_and_returns_empty_on_failure(
    monkeypatch, caplog
) -> None:
    """A retrieval failure should still return [] (Phase 1 contract) but
    emit a warning that includes the collection name for triage."""
    caplog.set_level(
        logging.WARNING, logger="server.modules.embeddings.retrieval"
    )

    def broken_model():
        raise RuntimeError("embedding model exploded")

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.get_embedding_model",
        broken_model,
    )

    results = retrieve_context("hello", "test_collection", n_results=3)

    assert results == []
    assert any(
        "retrieve_context failed" in r.message
        and "test_collection" in r.message
        for r in caplog.records
    ), f"expected retrieval failure warning, got: {[r.message for r in caplog.records]}"


def test_retrieve_context_with_embedding_logs_warning_and_returns_empty(
    monkeypatch, caplog
) -> None:
    """A pre-embedded retrieval failure should still return [] (Phase 1
    contract) but emit a warning that includes the collection name."""
    caplog.set_level(
        logging.WARNING, logger="server.modules.embeddings.retrieval"
    )

    class FakeChroma:
        def get_collection(self, name):
            raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.get_chroma_client",
        lambda: FakeChroma(),
    )

    results = retrieve_context_with_embedding(
        [0.1, 0.2, 0.3], "test_collection", n_results=3,
    )

    assert results == []
    assert any(
        "retrieve_context_with_embedding failed" in r.message
        and "test_collection" in r.message
        for r in caplog.records
    ), f"expected retrieval failure warning, got: {[r.message for r in caplog.records]}"
