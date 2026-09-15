"""Tests for embedding metadata filtering (Task 3).

Ensures:
- Metadata keys with None values are omitted from Chroma upserts.
- Real Chroma EphemeralClient is used for both initial and rebuild embedding paths.
- Non-policy and policy chunks both handle metadata correctly.
"""

from __future__ import annotations

import uuid

import chromadb
import numpy as np
import pytest
from server.modules.documents.models import DocumentChunk
from server.modules.embeddings.collections import COL_POLICY_ALL, COL_REFERENCE_ALL
from server.modules.embeddings.service import (
    EmbeddingChunk,
    _omit_none,
    _to_embedding_chunk,
    embed_and_store_chunks,
)

# ============================================================================
# Unit: _omit_none
# ============================================================================


class TestOmitNone:
    def test_omits_none_values(self):
        result = _omit_none({"a": 1, "b": None, "c": "hello", "d": None})
        assert result == {"a": 1, "c": "hello"}

    def test_preserves_false_and_zero(self):
        result = _omit_none({"a": 0, "b": False, "c": "", "d": None})
        assert result == {"a": 0, "b": False, "c": ""}

    def test_empty_dict_when_all_none(self):
        result = _omit_none({"a": None, "b": None})
        assert result == {}

    def test_unchanged_when_no_none(self):
        result = _omit_none({"a": 1, "b": "x"})
        assert result == {"a": 1, "b": "x"}


# ============================================================================
# Unit: _to_embedding_chunk uses policy_area (not _policy_area)
# ============================================================================


class TestToEmbeddingChunk:
    def test_uses_policy_area_from_chunk(self):
        """_to_embedding_chunk reads policy_area, not _policy_area."""
        chunk = DocumentChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            source_type="policy",
            agent_domain="itso",
            page_number=1,
            text="test",
            token_count=4,
            is_ocr=False,
            policy_area="data_privacy",
            section_ref="Section 1",
            chunk_index=0,
        )
        ec = _to_embedding_chunk(chunk)
        assert ec.policy_area == "data_privacy"

    def test_non_policy_chunk_has_none_policy_area(self):
        chunk = DocumentChunk(
            chunk_id=uuid.uuid4(),
            document_id=uuid.uuid4(),
            source_type="syllabus",
            agent_domain="all",
            page_number=1,
            text="reference text",
            token_count=5,
            is_ocr=False,
        )
        ec = _to_embedding_chunk(chunk)
        assert ec.policy_area is None
        assert ec.section_ref is None
        assert ec.chunk_index is None

    def test_embedding_chunk_from_dictlike(self):
        """Works with simple objects via getattr."""
        class FakeChunk:
            chunk_id = uuid.uuid4()
            document_id = uuid.uuid4()
            source_type = "policy"
            page_number = 2
            text = "policy text"
            token_count = 10
            is_ocr = True
            policy_area = "intellectual_property"
            section_ref = "Section 2"
            chunk_index = 1

        ec = _to_embedding_chunk(FakeChunk())
        assert ec.policy_area == "intellectual_property"
        assert ec.section_ref == "Section 2"
        assert ec.chunk_index == 1

    def test_embedding_chunk_from_class_without_policy_area(self):
        """Chunks without policy_area attribute get None."""
        class BareChunk:
            chunk_id = uuid.uuid4()
            document_id = uuid.uuid4()
            source_type = "syllabus"
            page_number = 1
            text = "bare"
            token_count = 1
            is_ocr = False

        ec = _to_embedding_chunk(BareChunk())
        assert ec.policy_area is None


# ============================================================================
# Integration: real Chroma EphemeralClient for both embedding paths
# ============================================================================


