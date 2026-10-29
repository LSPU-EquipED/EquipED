from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest
from server.modules.embeddings import service as embedding_service
from server.modules.embeddings import slm_retrieval as service
from server.modules.embeddings.collections import resolve_slm_collection_name


class FakeCollection:
    def __init__(self):
        self.rows = {}
        self.fail_after = None
        self.query_calls = 0
        self.dimension = None

    def get(self, where=None, limit=None, offset=0, include=None, ids=None):
        assert limit is None or limit <= 300  # Configured Chroma Cloud read quota.
        rows = [(key, value) for key, value in self.rows.items()]
        if ids is not None:
            rows = [(key, value) for key, value in rows if key in ids]
        if where and isinstance(where, dict) and "document_id" in where:
            doc_id = where["document_id"]["$eq"]
            rows = [
                (key, value) for key, value in rows if value[1]["document_id"] == doc_id
            ]
        rows = rows[offset : offset + limit] if limit else rows[offset:]
        return {
            "ids": [x[0] for x in rows],
            "documents": [x[1][0] for x in rows],
            "metadatas": [x[1][1] for x in rows],
        }

    def upsert(self, ids, documents, metadatas, embeddings):
        assert len(ids) <= 2
        dimensions = {len(vector) for vector in embeddings}
        assert len(dimensions) == 1
        dimension = dimensions.pop()
        if self.dimension is None:
            self.dimension = dimension
        assert self.dimension == dimension
        if self.fail_after is not None and len(self.rows) >= self.fail_after:
            raise RuntimeError("write failed")
        self.rows.update(
            {i: (d, m) for i, d, m in zip(ids, documents, metadatas, strict=True)}
        )

    def delete(self, ids=None, where=None):
        if ids is not None:
            for item in ids:
                self.rows.pop(item, None)
        elif where:
            if "$and" in where:
                doc_id = where["$and"][0]["document_id"]["$eq"]
                identity = where["$and"][1]["index_identity"]["$ne"]
                self.rows = {
                    key: value
                    for key, value in self.rows.items()
                    if value[1]["document_id"] != doc_id
                    or value[1]["index_identity"] == identity
                }
            else:
                doc_id = where["document_id"]["$eq"]
                self.rows = {
                    key: value
                    for key, value in self.rows.items()
                    if value[1]["document_id"] != doc_id
                }

    def query(self, query_embeddings, n_results, where, include):
        self.query_calls += 1
        assert len(query_embeddings[0]) == self.dimension
        doc_id = where["$and"][0]["document_id"]["$eq"]
        source_hash = where["$and"][2]["source_hash"]["$eq"]
        identity = where["$and"][4]["index_identity"]["$eq"]
        rows = [
            (i, d, m)
            for i, (d, m) in self.rows.items()
            if m["document_id"] == doc_id
            and m["source_hash"] == source_hash
            and m["index_identity"] == identity
        ]
        rows = rows[:n_results]
        return {
            "ids": [[x[0] for x in rows]],
            "documents": [[x[1] for x in rows]],
            "metadatas": [[x[2] for x in rows]],
            "distances": [[0.1] * len(rows)],
        }


class FakeClient:
    def __init__(self, max_batch=2):
        default_name = resolve_slm_collection_name("test-model", 3)
        self.collections = {default_name: FakeCollection()}
        self.collection = self.collections[default_name]
        self.max_batch = max_batch

    def get_or_create_collection(self, name, embedding_function=None):
        assert name.startswith("col_slm_all_")
        if name not in self.collections:
            self.collections[name] = FakeCollection()
        self.collection = self.collections[name]
        return self.collection

    def get_collection(self, name):
        return self.collections[name]

    def list_collections(self):
        return list(self.collections)

    def get_max_batch_size(self):
        return self.max_batch


class FakeModel:
    def __init__(self, dimension=3):
        self.dimension = dimension
        self.max_batch_seen = 0
        self.encoded_texts = []

    def encode(self, texts, **kwargs):
        self.max_batch_seen = max(self.max_batch_seen, len(texts))
        self.encoded_texts.extend(texts)
        return np.ones((len(texts), self.dimension))


class InconsistentModel(FakeModel):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def encode(self, texts, **kwargs):
        self.calls += 1
        dimension = 3 if self.calls == 1 else 4
        return np.ones((len(texts), dimension))


class NonFiniteModel(FakeModel):
    def encode(self, texts, **kwargs):
        values = np.ones((len(texts), self.dimension))
        values[0, 0] = np.nan
        return values


