"""Tests for embeddings.policy_retrieval — mapping, allowlist, orphan exclusion,
fallback, tie-sort, bounds, fail-open behaviour, and provenance integrity.

Uses real chromadb.EphemeralClient for Chroma interaction tests.
"""

from __future__ import annotations

import logging
import uuid
from pathlib import Path

import chromadb
import pytest
from server.modules.documents.models import Document, DocumentChunk
from server.modules.embeddings.collections import COL_POLICY_ALL
from server.modules.embeddings.policy_retrieval import (
    ITSO_POLICY_MAP,
    PolicyEvidenceChunk,
    _build_provenance_hash,
    _parse_policy_chunks,
    _unavailable_result,
    retrieve_policy_context,
)

# Sentinel — must never appear in log output.
_SENTINEL = "SENTINEL-CAUGHT-ERROR"

_TMP = Path("/tmp")


# ============================================================================
# Chroma fixtures
# ============================================================================


@pytest.fixture()
def ephemeral_client():
    """Return a real EphemeralClient for Chroma tests."""
    return chromadb.EphemeralClient()


@pytest.fixture(autouse=True)
def _cleanup_test_pdfs():
    """Remove any temp PDF files created during tests."""
    yield
    for p in _TMP.glob("test_policy_*"):
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


# ============================================================================
# Helpers — factory functions for test data
# ============================================================================


def _healthy_doc(db_session, policy_area: str, tag: str) -> uuid.UUID:
    """Insert a healthy policy Document row with a real temp PDF file.

    Returns the document UUID.
    """
    doc_id = uuid.uuid4()
    pdf = _TMP / f"test_policy_{tag}_{doc_id}.pdf"
    pdf.write_text("test")
    db_session.add(
        Document(
            document_id=doc_id,
            title=f"Policy {tag}",
            source_type="policy",
            policy_area=policy_area,
            file_path=str(pdf),
            uploaded_by=uuid.uuid4(),
            processing_status="PROCESSED",
        )
    )
    db_session.flush()
    return doc_id


def _chunk_in_db(db_session, doc_id, *, chroma_stored: bool = True,
                 policy_area: str | None = None) -> uuid.UUID:
    """Create one DocumentChunk row and return its UUID.

    Caller should ``session.commit()`` before post-validation tests.
    If ``policy_area`` is not given, it is looked up from the parent Document.
    """
    if policy_area is None:
        parent = db_session.get(Document, doc_id)
        if parent is not None:
            policy_area = parent.policy_area
    cid = uuid.uuid4()
    db_session.add(
        DocumentChunk(
            chunk_id=cid,
            document_id=doc_id,
            source_type="policy",
            agent_domain="itso",
            page_number=1,
            text="policy test chunk",
            token_count=4,
            is_ocr=False,
            chroma_stored=chroma_stored,
            policy_area=policy_area,
            section_ref="Section 1",
            chunk_index=0,
        )
    )
    db_session.flush()
    return cid


def _seed_policy_chunks(
    collection, doc_id: str, policy_area: str, chunk_ids: list[uuid.UUID],
):
    """Seed chunks into Chroma using the given SQL chunk IDs.

    This simulates the real embedding flow where Chroma IDs == SQL chunk IDs.
    """
    count = len(chunk_ids)
    str_ids = [str(cid) for cid in chunk_ids]
    docs_text = [f"{policy_area} text chunk {i}" for i in range(count)]
    metas = [
        {
            "chunk_id": str_ids[i],
            "document_id": doc_id,
            "policy_area": policy_area,
            "page_number": i + 1,
            "token_count": 10 + i,
            "section_ref": f"Section {i + 1}",
            "chunk_index": i,
        }
        for i in range(count)
    ]
    embeddings = [[0.1 + i * 0.01] * 384 for i in range(count)]
    collection.add(
        ids=str_ids, documents=docs_text, metadatas=metas, embeddings=embeddings,
    )


# ============================================================================
# Mapping tests
# ============================================================================


class TestITSOToPolicyMapping:
    def test_itso_03_maps_to_intellectual_property(self):
        assert ITSO_POLICY_MAP["ITSO-03"] == ("intellectual_property", "general_itso")

    def test_itso_04_maps_to_data_privacy(self):
        assert ITSO_POLICY_MAP["ITSO-04"] == ("data_privacy", "general_itso")

    def test_itso_05_maps_to_academic_rights(self):
        assert ITSO_POLICY_MAP["ITSO-05"] == ("academic_rights", "general_itso")

    def test_unknown_criterion_returns_none(self):
        assert ITSO_POLICY_MAP.get("ITSO-01") is None
        assert ITSO_POLICY_MAP.get("ITSO-99") is None

    def test_all_mapped_have_primary_and_fallback(self):
        for _criteria, areas in ITSO_POLICY_MAP.items():
            assert len(areas) >= 2
            assert areas[0] != "general_itso"


