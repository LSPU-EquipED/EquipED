"""Reference ingestion resolves storage URIs before extraction and cleanup."""

import uuid
from pathlib import Path
from unittest.mock import Mock

import chromadb
import numpy as np
import pytest
from server.core.config import Settings
from server.modules.documents import background, paths
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.journaling import UNVERIFIED_VECTOR_CLEANUP_WARNING
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.schemas import DocumentChunkData


def test_partial_chroma_upsert_failure_cleans_only_failed_document(
    db_session, monkeypatch, ingestion_context
):
    """A failed second embedding batch removes only this document's vectors."""
    create, _storage, _mocked_embed = ingestion_context
    document_id, local, _stored_path = create("syllabus", "local")
    client = chromadb.EphemeralClient()
    real_collection = client.get_or_create_collection(
        "col_reference_all", embedding_function=None
    )
    unrelated_chunk_id = str(uuid.uuid4())
    real_collection.upsert(
        ids=[unrelated_chunk_id],
        embeddings=[[0.0] * 384],
        documents=["unrelated reference"],
        metadatas=[{"document_id": str(uuid.uuid4()), "source_type": "syllabus"}],
    )

    class FailingSecondUpsert:
        def __init__(self):
            self.calls = 0

        def upsert(self, **kwargs):
            self.calls += 1
            if self.calls == 2:
                raise RuntimeError("simulated second batch failure")
            real_collection.upsert(**kwargs)

    failing_collection = FailingSecondUpsert()

    class TrackingClient:
        def get_max_batch_size(self):
            return 32

        def get_or_create_collection(self, name, *, embedding_function=None):
            assert name == "col_reference_all"
            assert embedding_function is None
            return failing_collection

        def get_collection(self, name, *, embedding_function=None):
            return client.get_collection(name, embedding_function=embedding_function)

    class FakeModel:
        def encode(self, texts, **_kwargs):
            return np.zeros((len(texts), 384), dtype=np.float32)

    from server.modules.documents import embedding as document_embedding

    monkeypatch.setattr(
        background, "embed_document_chunks", document_embedding.embed_document_chunks
    )
    monkeypatch.setattr(
        document_embedding, "get_settings", lambda: Settings(database_url="sqlite://")
    )
    monkeypatch.setattr(
        document_embedding, "get_session_factory", lambda: lambda: db_session
    )
    monkeypatch.setattr(
        "server.modules.embeddings.service.get_embedding_model", lambda: FakeModel()
    )
    monkeypatch.setattr(
        "server.modules.embeddings.service.get_chroma_client", lambda: TrackingClient()
    )
    monkeypatch.setattr(
        background,
        "ingest_document",
        lambda *_args, **_kwargs: [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=document_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text=f"reference chunk {index}",
                token_count=3,
                is_ocr=False,
                section_ref=f"section:{index}",
            )
            for index in range(33)
        ],
    )

    background.process_document_ingestion(document_id)

    db_session.expire_all()
    doc = db_session.get(Document, document_id)
    assert failing_collection.calls == 2
    assert doc.processing_status == "FAILED"
    assert doc.processing_warnings == [
        "The document could not be embedded due to an unexpected error."
    ]
    assert (
        db_session.query(DocumentChunk).filter_by(document_id=document_id).count() == 0
    )
    assert not local.exists()
    assert real_collection.get(where={"document_id": str(document_id)})["ids"] == []
    assert real_collection.get(ids=[unrelated_chunk_id])["ids"] == [unrelated_chunk_id]


@pytest.fixture
def ingestion_context(db_session, seeded_user, tmp_path, monkeypatch):
    monkeypatch.setattr(paths, "UPLOAD_ROOT", tmp_path)
    monkeypatch.setattr(
        background, "get_settings", lambda: Settings(database_url="sqlite://")
    )
    monkeypatch.setattr(background, "get_session_factory", lambda: lambda: db_session)
    embed = Mock()
    monkeypatch.setattr(background, "embed_document_chunks", embed)
    storage = Mock()
    monkeypatch.setattr("server.core.storage.get_storage_backend", lambda: storage)

    def create(source_type, mode):
        doc_id = uuid.uuid4()
        local = tmp_path / f"{doc_id}.pdf"
        uri = f"r2://equiped-storage/documents/{doc_id}.pdf"
        if mode in {"local", "cached"}:
            local.write_bytes(b"%PDF-1.7 reference contents")
        doc = Document(
            document_id=doc_id,
            title="Storage reference",
            source_type=source_type,
            file_path=str(local) if mode == "local" else uri,
            uploaded_by=seeded_user.user_id,
            processing_status="PROCESSING",
        )
        db_session.add(doc)
        db_session.commit()
        return doc_id, local, doc.file_path

    return create, storage, embed