class TestEmbedAndStoreMetadata:
    """Uses real EphemeralClient to verify metadata is correctly upserted.

    Tests both initial (persist) and rebuild embedding paths: chunks sent
    to ``embed_and_store_chunks`` get stored in Chroma with metadata that
    omits None-valued keys.
    """

    @pytest.fixture()
    def ephemeral_client(self):
        return chromadb.EphemeralClient()

    def _check_metadata_key(
        self, col, chunk_id: str, key: str, expected: object
    ):
        """Helper: check the stored value for a metadata key."""
        result = col.get(ids=[chunk_id])
        if result and result.get("metadatas"):
            meta = result["metadatas"][0]
            if expected is None:
                return key not in meta
            return meta.get(key) == expected
        return False

    def _patch_embedding(self, monkeypatch):
        """Patch embedding model to a simple list-based stub so tests
        can run without sentence-transformers installed."""
        class FakeModel:
            def encode(self, texts, **kwargs):
                return np.array([[0.0] * 384 for _ in texts])

        monkeypatch.setattr(
            "server.modules.embeddings.service.get_embedding_model",
            lambda: FakeModel(),
        )

    def test_policy_chunk_metadata_omits_none(
        self, ephemeral_client, monkeypatch,
    ):
        """Policy chunk metadata in Chroma omits keys with None values."""
        self._patch_embedding(monkeypatch)
        monkeypatch.setattr(
            "server.modules.embeddings.service.get_chroma_client",
            lambda: ephemeral_client,
        )

        chunk = EmbeddingChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            source_type="policy",
            page_number=1,
            text="policy test",
            token_count=3,
            is_ocr=False,
            policy_area="data_privacy",
            section_ref="Section 1",
            chunk_index=0,
        )
        embed_and_store_chunks([chunk])

        col = ephemeral_client.get_collection(COL_POLICY_ALL)
        result = col.get(ids=[chunk.chunk_id])
        assert result and result.get("metadatas")
        meta = result["metadatas"][0]
        assert meta["policy_area"] == "data_privacy"
        assert meta["chunk_id"] == chunk.chunk_id

    def test_non_policy_chunk_omits_none_metadata(
        self, ephemeral_client, monkeypatch,
    ):
        """Non-policy chunk (syllabus) metadata omits policy_area=None."""
        self._patch_embedding(monkeypatch)
        monkeypatch.setattr(
            "server.modules.embeddings.service.get_chroma_client",
            lambda: ephemeral_client,
        )

        chunk = EmbeddingChunk(
            chunk_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            source_type="syllabus",
            page_number=1,
            text="reference text",
            token_count=5,
            is_ocr=False,
            policy_area=None,
            section_ref=None,
            chunk_index=None,
        )
        embed_and_store_chunks([chunk])

        col = ephemeral_client.get_collection(COL_REFERENCE_ALL)
        result = col.get(ids=[chunk.chunk_id])
        assert result and result.get("metadatas")
        meta = result["metadatas"][0]
        # None keys must not appear in metadata
        assert "policy_area" not in meta
        assert "section_ref" not in meta
        assert "chunk_index" not in meta
        # Non-None keys must appear
        assert meta["chunk_id"] == chunk.chunk_id
        assert meta["source_type"] == "syllabus"
        assert meta["page_number"] == 1
        assert meta["is_ocr"] is False
        assert meta["token_count"] == 5

    def test_rebuild_path_metadata_consistency(
        self, ephemeral_client, monkeypatch,
    ):
        """Rebuild path (embed_and_store_chunks) produces same metadata shape."""
        self._patch_embedding(monkeypatch)
        monkeypatch.setattr(
            "server.modules.embeddings.service.get_chroma_client",
            lambda: ephemeral_client,
        )

        ident = str(uuid.uuid4())
        doc_id = str(uuid.uuid4())
        # First embed (initial path)
        chunk1 = EmbeddingChunk(
            chunk_id=ident,
            document_id=doc_id,
            source_type="policy",
            page_number=2,
            text="rebuild test",
            token_count=8,
            is_ocr=True,
            policy_area="academic_rights",
            section_ref="Section 2",
            chunk_index=1,
        )
        embed_and_store_chunks([chunk1])

        col = ephemeral_client.get_collection(COL_POLICY_ALL)
        result = col.get(ids=[ident])
        assert result and result.get("metadatas")
        meta1 = result["metadatas"][0]
        assert meta1["policy_area"] == "academic_rights"
        assert meta1["chunk_index"] == 1

        # Re-embed (rebuild path) with same data
        embed_and_store_chunks([chunk1])
        result2 = col.get(ids=[ident])
        assert result2 and result2.get("metadatas")
        meta2 = result2["metadatas"][0]
        assert meta2["policy_area"] == "academic_rights"
        assert meta2["chunk_index"] == 1
        assert meta2["is_ocr"] is True