# ============================================================================
# Chroma result parsing tests
# ============================================================================


class TestParsePolicyChunks:
    def test_empty_result_returns_empty(self):
        assert _parse_policy_chunks({}) == []

    def test_none_lists_returns_empty(self):
        assert _parse_policy_chunks({"documents": None}) == []

    def test_skips_missing_metadata(self):
        result = {
            "documents": [["text one", "text two"]],
            "metadatas": [
                [{"chunk_id": "c1", "document_id": "d1", "policy_area": "ip"}, {}]
            ],
            "distances": [[0.1, 0.2]],
        }
        chunks = _parse_policy_chunks(result)
        assert len(chunks) == 1
        assert chunks[0].chunk_id == "c1"

    def test_skips_empty_text(self):
        result = {
            "documents": [["", "valid text"]],
            "metadatas": [
                [
                    {"chunk_id": "c1", "document_id": "d1", "policy_area": "ip"},
                    {"chunk_id": "c2", "document_id": "d2", "policy_area": "dp"},
                ]
            ],
            "distances": [[0.1, 0.2]],
        }
        chunks = _parse_policy_chunks(result)
        assert len(chunks) == 1
        assert chunks[0].text == "valid text"

    def test_parses_all_valid_entries(self):
        result = {
            "documents": [["text a", "text b"]],
            "metadatas": [
                [
                    {"chunk_id": "c1", "document_id": "d1", "policy_area": "ip",
                     "page_number": 2, "token_count": 50},
                    {"chunk_id": "c2", "document_id": "d2", "policy_area": "dp",
                     "page_number": None, "token_count": None},
                ]
            ],
            "distances": [[0.5, 0.3]],
        }
        chunks = _parse_policy_chunks(result)
        assert len(chunks) == 2
        assert chunks[0].distance == 0.5
        assert chunks[1].distance == 0.3

    def test_skips_nonfinite_distances(self):
        """Non-finite distances must be skipped, never raise."""
        result = {
            "documents": [["good", "nan_dist", "inf_dist", "good2"]],
            "metadatas": [
                [
                    {"chunk_id": "c1", "document_id": "d1", "policy_area": "ip"},
                    {"chunk_id": "c2", "document_id": "d2", "policy_area": "ip"},
                    {"chunk_id": "c3", "document_id": "d3", "policy_area": "ip"},
                    {"chunk_id": "c4", "document_id": "d4", "policy_area": "ip"},
                ]
            ],
            "distances": [[0.1, float("nan"), float("inf"), 0.2]],
        }
        chunks = _parse_policy_chunks(result)
        assert len(chunks) == 2
        assert chunks[0].chunk_id == "c1"
        assert chunks[1].chunk_id == "c4"


# ============================================================================
# Deterministic ranking and bounds
# ============================================================================


class TestRankingAndBounds:
    def test_sort_by_distance_then_chunk_id(self):
        chunks = [
            PolicyEvidenceChunk("c", "d1", "text", "ip", None, None, 0.5),
            PolicyEvidenceChunk("a", "d1", "text", "ip", None, None, 0.3),
            PolicyEvidenceChunk("b", "d1", "text", "ip", None, None, 0.3),
        ]
        sorted_chunks = sorted(chunks, key=lambda c: (c.distance, c.chunk_id))
        assert sorted_chunks[0].chunk_id == "a"
        assert sorted_chunks[1].chunk_id == "b"
        assert sorted_chunks[2].chunk_id == "c"

    def test_default_max_chunks_is_5(self):
        from server.modules.embeddings.policy_retrieval import (
            _DEFAULT_MAX_CHUNKS_PER_CRITERION,
        )
        assert _DEFAULT_MAX_CHUNKS_PER_CRITERION == 5


# ============================================================================
# General fallback / error tests
# ============================================================================


class TestGeneralFallback:
    def test_returns_unavailable_when_no_db(self):
        result = retrieve_policy_context("ITSO-03", [0.0] * 384, db=None)
        assert result.status == "unavailable"
        assert result.policy_area == "intellectual_property"

    def test_returns_unavailable_for_unknown_criterion(self, db_session):
        result = retrieve_policy_context("ITSO-99", [0.0] * 384, db_session)
        assert result.status == "unavailable"
        assert result.policy_area == "unknown"


