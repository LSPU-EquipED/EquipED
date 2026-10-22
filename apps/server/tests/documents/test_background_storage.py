"""Reference ingestion resolves storage URIs before extraction and cleanup."""

import uuid
from pathlib import Path
from unittest.mock import Mock

import pytest
from server.core.config import Settings
from server.modules.documents import background, paths
from server.modules.documents.exceptions import ExtractionFailedError
from server.modules.documents.models import Document, DocumentChunk
from server.modules.documents.schemas import DocumentChunkData


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