@pytest.mark.parametrize("source_type", ["syllabus", "curriculum"])
@pytest.mark.parametrize("mode", ["local", "cached", "download"])
def test_ingestion_resolves_reference_storage(
    db_session, monkeypatch, ingestion_context, source_type, mode
):
    create, storage, embed = ingestion_context
    doc_id, local, stored_path = create(source_type, mode)
    storage.file_exists.return_value = True

    def download(key, target):
        assert key == stored_path
        target.write_bytes(b"%PDF-1.7 reference contents")
        return target

    storage.download_file.side_effect = download

    def ingest(file_path, actual_type, document_id, program=None):
        assert Path(file_path) == local.resolve()
        assert Path(file_path).read_bytes() == b"%PDF-1.7 reference contents"
        assert actual_type == source_type
        assert document_id == str(doc_id)
        return [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type=source_type,
                agent_domain="all",
                page_number=1,
                text="Course reference contents",
                token_count=3,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
            )
        ]

    monkeypatch.setattr(background, "ingest_document", ingest)

    def assert_processing_during_embedding(_document_id):
        db_session.expire_all()
        assert db_session.get(Document, doc_id).processing_status == "PROCESSING"

    embed.side_effect = assert_processing_during_embedding
    background.process_document_ingestion(doc_id)

    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    assert doc.processing_status == "PROCESSED"
    assert doc.processing_warnings is None
    assert doc.file_path == stored_path
    assert db_session.query(DocumentChunk).filter_by(document_id=doc_id).count() == 1
    embed.assert_called_once_with(doc_id)
    if mode == "download":
        storage.download_file.assert_called_once_with(stored_path, local.resolve())
    else:
        storage.file_exists.assert_not_called()
        storage.download_file.assert_not_called()


@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_embedding_failure_cleans_up_only_after_verified_vector_delete(
    db_session, monkeypatch, ingestion_context, cleanup_fails
):
    create, storage, embed = ingestion_context
    doc_id, local, stored_path = create("syllabus", "download")
    storage.file_exists.return_value = True

    def download(key, target):
        target.write_bytes(b"%PDF-1.7 reference contents")
        return target

    storage.download_file.side_effect = download
    monkeypatch.setattr(
        background,
        "ingest_document",
        lambda *_args, **_kwargs: [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="Course reference contents",
                token_count=3,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
            )
        ],
    )
    cleanup = (
        Mock(side_effect=RuntimeError("private Chroma credentials"))
        if cleanup_fails
        else Mock()
    )
    monkeypatch.setattr(background, "delete_chroma_vectors_strict", cleanup)
    embed.side_effect = RuntimeError("private embedding provider details")

    background.process_document_ingestion(doc_id)

    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    chunks = db_session.query(DocumentChunk).filter_by(document_id=doc_id).count()
    assert doc.processing_status == "FAILED"
    assert doc.file_path == stored_path
    cleanup.assert_called_once_with(str(doc_id), "syllabus")
    if cleanup_fails:
        assert doc.processing_warnings == [UNVERIFIED_VECTOR_CLEANUP_WARNING]
        assert chunks == 1
        assert local.exists()
    else:
        assert doc.processing_warnings == [
            "The document could not be embedded due to an unexpected error."
        ]
        assert chunks == 0
        assert not local.exists()


def test_terminal_status_commit_failure_cleans_up_embedded_state(
    db_session, monkeypatch, ingestion_context
):
    create, storage, embed = ingestion_context
    doc_id, local, stored_path = create("syllabus", "download")
    storage.file_exists.return_value = True
    storage.download_file.side_effect = lambda _key, target: (
        target.write_bytes(b"%PDF-1.7 reference contents") or target
    )
    monkeypatch.setattr(
        background,
        "ingest_document",
        lambda *_args, **_kwargs: [
            DocumentChunkData(
                chunk_id=uuid.uuid4(),
                document_id=doc_id,
                source_type="syllabus",
                agent_domain="all",
                page_number=1,
                text="Course reference contents",
                token_count=3,
                is_ocr=False,
                section_ref="syllabus_course_content:1:1",
            )
        ],
    )
    cleanup = Mock()
    monkeypatch.setattr(background, "delete_chroma_vectors_strict", cleanup)
    real_commit = db_session.commit
    commit_count = 0

    def fail_terminal_commit():
        nonlocal commit_count
        commit_count += 1
        if commit_count == 3:
            raise RuntimeError("private database details")
        real_commit()

    monkeypatch.setattr(db_session, "commit", fail_terminal_commit)

    background.process_document_ingestion(doc_id)

    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    chunks = db_session.query(DocumentChunk).filter_by(document_id=doc_id).count()
    assert embed.call_count == 1
    assert commit_count == 4  # chunk write, metadata, failed terminal, finalization
    assert doc.processing_status == "FAILED"
    assert doc.file_path == stored_path
    assert doc.processing_warnings == [
        "The document could not be processed due to an unexpected error."
    ]
    assert chunks == 0
    assert not local.exists()
    cleanup.assert_called_once_with(str(doc_id), "syllabus")


@pytest.mark.parametrize("failure", ["missing", "download", "extraction"])
def test_storage_or_extraction_failure_fails_closed(
    db_session, monkeypatch, ingestion_context, failure
):
    create, storage, embed = ingestion_context
    doc_id, local, stored_path = create("syllabus", "download")
    storage.file_exists.return_value = failure != "missing"

    def download(key, target):
        if failure == "download":
            raise RuntimeError("private storage credentials")
        target.write_bytes(b"%PDF-1.7 reference contents")
        return target

    storage.download_file.side_effect = download
    ingest = Mock(side_effect=ExtractionFailedError("No Course Contents table found"))
    monkeypatch.setattr(background, "ingest_document", ingest)

    background.process_document_ingestion(doc_id)

    db_session.expire_all()
    doc = db_session.get(Document, doc_id)
    assert doc.processing_status == "FAILED"
    assert doc.file_path == stored_path
    assert db_session.query(DocumentChunk).filter_by(document_id=doc_id).count() == 0
    assert not local.exists()
    embed.assert_not_called()
    storage.delete_file.assert_not_called()
    if failure == "extraction":
        ingest.assert_called_once()
        assert doc.processing_warnings == ["No Course Contents table found"]
    else:
        ingest.assert_not_called()
        assert doc.processing_warnings == ["The uploaded file could not be processed."]