class TestFailOpen:
    def test_unavailable_result_is_always_safe(self):
        result = _unavailable_result("academic_rights")
        assert result.status == "unavailable"
        assert result.chunks == ()
        assert isinstance(result.provenance_hash, str)
        assert len(result.provenance_hash) == 64


# ============================================================================
# Provenance hash tests
# ============================================================================


class TestProvenanceHash:
    def test_empty_produces_stable_hash(self):
        h1 = _build_provenance_hash(())
        h2 = _build_provenance_hash(())
        assert h1 == h2
        assert len(h1) == 64

    def test_same_chunks_produce_same_hash(self):
        chunks = (
            PolicyEvidenceChunk("c1", "d1", "same text", "ip", 1, 10, 0.1),
            PolicyEvidenceChunk("c2", "d2", "same text", "dp", None, None, 0.2),
        )
        assert _build_provenance_hash(chunks) == _build_provenance_hash(chunks)

    def test_changed_text_changes_hash(self):
        chunks_a = (PolicyEvidenceChunk("c1", "d1", "original text", "ip", 1, 10, 0.1),)
        chunks_b = (PolicyEvidenceChunk("c1", "d1", "changed text", "ip", 1, 10, 0.1),)
        assert _build_provenance_hash(chunks_a) != _build_provenance_hash(chunks_b)

    def test_hash_is_opaque_hex(self):
        chunk = PolicyEvidenceChunk("my-chunk", "my-doc", "text", "ip", None, None, 0.1)
        chunks = (chunk,)
        h = _build_provenance_hash(chunks)
        assert "my-chunk" not in h
        assert "my-doc" not in h
        assert all(c in "0123456789abcdef" for c in h)
        assert len(h) == 64


# ============================================================================
# Integration: retrieval with real SQL allowlist + real Chroma EphemeralClient
# ============================================================================


