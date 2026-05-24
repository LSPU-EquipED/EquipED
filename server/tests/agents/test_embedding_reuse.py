"""Tests for embedding reuse in supervisor precomputation and retrieval."""

from __future__ import annotations

from server.modules.agents.supervisor import Supervisor
from server.modules.embeddings.retrieval import retrieve_context_with_embedding


def test_supervisor_compute_embedding_returns_none_for_empty() -> None:
    """_compute_query_embedding should return None for empty/whitespace text."""
    supervisor = Supervisor()
    assert supervisor._compute_query_embedding("") is None
    assert supervisor._compute_query_embedding("   ") is None


def test_supervisor_compute_embedding_returns_list_for_text(monkeypatch) -> None:
    """_compute_query_embedding should return a list of floats for valid text."""
    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            class Result:
                def tolist(self):
                    return [[0.1, 0.2, 0.3]]
            return Result()

    monkeypatch.setattr(
        "server.core.embedding.get_embedding_model",
        lambda: FakeModel(),
    )

    supervisor = Supervisor()
    result = supervisor._compute_query_embedding("hello world")
    assert result == [0.1, 0.2, 0.3]


def test_supervisor_compute_embedding_returns_none_on_error(monkeypatch) -> None:
    """_compute_query_embedding should return None when model fails."""
    def broken_model():
        raise RuntimeError("model broken")

    monkeypatch.setattr(
        "server.core.embedding.get_embedding_model",
        broken_model,
    )

    supervisor = Supervisor()
    result = supervisor._compute_query_embedding("hello")
    assert result is None


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


def test_precompute_uses_embedding_when_available(monkeypatch) -> None:
    """_build_precomputed_context should use embedding path when provided."""
    call_counts = {"with_embedding": 0, "with_text": 0}

    def fake_retrieve_with_embedding(embedding, collection, n_results=5, document_id_filter=None):
        call_counts["with_embedding"] += 1
        from server.modules.embeddings.retrieval import RetrievedChunk
        return [RetrievedChunk(text=f"emb:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    def fake_retrieve_context(query_text, collection, n_results=5, document_id_filter=None):
        call_counts["with_text"] += 1
        from server.modules.embeddings.retrieval import RetrievedChunk
        return [RetrievedChunk(text=f"text:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        fake_retrieve_with_embedding,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve_context,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    supervisor = Supervisor()
    embedding = [0.1, 0.2, 0.3]
    result = supervisor._build_precomputed_context(
        "query text", query_embedding=embedding,
    )

    # Should have used embedding path, not text path
    assert call_counts["with_embedding"] > 0
    assert call_counts["with_text"] == 0


def test_precompute_falls_back_to_text_when_no_embedding(monkeypatch) -> None:
    """_build_precomputed_context should fall back to text path when embedding is None."""
    call_counts = {"with_embedding": 0, "with_text": 0}

    def fake_retrieve_with_embedding(embedding, collection, n_results=5, document_id_filter=None):
        call_counts["with_embedding"] += 1
        from server.modules.embeddings.retrieval import RetrievedChunk
        return [RetrievedChunk(text=f"emb:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    def fake_retrieve_context(query_text, collection, n_results=5, document_id_filter=None):
        call_counts["with_text"] += 1
        from server.modules.embeddings.retrieval import RetrievedChunk
        return [RetrievedChunk(text=f"text:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        fake_retrieve_with_embedding,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context",
        fake_retrieve_context,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    supervisor = Supervisor()
    result = supervisor._build_precomputed_context(
        "query text", query_embedding=None,
    )

    # Should have used text path, not embedding path
    assert call_counts["with_text"] > 0
    assert call_counts["with_embedding"] == 0
    # All text calls should use the same query text
