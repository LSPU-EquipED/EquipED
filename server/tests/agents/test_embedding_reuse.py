"""Tests for supervisor embedding reuse in precomputation."""

from __future__ import annotations

from server.modules.agents.supervisor import Supervisor


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
        "query text",
        query_embedding=embedding,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
            "curriculum": "00000000-0000-0000-0000-000000000002",
        },
    )

    # Should have used embedding path, not text path
    assert call_counts["with_embedding"] == 2  # one per reference source type
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
        "query text",
        query_embedding=None,
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    # Should have used text path, not embedding path
    assert call_counts["with_text"] == 1
    assert call_counts["with_embedding"] == 0


def test_precompute_computes_embedding_once_for_multiple_sources(monkeypatch) -> None:
    """Embedding should be computed exactly once, not per source type."""
    encode_calls = []

    class FakeModel:
        def encode(self, texts, show_progress_bar=False):
            encode_calls.append(texts)

            class Result:
                def tolist(self):
                    return [[0.1, 0.2, 0.3]]

            return Result()

    monkeypatch.setattr(
        "server.core.embedding.get_embedding_model",
        lambda: FakeModel(),
    )

    retrieve_calls = []

    def fake_retrieve_with_embedding(embedding, collection, n_results=5, document_id_filter=None):
        retrieve_calls.append(("embedding", collection))
        from server.modules.embeddings.retrieval import RetrievedChunk

        return [RetrievedChunk(text=f"emb:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        fake_retrieve_with_embedding,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    supervisor = Supervisor()
    # Two reference document types should trigger two retrievals but only ONE embedding.
    result = supervisor._build_precomputed_context(
        "test query",
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
            "curriculum": "00000000-0000-0000-0000-000000000002",
        },
    )

    assert len(encode_calls) == 1, "embedding should be computed exactly once"
    assert encode_calls[0] == ["test query"]
    assert len(retrieve_calls) == 2, "should retrieve for both syllabus and curriculum"
    assert result["syllabus"] == ["emb:syllabus"]
    assert result["curriculum"] == ["emb:curriculum"]


def test_precompute_reuses_explicit_embedding_parameter(monkeypatch) -> None:
    """When query_embedding is passed explicitly, _compute_query_embedding must not be called."""
    encode_calls = []

    def broken_model():
        encode_calls.append(1)
        raise RuntimeError("should not be called")

    monkeypatch.setattr(
        "server.core.embedding.get_embedding_model",
        broken_model,
    )

    def fake_retrieve_with_embedding(embedding, collection, n_results=5, document_id_filter=None):
        from server.modules.embeddings.retrieval import RetrievedChunk
        return [RetrievedChunk(text=f"emb:{collection}", distance=0.1, document_id=None, source_type=None, page_number=None, is_ocr=None, token_count=None)]

    monkeypatch.setattr(
        "server.modules.embeddings.retrieval.retrieve_context_with_embedding",
        fake_retrieve_with_embedding,
    )
    monkeypatch.setattr(
        "server.modules.embeddings.collections.resolve_collection_name",
        lambda source_type: source_type,
    )

    supervisor = Supervisor()
    result = supervisor._build_precomputed_context(
        "query text",
        query_embedding=[0.5, 0.6, 0.7],
        reference_document_ids={
            "syllabus": "00000000-0000-0000-0000-000000000001",
        },
    )

    assert encode_calls == [], "_compute_query_embedding should not be called when embedding is provided"
    assert result["syllabus"] == ["emb:syllabus"]