class TestRetrievePolicyContextIntegration:
    """Full integration using real SQL allowlist and real EphemeralClient.

    Every test:
    1. Creates healthy policy Document + DocumentChunk rows in SQL.
    2. Seeds the same chunk IDs into Chroma (matching real embedding flow).
    3. Patches ``get_chroma_client`` to return the ephemeral instance.
    4. Calls ``retrieve_policy_context`` and asserts behaviour.
    """

    def test_happy_path_returns_available(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        doc_id = _healthy_doc(db_session, "data_privacy", "happy")
        chunk_id = _chunk_in_db(db_session, doc_id)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(doc_id), "data_privacy", [chunk_id])

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=3,
        )
        assert result.status == "available"
        assert result.policy_area == "data_privacy"
        assert 1 <= result.chunk_count <= 3
        assert isinstance(result.provenance_hash, str)
        assert len(result.provenance_hash) == 64

    def test_excludes_orphan_document(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        """Chunks from a doc not in the SQL allowlist must be excluded."""
        healthy_id = _healthy_doc(db_session, "data_privacy", "healthy")
        healthy_chunk = _chunk_in_db(db_session, healthy_id)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        # Seed the healthy doc's chunk.
        _seed_policy_chunks(col, str(healthy_id), "data_privacy", [healthy_chunk])
        # Seed an orphan chunk — doc never registered in SQL.
        orphan_id = uuid.uuid4()
        _seed_policy_chunks(col, "orphan-doc-uuid", "data_privacy", [orphan_id])

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=5,
        )
        assert result.status == "available"
        for chunk in result.chunks:
            assert chunk.document_id == str(healthy_id)

    def test_excludes_stale_vector_no_chroma_stored(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        """Stale vector in Chroma for a doc lacking chroma_stored chunks is excluded."""
        doc_id = _healthy_doc(db_session, "intellectual_property", "stale")
        _chunk_in_db(db_session, doc_id, chroma_stored=False)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(doc_id), "intellectual_property", [uuid.uuid4()])

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-03", [0.1] * 384, db_session, max_chunks=3,
        )
        assert result.status == "unavailable"

    def test_falls_back_to_general_itso(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        gen_id = _healthy_doc(db_session, "general_itso", "gen")
        gen_chunk = _chunk_in_db(db_session, gen_id)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(gen_id), "general_itso", [gen_chunk])

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-03", [0.1] * 384, db_session, max_chunks=3,
        )
        assert result.status == "available"
        assert result.policy_area == "general_itso"

    def test_max_chunks_clamped_to_5(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        doc_id = _healthy_doc(db_session, "academic_rights", "clamp")
        chunk_ids = [_chunk_in_db(db_session, doc_id) for _ in range(10)]
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(doc_id), "academic_rights", chunk_ids)

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-05", [0.1] * 384, db_session, max_chunks=100,
        )
        assert result.status == "available"
        assert result.chunk_count <= 5

    def test_min_chunks_clamped_to_1(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        doc_id = _healthy_doc(db_session, "data_privacy", "minclamp")
        chunk_ids = [_chunk_in_db(db_session, doc_id) for _ in range(5)]
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(doc_id), "data_privacy", chunk_ids)

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=0,
        )
        assert result.status == "available"
        assert result.chunk_count == 1

    def test_excludes_wrong_document_tuple(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        """Chunk with valid chunk_id but wrong document_id in Chroma metadata."""
        doc_a = _healthy_doc(db_session, "data_privacy", "docA")
        doc_b = _healthy_doc(db_session, "data_privacy", "docB")
        _chunk_in_db(db_session, doc_a)
        # chunk_b belongs to doc_b in SQL but is seeded into Chroma with doc_a's ID
        chunk_b = _chunk_in_db(db_session, doc_b)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        # Seed chunk_b with WRONG document_id in Chroma metadata
        str_ids = [str(chunk_b)]
        docs_text = ["wrong doc metadata"]
        metas = [
            {
                "chunk_id": str(chunk_b),
                "document_id": str(doc_a),  # WRONG — SQL says doc_b
                "policy_area": "data_privacy",
                "page_number": 1,
                "token_count": 5,
            }
        ]
        embeddings = [[0.1] * 384]
        col.add(
            ids=str_ids, documents=docs_text, metadatas=metas,
            embeddings=embeddings,
        )

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=5,
        )
        assert result.status == "unavailable"

    def test_excludes_wrong_policy_area_tuple(
        self, db_session, ephemeral_client, monkeypatch,
    ):
        """Chunk with valid chunk_id but wrong policy_area in Chroma metadata."""
        doc_id = _healthy_doc(db_session, "data_privacy", "areaMismatch")
        chunk_id = _chunk_in_db(db_session, doc_id)
        db_session.commit()

        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        str_ids = [str(chunk_id)]
        docs_text = ["wrong area metadata"]
        metas = [
            {
                "chunk_id": str(chunk_id),
                "document_id": str(doc_id),
                "policy_area": "intellectual_property",  # WRONG — SQL says data_privacy
                "page_number": 1,
                "token_count": 5,
            }
        ]
        embeddings = [[0.1] * 384]
        col.add(
            ids=str_ids, documents=docs_text, metadatas=metas,
            embeddings=embeddings,
        )

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            lambda: ephemeral_client,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=5,
        )
        assert result.status == "unavailable"

    def test_logs_use_category_only_no_raw_ids(
        self, db_session, ephemeral_client, monkeypatch, caplog,
    ):
        """All log messages use fixed category labels; no raw criterion or doc IDs."""
        caplog.set_level(
            logging.WARNING, logger="server.modules.embeddings.policy_retrieval"
        )

        doc_id = _healthy_doc(db_session, "data_privacy", "logtest")
        chunk_id = _chunk_in_db(db_session, doc_id)
        db_session.commit()
        col = ephemeral_client.get_or_create_collection(COL_POLICY_ALL)
        _seed_policy_chunks(col, str(doc_id), "data_privacy", [chunk_id])

        def _broken_chroma():
            raise RuntimeError(_SENTINEL)

        monkeypatch.setattr(
            "server.modules.embeddings.policy_retrieval.get_chroma_client",
            _broken_chroma,
        )

        result = retrieve_policy_context(
            "ITSO-04", [0.1] * 384, db_session, max_chunks=3,
        )
        assert result.status == "unavailable"

        log_text = " ".join(r.message for r in caplog.records)
        assert _SENTINEL not in log_text, f"str(exc) leaked into logs: {log_text}"
        # Must use only fixed category labels, never raw IDs or criteria
        assert "policy:collection" in log_text
        # The sentinel (raw error text) must not appear
        for record in caplog.records:
            assert _SENTINEL not in record.message

    def test_logs_unknown_criterion_no_raw_id(
        self, db_session, caplog,
    ):
        """Unknown criterion log uses category-only message, no raw ID."""
        caplog.set_level(
            logging.WARNING, logger="server.modules.embeddings.policy_retrieval"
        )

        result = retrieve_policy_context("ITSO-99", [0.0] * 384, db_session)
        assert result.status == "unavailable"

        for record in caplog.records:
            assert _SENTINEL not in record.message
            # Must not contain the raw criterion ID
            assert "ITSO-99" not in record.message
            # Must use the category label
            assert "policy:criteria" in record.message