@pytest.fixture
def setup(monkeypatch):
    client = FakeClient()
    model = FakeModel()
    monkeypatch.setattr(service, "get_chroma_client", lambda: client)
    monkeypatch.setattr(service, "get_embedding_model", lambda: model)
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(embedding_model_name="test-model"),
    )
    return client, model


def test_build_reuses_verified_index_and_returns_bounded_passages(setup):
    client, model = setup
    text = "A" * (service.SLM_SOURCE_SPAN_CHARS + 20)
    result = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text=text, queries={"C1": "query"}
    )
    original_rows = dict(client.collection.rows)
    model.encoded_texts.clear()
    second = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text=text, queries={"C1": "query"}
    )
    assert client.collection.rows == original_rows
    assert model.encoded_texts == ["query"]
    assert model.max_batch_seen <= 2
    assert result == second
    assert result["contract"] == "slm_retrieval.v2"
    assert 0 < len(result["rankings"]["C1"]) <= 12
    assert set(result["rankings"]["C1"]) == set(result["passages"])
    assert all(key in original_rows for key in result["rankings"]["C1"])


def test_index_verification_paginates_within_cloud_read_quota(setup):
    client, _ = setup
    text = "A" * (800 * 135)
    result = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text=text, queries={"C": "query"}
    )
    assert len(client.collection.rows) == 135
    assert len(result["rankings"]["C"]) == 12


def test_retrieval_returns_bounded_index_ids_and_exact_offsets(setup):
    _client, _model = setup
    text = "A" * (service.SLM_SOURCE_SPAN_CHARS + 20)
    result = service.build_slm_retrieval(
        document_id="doc-a",
        canonical_source_text=text,
        queries={"C1": "query"},
    )
    assert result["rankings"]["C1"]
    assert len(result["rankings"]["C1"]) <= 12
    assert set(result["rankings"]["C1"]) == set(result["passages"])
    assert all(
        0 < passage["end"] - passage["start"] <= 800
        for passage in result["passages"].values()
    )
    assert any(passage["start"] == 800 for passage in result["passages"].values())


def test_tokenizer_limit_change_replaces_the_old_chunk_layout(setup, monkeypatch):
    client, model = setup

    class CharacterTokenizer:
        def encode(self, text, **kwargs):
            return list(range(len(text) + 2))

    model.tokenizer = CharacterTokenizer()
    model.max_seq_length = 64
    service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="A" * 200, queries={"C": "query"}
    )
    old_ids = set(client.collection.rows)
    model.max_seq_length = 32
    service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="A" * 200, queries={"C": "query"}
    )
    assert not old_ids.intersection(client.collection.rows)
    assert len(client.collection.rows) == 8
    assert all(len(text) + 2 <= 32 for text, _ in client.collection.rows.values())


def test_source_and_model_changes_create_new_identity(setup, monkeypatch):
    client, _ = setup
    first = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="first", queries={"C": "query"}
    )
    second = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="second", queries={"C": "query"}
    )
    monkeypatch.setattr(
        service,
        "get_settings",
        lambda: SimpleNamespace(embedding_model_name="other-model"),
    )
    third = service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="second", queries={"C": "query"}
    )
    assert first["source_hash"] != second["source_hash"]
    assert third["source_hash"] == second["source_hash"]
    assert first["embedding_model"] == second["embedding_model"]
    assert third["embedding_model"] == "other-model"
    assert all(
        metadata["embedding_model"] == "other-model"
        for _, metadata in client.collection.rows.values()
    )


def test_documents_are_isolated(setup):
    client, _ = setup
    service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="alpha", queries={"A": "alpha"}
    )
    before = set(client.collection.rows)
    service.build_slm_retrieval(
        document_id="doc-b", canonical_source_text="bravo", queries={"B": "bravo"}
    )
    assert before <= set(client.collection.rows)
    assert {m["document_id"] for _, m in client.collection.rows.values()} == {
        "doc-a",
        "doc-b",
    }


def test_failed_write_cleans_partial_index_and_propagates(setup):
    client, _ = setup
    client.collection.fail_after = 2
    with pytest.raises(RuntimeError, match="write failed"):
        service.build_slm_retrieval(
            document_id="doc-a",
            canonical_source_text="A" * 2800,
            queries={"C": "query"},
        )
    assert client.collection.rows == {}


def test_query_failure_or_empty_result_does_not_return_empty_rankings(
    setup, monkeypatch
):
    client, _ = setup
    monkeypatch.setattr(
        client.collection,
        "query",
        lambda **kwargs: {"ids": [[]], "documents": [[]], "metadatas": [[]]},
    )
    with pytest.raises(RuntimeError, match="returned no indexed chunks"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_query_outage_propagates(setup, monkeypatch):
    client, _ = setup

    def outage(**kwargs):
        raise RuntimeError("chroma unavailable")

    monkeypatch.setattr(client.collection, "query", outage)
    with pytest.raises(RuntimeError, match="chroma unavailable"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_tampered_text_is_rejected(setup, monkeypatch):
    client, _ = setup
    original = client.collection.query

    def tampered(**kwargs):
        result = original(**kwargs)
        result["documents"][0][0] = "forged"
        return result

    monkeypatch.setattr(client.collection, "query", tampered)
    with pytest.raises(RuntimeError, match="altered index row"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_unknown_parent_is_rejected(setup, monkeypatch):
    client, _ = setup
    original = client.collection.query

    def unknown_parent(**kwargs):
        result = original(**kwargs)
        result["metadatas"][0][0]["parent_source_id"] = "slm-9999"
        return result

    monkeypatch.setattr(client.collection, "query", unknown_parent)
    with pytest.raises(RuntimeError, match="unknown parent source ID"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_query_rejects_mismatched_row_arrays(setup, monkeypatch):
    client, _ = setup
    original = client.collection.query

    def incomplete(**kwargs):
        result = original(**kwargs)
        result["metadatas"][0].clear()
        return result

    monkeypatch.setattr(client.collection, "query", incomplete)
    with pytest.raises(RuntimeError, match="incomplete rows"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_query_rejects_out_of_scope_rows(setup, monkeypatch):
    client, _ = setup
    original = client.collection.query

    def wrong_document(**kwargs):
        result = original(**kwargs)
        result["metadatas"][0][0]["document_id"] = "doc-b"
        return result

    monkeypatch.setattr(client.collection, "query", wrong_document)
    with pytest.raises(RuntimeError, match="out-of-scope result"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="text", queries={"C": "query"}
        )


def test_slm_collection_routing():
    from server.modules.embeddings.collections import (
        COL_SLM_ALL,
        resolve_collection_name,
    )

    assert resolve_collection_name("slm") == COL_SLM_ALL == "col_slm_all"


def test_dimension_change_uses_a_separate_collection(setup, monkeypatch):
    client, _ = setup
    service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="source", queries={"C": "query"}
    )
    original_names = set(client.collections)
    monkeypatch.setattr(service, "get_embedding_model", lambda: FakeModel(5))
    service.build_slm_retrieval(
        document_id="doc-a", canonical_source_text="source", queries={"C": "query"}
    )
    assert len(client.collections) == 2
    assert len(original_names & set(client.collections)) == 1
    assert all(
        collection.dimension == 3
        for name, collection in client.collections.items()
        if name in original_names
    )
    assert {
        collection.dimension
        for name, collection in client.collections.items()
        if name not in original_names
    } == {5}


def test_strict_slm_delete_clears_every_reserved_generation(setup, monkeypatch):
    client, _ = setup
    doc_id = "doc-shared"
    service.build_slm_retrieval(
        document_id=doc_id, canonical_source_text="source", queries={"C": "query"}
    )
    monkeypatch.setattr(service, "get_embedding_model", lambda: FakeModel(5))
    service.build_slm_retrieval(
        document_id=doc_id, canonical_source_text="source", queries={"C": "query"}
    )
    monkeypatch.setattr(embedding_service, "get_chroma_client", lambda: client)

    assert embedding_service.check_chroma_availability(doc_id, "slm") is True
    assert embedding_service.delete_chroma_vectors_strict(doc_id, "slm") is True
    assert all(not collection.rows for collection in client.collections.values())
    assert embedding_service.check_chroma_availability(doc_id, "slm") is False


def test_generic_chunk_writer_rejects_slm(setup):
    from types import SimpleNamespace

    chunk = SimpleNamespace(
        chunk_id="chunk", document_id="doc-a", source_type="slm", text="source"
    )
    with pytest.raises(ValueError, match="build_slm_retrieval"):
        embedding_service.embed_and_store_chunks([chunk])


def test_inconsistent_embedding_dimensions_are_rejected(setup, monkeypatch):
    monkeypatch.setattr(service, "get_embedding_model", InconsistentModel)
    with pytest.raises(RuntimeError, match="inconsistent dimensions"):
        service.build_slm_retrieval(
            document_id="doc-a",
            canonical_source_text="A" * 2400,
            queries={"C": "query"},
        )


def test_non_finite_embedding_values_are_rejected(setup, monkeypatch):
    monkeypatch.setattr(service, "get_embedding_model", NonFiniteModel)
    with pytest.raises(RuntimeError, match="non-finite"):
        service.build_slm_retrieval(
            document_id="doc-a", canonical_source_text="source", queries={"C": "query"}
        )
