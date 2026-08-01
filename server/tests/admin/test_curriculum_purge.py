"""Focused tests for the curriculum purge service and CLI.

Covers the OpenSpec purge tasks:
- dry-run-by-default planning that never mutates anything
- strict DB / Chroma / upload-root reachability
- no active curriculum docs or referencing jobs
- safe scoped vector deletion inside the shared reference collection
- root-contained, non-symlink, unique PDF path checks
- one SQL transaction clearing nullable EvaluationFlag.chunk_id and
  curriculum_id pointers and deleting chunk/doc rows while preserving job
  partial flags
- fail-closed external cleanup: vector/file deletion is strictly verified
  before the SQL commit; failures roll back, raise, and can be rerun
- content-free JSON manifest
- CLI dry-run / --execute behavior and manifest file output
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import chromadb
import pytest
from server.core.database import Base
from server.modules.admin.curriculum_purge import (
    COL_REFERENCE_ALL,
    PurgeBlockedError,
    PurgeExecutionError,
    PurgeUnreachableError,
    execute_curriculum_purge,
    plan_curriculum_purge,
)
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult, CriterionScore, EvaluationFlag
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Distinctive content that must never leak into the manifest.
CONTENT_MARKER = "SECRET_CURRICULUM_CONTENT_MARKER_7f3a"


@pytest.fixture()
def owner(db_session):
    user = create_user(
        db_session,
        name="Purge Owner",
        email="purge-owner@example.com",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    return user


@pytest.fixture()
def ephemeral_client():
    return chromadb.EphemeralClient()


@pytest.fixture()
def upload_root(tmp_path):
    root = tmp_path / "uploads"
    root.mkdir()
    return root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _seed_document(
    db_session,
    *,
    owner_id,
    source_type: str,
    upload_root: Path,
    document_id: uuid.UUID | None = None,
    program: str = "BSCS",
    processing_status: str = "PROCESSED",
    with_file: bool = True,
    file_path: str | None = None,
) -> uuid.UUID:
    document_id = document_id or uuid.uuid4()
    if file_path is None:
        file_path = f"uploads/{document_id}.pdf"
    if with_file:
        (upload_root.parent / file_path).parent.mkdir(parents=True, exist_ok=True)
        (upload_root.parent / file_path).write_bytes(b"%PDF-1.4 purge-test")
    db_session.add(
        Document(
            document_id=document_id,
            title=f"{source_type} {document_id}",
            program=program,
            source_type=source_type,
            file_path=file_path,
            uploaded_by=owner_id,
            processing_status=processing_status,
            evaluation_readiness="READY",
        )
    )
    db_session.commit()
    return document_id


def _seed_chunk(
    db_session,
    *,
    document_id: uuid.UUID,
    source_type: str,
    text: str = CONTENT_MARKER,
) -> uuid.UUID:
    chunk_id = uuid.uuid4()
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text=text,
            token_count=4,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    db_session.commit()
    return chunk_id


def _seed_job(
    db_session,
    *,
    document_id: uuid.UUID,
    curriculum_id: uuid.UUID | None,
    status: str,
    partial_without_curriculum: bool = False,
    partial_reason: str | None = None,
) -> EvaluationJob:
    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=document_id,
        curriculum_id=curriculum_id,
        status=status,
        partial_without_curriculum=partial_without_curriculum,
        partial_reason=partial_reason,
    )
    db_session.add(job)
    db_session.commit()
    return job


def _seed_vectors(client, *, document_id: uuid.UUID, n: int, source_type: str):
    collection = client.get_or_create_collection(COL_REFERENCE_ALL)
    collection.add(
        ids=[f"{document_id}::v{i}" for i in range(n)],
        embeddings=[[0.1 * (i + 1)] * 8 for i in range(n)],
        documents=["vector text"] * n,
        metadatas=[
            {"document_id": str(document_id), "source_type": source_type}
            for _ in range(n)
        ],
    )


def _vector_count(client, *, document_id: uuid.UUID) -> int:
    collection = client.get_collection(COL_REFERENCE_ALL)
    result = collection.get(where={"document_id": {"$eq": str(document_id)}})
    return len(result.get("ids", []))


def _patch_chroma(monkeypatch, client):
    monkeypatch.setattr(
        "server.modules.admin.curriculum_purge.get_chroma_client",
        lambda: client,
    )


# ---------------------------------------------------------------------------
# Service: planning (dry run)
# ---------------------------------------------------------------------------


def test_plan_dry_run_is_non_mutating(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=3, source_type="curriculum",
    )
    syllabus_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        upload_root=upload_root,
    )
    _seed_vectors(
        ephemeral_client, document_id=syllabus_id, n=2, source_type="syllabus",
    )

    manifest = plan_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )

    assert manifest["dry_run"] is True
    assert manifest["blockers"] == []
    assert manifest["checks"] == {"database": True, "chroma": True, "upload_root": True}
    assert manifest["collection"] == COL_REFERENCE_ALL
    assert manifest["totals"]["documents"] == 1
    assert manifest["totals"]["chunks"] == 1
    assert manifest["totals"]["vectors_to_delete"] == 3
    assert manifest["curricula"][0]["document_id"] == str(curriculum_id)
    assert manifest["curricula"][0]["file"]["safe"] is True

    # Nothing was mutated.
    assert db_session.get(Document, curriculum_id) is not None
    assert db_session.query(DocumentChunk).count() == 1
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 3
    assert _vector_count(ephemeral_client, document_id=syllabus_id) == 2
    assert (upload_root / f"{curriculum_id}.pdf").exists()


def test_plan_reports_unreachable_chroma(db_session, owner, upload_root, monkeypatch):
    def _boom():
        raise RuntimeError("chroma down")

    monkeypatch.setattr(
        "server.modules.admin.curriculum_purge.get_chroma_client", _boom
    )
    _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )

    manifest = plan_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=None
    )

    assert manifest["checks"]["chroma"] is False
    assert "chroma unreachable" in manifest["blockers"]
    # Planning still reports the curricula it found.
    assert manifest["totals"]["documents"] == 1


def test_plan_reports_missing_upload_root(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    missing = upload_root.parent / "no-such-uploads"
    _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )

    manifest = plan_curriculum_purge(
        db_session, upload_root=missing, chroma_client=ephemeral_client
    )

    assert manifest["checks"]["upload_root"] is False
    assert any("upload root is not a directory" in b for b in manifest["blockers"])


def test_plan_lists_active_job_blocker(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    slm_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="slm",
        upload_root=upload_root,
    )
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_job(
        db_session,
        document_id=slm_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.EVALUATING.value,
    )

    manifest = plan_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )

    assert any("active evaluation job" in b for b in manifest["blockers"])
    assert manifest["curricula"][0]["jobs_referencing"] == 1


# ---------------------------------------------------------------------------
# Service: execution
# ---------------------------------------------------------------------------


def test_execute_happy_path_purges_rows_vectors_and_files(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    slm_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="slm",
        upload_root=upload_root,
    )
    curr_a = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    curr_b = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
        program="BSInfoTech",
    )
    syllabus_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        upload_root=upload_root,
    )
    for doc_id in (curr_a, curr_b):
        _seed_chunk(db_session, document_id=doc_id, source_type="curriculum")
        _seed_vectors(
            ephemeral_client, document_id=doc_id, n=2, source_type="curriculum",
        )
    _seed_chunk(db_session, document_id=syllabus_id, source_type="syllabus")
    _seed_vectors(
        ephemeral_client, document_id=syllabus_id, n=1, source_type="syllabus",
    )
    # Two terminal jobs referencing curr_a, one with partial flags.
    _seed_job(
        db_session,
        document_id=slm_id,
        curriculum_id=curr_a,
        status=EvaluationStatus.COMPLETED.value,
        partial_without_curriculum=True,
        partial_reason="Curriculum evaluation flow retired",
    )
    _seed_job(
        db_session,
        document_id=slm_id,
        curriculum_id=curr_a,
        status=EvaluationStatus.FAILED.value,
    )

    manifest = execute_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )

    assert manifest["dry_run"] is False
    assert manifest["blockers"] == []
    assert manifest["results"]["documents_deleted"] == 2
    assert manifest["results"]["chunks_deleted"] == 2
    assert manifest["results"]["jobs_curriculum_cleared"] == 2
    assert manifest["results"]["vectors_deleted"] == 4
    assert manifest["results"]["files_deleted"] == 2
    assert manifest["totals"]["documents"] == 2

    # Curriculum rows and chunks are gone; syllabus survives.
    assert db_session.get(Document, curr_a) is None
    assert db_session.get(Document, curr_b) is None
    assert db_session.query(DocumentChunk).count() == 1
    assert db_session.get(Document, syllabus_id) is not None

    # Job curriculum pointers cleared; partial flags preserved.
    jobs = (
        db_session.query(EvaluationJob)
        .order_by(EvaluationJob.evaluation_id)
        .all()
    )
    assert len(jobs) == 2
    for job in jobs:
        assert job.curriculum_id is None
    completed = next(j for j in jobs if j.status == EvaluationStatus.COMPLETED.value)
    assert completed.partial_without_curriculum is True
    assert completed.partial_reason == "Curriculum evaluation flow retired"
    failed = next(j for j in jobs if j.status == EvaluationStatus.FAILED.value)
    assert failed.partial_without_curriculum is False

    # Scoped vectors: curriculum vectors deleted, syllabus vectors retained.
    assert _vector_count(ephemeral_client, document_id=curr_a) == 0
    assert _vector_count(ephemeral_client, document_id=curr_b) == 0
    assert _vector_count(ephemeral_client, document_id=syllabus_id) == 1

    # Local PDFs deleted.
    assert not (upload_root / f"{curr_a}.pdf").exists()
    assert not (upload_root / f"{curr_b}.pdf").exists()


def test_execute_blocks_on_active_job(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    slm_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="slm",
        upload_root=upload_root,
    )
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=1, source_type="curriculum",
    )
    _seed_job(
        db_session,
        document_id=slm_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.SUBMITTED.value,
    )

    with pytest.raises(PurgeBlockedError, match="active evaluation job"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    # Nothing was mutated.
    assert db_session.get(Document, curriculum_id) is not None
    assert db_session.query(DocumentChunk).count() == 1
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 1
    assert (upload_root / f"{curriculum_id}.pdf").exists()


def test_execute_blocks_on_active_document_processing(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
        processing_status="PROCESSING",
    )

    with pytest.raises(PurgeBlockedError, match="still processing"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    assert db_session.get(Document, curriculum_id) is not None


def test_execute_blocks_on_path_escaping_upload_root(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
        file_path="../outside-root.pdf",
        with_file=False,
    )

    with pytest.raises(PurgeBlockedError, match="unsafe path"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    assert db_session.get(Document, curriculum_id) is not None


def test_execute_blocks_on_symlink_path(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    # Real file outside the root; curriculum file_path is a symlink to it.
    outside = upload_root.parent / "real-target.pdf"
    outside.write_bytes(b"%PDF-1.4 target")
    link = upload_root / "linked.pdf"
    link.symlink_to(outside)
    curriculum_id = uuid.uuid4()
    _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
        document_id=curriculum_id,
        file_path=f"uploads/{link.name}",
        with_file=False,
    )

    with pytest.raises(PurgeBlockedError, match="unsafe path"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    assert db_session.get(Document, curriculum_id) is not None
    assert outside.exists()


def test_execute_commit_failure_is_retryable(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    """A commit failure rolls the DB back but keeps external cleanup done;
    the very same purge rerun then completes successfully."""
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=1, source_type="curriculum",
    )

    original_commit = db_session.commit
    fail_commit = {"fail": True}

    def _flaky_commit():
        if fail_commit["fail"]:
            raise RuntimeError("forced commit failure")
        return original_commit()

    monkeypatch.setattr(db_session, "commit", _flaky_commit)

    with pytest.raises(RuntimeError, match="forced commit failure"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    # Database transaction rolled back: rows restored and rerunnable.
    db_session.expire_all()
    assert db_session.get(Document, curriculum_id) is not None
    assert db_session.query(DocumentChunk).count() == 1
    # External cleanup already happened before the failed commit; on rerun the
    # zero-vector / missing-file states are tolerated, so the retry succeeds.
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 0
    assert not (upload_root / f"{curriculum_id}.pdf").exists()

    fail_commit["fail"] = False
    manifest = execute_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )
    assert manifest["dry_run"] is False
    assert manifest["results"]["documents_deleted"] == 1
    assert manifest["results"]["vectors_deleted"] == 0
    assert manifest["results"]["files_missing"] == 1
    db_session.expire_all()
    assert db_session.get(Document, curriculum_id) is None


def test_execute_vector_delete_failure_raises_and_is_retryable(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    """A Chroma delete error raises, rolls back, and a fixed rerun succeeds."""
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=1, source_type="curriculum",
    )

    fail_delete = {"fail": True}
    from chromadb.api.models.Collection import Collection as ChromaCollection

    original_delete = ChromaCollection.delete

    def _flaky_delete(self, *args, **kwargs):
        if fail_delete["fail"]:
            raise RuntimeError("chroma delete down")
        return original_delete(self, *args, **kwargs)

    monkeypatch.setattr(ChromaCollection, "delete", _flaky_delete)

    with pytest.raises(PurgeExecutionError, match="vector cleanup failed"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    # Nothing was committed or left half-deleted: rows, vectors, files intact.
    db_session.expire_all()
    assert db_session.get(Document, curriculum_id) is not None
    assert db_session.query(DocumentChunk).count() == 1
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 1
    assert (upload_root / f"{curriculum_id}.pdf").exists()

    # Retry semantics: once the delete works again the same run completes.
    fail_delete["fail"] = False
    manifest = execute_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )
    assert manifest["results"]["documents_deleted"] == 1
    assert manifest["results"]["vectors_deleted"] == 1
    assert manifest["results"]["files_deleted"] == 1
    db_session.expire_all()
    assert db_session.get(Document, curriculum_id) is None
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 0


def test_execute_file_unlink_failure_raises_and_rolls_back(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    """An unlink error raises PurgeExecutionError and rolls the DB back."""
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=1, source_type="curriculum",
    )

    real_unlink = Path.unlink

    def _blocking_unlink(self):
        if str(self).startswith(str(upload_root)):
            raise OSError("permission denied")
        return real_unlink(self)

    monkeypatch.setattr(Path, "unlink", _blocking_unlink)

    with pytest.raises(PurgeExecutionError, match="file cleanup failed"):
        execute_curriculum_purge(
            db_session, upload_root=upload_root, chroma_client=ephemeral_client
        )

    db_session.expire_all()
    assert db_session.get(Document, curriculum_id) is not None
    assert db_session.query(DocumentChunk).count() == 1
    # Vectors were already deleted before the file step; DB rows restored.
    assert _vector_count(ephemeral_client, document_id=curriculum_id) == 0
    assert (upload_root / f"{curriculum_id}.pdf").exists()


def test_execute_clears_evaluation_flag_chunk_pointers(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    """Nullable EvaluationFlag.chunk_id is cleared for purged chunks while
    flag rows (and their partial/job history) are preserved."""
    _patch_chroma(monkeypatch, ephemeral_client)
    slm_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="slm",
        upload_root=upload_root,
    )
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    chunk_id = _seed_chunk(
        db_session, document_id=curriculum_id, source_type="curriculum"
    )
    other_chunk_id = _seed_chunk(
        db_session, document_id=slm_id, source_type="slm", text="other chunk"
    )
    job = _seed_job(
        db_session,
        document_id=slm_id,
        curriculum_id=curriculum_id,
        status=EvaluationStatus.COMPLETED.value,
        partial_without_curriculum=True,
        partial_reason="Curriculum evaluation flow retired",
    )
    # Full evaluation-flag rows: one pointing at a purged chunk, one not.
    agent_result = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        document_id=slm_id,
        agent_name="sme",
        model_name="mock-model",
        success=True,
        subtotal=3.5,
    )
    db_session.add(agent_result)
    db_session.flush()
    criterion_score = CriterionScore(
        criterion_score_id=uuid.uuid4(),
        evaluation_id=job.evaluation_id,
        agent_result_id=agent_result.agent_result_id,
        document_id=slm_id,
        criterion_id="c1",
        criterion_title="Criterion 1",
        score=3,
        justification="ok",
    )
    db_session.add(criterion_score)
    db_session.flush()
    db_session.add(
        EvaluationFlag(
            evaluation_id=job.evaluation_id,
            document_id=slm_id,
            agent_result_id=agent_result.agent_result_id,
            criterion_score_id=criterion_score.criterion_score_id,
            chunk_id=chunk_id,
            criterion_id="c1",
            score=3,
            reason="flagged",
        )
    )
    db_session.add(
        EvaluationFlag(
            evaluation_id=job.evaluation_id,
            document_id=slm_id,
            agent_result_id=agent_result.agent_result_id,
            criterion_score_id=criterion_score.criterion_score_id,
            chunk_id=other_chunk_id,
            criterion_id="c2",
            score=2,
            reason="not purged",
        )
    )
    db_session.commit()

    manifest = execute_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )

    assert manifest["results"]["flag_chunk_pointers_cleared"] == 1
    assert manifest["results"]["documents_deleted"] == 1
    db_session.expire_all()
    # Flag rows survive; only the pointer to the purged chunk is NULL.
    flags = (
        db_session.query(EvaluationFlag)
        .order_by(EvaluationFlag.criterion_id)
        .all()
    )
    assert len(flags) == 2
    by_criterion = {flag.criterion_id: flag for flag in flags}
    assert by_criterion["c1"].chunk_id is None
    assert by_criterion["c2"].chunk_id == other_chunk_id
    # Historical job state and partial flags preserved.
    refreshed = db_session.get(EvaluationJob, job.evaluation_id)
    assert refreshed is not None
    assert refreshed.curriculum_id is None
    assert refreshed.partial_without_curriculum is True
    assert refreshed.partial_reason == "Curriculum evaluation flow retired"


def test_execute_without_curricula_is_noop(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="syllabus",
        upload_root=upload_root,
    )

    manifest = execute_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )

    assert manifest["dry_run"] is False
    assert manifest["totals"]["documents"] == 0
    assert manifest["results"]["documents_deleted"] == 0
    assert db_session.query(Document).count() == 1


def test_execute_raises_unreachable_chroma(
    db_session, owner, upload_root, monkeypatch
):
    def _boom():
        raise RuntimeError("chroma down")

    monkeypatch.setattr(
        "server.modules.admin.curriculum_purge.get_chroma_client", _boom
    )
    _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )

    with pytest.raises(PurgeUnreachableError, match="chroma unreachable"):
        execute_curriculum_purge(db_session, upload_root=upload_root)


def test_manifest_is_content_free(
    db_session, owner, ephemeral_client, upload_root, monkeypatch
):
    _patch_chroma(monkeypatch, ephemeral_client)
    curriculum_id = _seed_document(
        db_session,
        owner_id=owner.user_id,
        source_type="curriculum",
        upload_root=upload_root,
    )
    _seed_chunk(db_session, document_id=curriculum_id, source_type="curriculum")
    _seed_vectors(
        ephemeral_client, document_id=curriculum_id, n=2, source_type="curriculum",
    )

    manifest = plan_curriculum_purge(
        db_session, upload_root=upload_root, chroma_client=ephemeral_client
    )
    serialized = json.dumps(manifest, default=str)

    assert CONTENT_MARKER not in serialized
    assert "vector text" not in serialized
    # Document titles are excluded from the manifest.
    assert f"curriculum {curriculum_id}" not in serialized


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_env(tmp_path, monkeypatch):
    """Standalone DB + ephemeral Chroma wired into the CLI module."""
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    ephemeral = chromadb.EphemeralClient()
    monkeypatch.setattr(
        "server.modules.admin.curriculum_purge.get_chroma_client",
        lambda: ephemeral,
    )
    monkeypatch.setattr(
        "server.scripts.purge_curriculum.get_session_factory",
        lambda: SessionLocal,
    )

    root = tmp_path / "uploads"
    root.mkdir()
    return engine, SessionLocal, ephemeral, root


def _cli_owner(session_local):
    with session_local() as session:
        user = create_user(
            session,
            name="CLI Owner",
            email="cli-owner@example.com",
            password="password123",
            role=UserRole.FACULTY,
        )
        session.commit()
        return user.user_id


def test_cli_dry_run_by_default(capsys, cli_env):
    from server.scripts.purge_curriculum import main

    engine, session_local, ephemeral, root = cli_env
    owner = _cli_owner(session_local)
    with session_local() as session:
        curriculum_id = _seed_document(
            session,
            owner_id=owner,
            source_type="curriculum",
            upload_root=root,
        )
        _seed_chunk(session, document_id=curriculum_id, source_type="curriculum")
        _seed_vectors(
            ephemeral, document_id=curriculum_id, n=1, source_type="curriculum"
        )

    exit_code = main(["--upload-root", str(root)])
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert manifest["dry_run"] is True
    assert manifest["totals"]["documents"] == 1
    assert manifest["curricula"][0]["document_id"] == str(curriculum_id)

    # Dry run changed nothing.
    with session_local() as session:
        assert session.get(Document, curriculum_id) is not None
        assert session.query(DocumentChunk).count() == 1
    assert (root / f"{curriculum_id}.pdf").exists()
    assert _vector_count(ephemeral, document_id=curriculum_id) == 1


def test_cli_execute_flag_applies_purge(capsys, cli_env):
    from server.scripts.purge_curriculum import main

    engine, session_local, ephemeral, root = cli_env
    owner = _cli_owner(session_local)
    with session_local() as session:
        slm_id = _seed_document(
            session,
            owner_id=owner,
            source_type="slm",
            upload_root=root,
        )
        curriculum_id = _seed_document(
            session,
            owner_id=owner,
            source_type="curriculum",
            upload_root=root,
        )
        _seed_chunk(session, document_id=curriculum_id, source_type="curriculum")
        _seed_vectors(
            ephemeral, document_id=curriculum_id, n=1, source_type="curriculum"
        )
        _seed_job(
            session,
            document_id=slm_id,
            curriculum_id=curriculum_id,
            status=EvaluationStatus.COMPLETED.value,
            partial_without_curriculum=True,
            partial_reason="Curriculum evaluation flow retired",
        )

    exit_code = main(["--upload-root", str(root), "--execute"])
    captured = capsys.readouterr()

    assert exit_code == 0
    manifest = json.loads(captured.out)
    assert manifest["dry_run"] is False
    assert manifest["results"]["documents_deleted"] == 1
    assert manifest["results"]["vectors_deleted"] == 1

    with session_local() as session:
        assert session.get(Document, curriculum_id) is None
        assert session.query(DocumentChunk).count() == 0
        job = session.query(EvaluationJob).one()
        assert job.curriculum_id is None
        assert job.partial_without_curriculum is True
        assert job.partial_reason == "Curriculum evaluation flow retired"
    assert not (root / f"{curriculum_id}.pdf").exists()
    assert _vector_count(ephemeral, document_id=curriculum_id) == 0


def test_cli_execute_blocked_exits_nonzero(capsys, cli_env):
    from server.scripts.purge_curriculum import main

    engine, session_local, ephemeral, root = cli_env
    owner = _cli_owner(session_local)
    with session_local() as session:
        slm_id = _seed_document(
            session,
            owner_id=owner,
            source_type="slm",
            upload_root=root,
        )
        curriculum_id = _seed_document(
            session,
            owner_id=owner,
            source_type="curriculum",
            upload_root=root,
        )
        _seed_job(
            session,
            document_id=slm_id,
            curriculum_id=curriculum_id,
            status=EvaluationStatus.SUBMITTED.value,
        )

    exit_code = main(["--upload-root", str(root), "--execute"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "purge failed" in captured.err
    assert "active evaluation job" in captured.err


def test_cli_execute_cleanup_failure_exits_nonzero(capsys, cli_env, monkeypatch):
    """A vector/file cleanup failure surfaces as a nonzero CLI exit."""
    from server.scripts.purge_curriculum import main

    engine, session_local, ephemeral, root = cli_env
    owner = _cli_owner(session_local)
    with session_local() as session:
        curriculum_id = _seed_document(
            session,
            owner_id=owner,
            source_type="curriculum",
            upload_root=root,
        )
        _seed_vectors(
            ephemeral, document_id=curriculum_id, n=1, source_type="curriculum",
        )

    def _fail(*args, **kwargs):
        raise PurgeExecutionError("vector cleanup failed: boom")

    monkeypatch.setattr(
        "server.modules.admin.curriculum_purge._delete_vectors_strict", _fail
    )

    exit_code = main(["--upload-root", str(root), "--execute"])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert "purge failed" in captured.err
    assert "vector cleanup failed" in captured.err
    # No success manifest was emitted on stdout.
    assert "dry_run" not in captured.out


def test_cli_execute_standalone_loads_all_orm_metadata(tmp_path):
    """Regression: the standalone CLI must register ALL ORM metadata —
    including the auth `users` table referenced by `documents.uploaded_by` —
    before the purge session commits. The bare CLI import chain
    (core.database + curriculum_purge models only) previously failed at
    commit with ``NoReferencedTableError``.

    Runs a fresh subprocess that imports ONLY the CLI module chain (no auth
    models, no app bootstrap) and routes the production session factory onto
    a real sqlite file DB, so the standalone import path is exercised end to
    end against a real commit.
    """
    from server.core.database import Base
    from server.db.metadata import import_model_modules
    from server.modules.auth.service import create_user
    from server.modules.documents.models import Document, DocumentChunk
    from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    import_model_modules()

    db_path = tmp_path / "purge_standalone.db"
    upload_root = tmp_path / "uploads"
    upload_root.mkdir()
    chroma_root = tmp_path / "chroma"
    chroma_root.mkdir()

    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    with SessionLocal() as session:
        user = create_user(
            session,
            name="Standalone Owner",
            email="standalone-owner@example.com",
            password="password123",
            role=UserRole.FACULTY,
        )
        session.commit()
        owner_id = user.user_id
        slm_id = uuid.uuid4()
        curriculum_id = uuid.uuid4()
        (upload_root / f"{curriculum_id}.pdf").write_bytes(
            b"%PDF-1.4 standalone"
        )
        session.add_all(
            [
                Document(
                    document_id=slm_id,
                    title="Standalone SLM",
                    source_type="slm",
                    file_path=f"uploads/{slm_id}.pdf",
                    uploaded_by=owner_id,
                    processing_status="PROCESSED",
                ),
                Document(
                    document_id=curriculum_id,
                    title="Standalone Curriculum",
                    source_type="curriculum",
                    file_path=f"uploads/{curriculum_id}.pdf",
                    uploaded_by=owner_id,
                    processing_status="PROCESSED",
                ),
                DocumentChunk(
                    chunk_id=uuid.uuid4(),
                    document_id=curriculum_id,
                    source_type="curriculum",
                    agent_domain="all",
                    page_number=1,
                    text="standalone chunk",
                    token_count=4,
                    is_ocr=False,
                    chroma_stored=True,
                ),
                EvaluationJob(
                    evaluation_id=uuid.uuid4(),
                    document_id=slm_id,
                    curriculum_id=curriculum_id,
                    status=EvaluationStatus.COMPLETED.value,
                    partial_without_curriculum=False,
                ),
            ]
        )
        session.commit()

    repo_root = str(Path(__file__).resolve().parents[3])
    wrapper = tmp_path / "standalone_cli_wrapper.py"
    wrapper.write_text(
        "\n".join(
            [
                "import os",
                "import sys",
                "from pathlib import Path",
                "",
                "sys.path.insert(0, os.environ['PURGE_TEST_ROOT'])",
                "",
                "import sqlalchemy",
                "import server.core.database as core_database",
                "",
                "def main() -> int:",
                "    engine = sqlalchemy.create_engine(",
                "        f\"sqlite:///{os.environ['PURGE_TEST_DB']}\"",
                "    )",
                "    core_database.get_engine = lambda: engine",
                "",
                "    # Standalone CLI import chain: this module does not import",
                "    # auth models; metadata registration happens inside main().",
                "    import server.scripts.purge_curriculum as cli",
                "",
                "    return cli.main([",
                "        '--execute',",
                "        '--upload-root',",
                "        os.environ['PURGE_TEST_UPLOAD_ROOT'],",
                "    ])",
                "",
                "if __name__ == '__main__':",
                "    sys.exit(main())",
                "",
            ]
        ),
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["PURGE_TEST_ROOT"] = repo_root
    env["PURGE_TEST_DB"] = str(db_path)
    env["PURGE_TEST_UPLOAD_ROOT"] = str(upload_root)
    env["CHROMA_PERSIST_DIRECTORY"] = str(chroma_root)
    # Pin settings so get_settings() (loaded via dotenv fallbacks) cannot
    # raise for CORS or prompt-budget cross-field validation.
    env["CORS_ORIGINS"] = ""
    env["AGENT_PROMPT_BUDGET_CHARS"] = "5000"
    env["AGENT_TOTAL_PROMPT_BUDGET_CHARS"] = "8000"

    result = subprocess.run(
        [sys.executable, str(wrapper)],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert result.returncode == 0, result.stderr

    manifest = json.loads(result.stdout)
    assert manifest["dry_run"] is False
    assert manifest["results"]["documents_deleted"] == 1
    assert manifest["results"]["chunks_deleted"] == 1
    assert manifest["results"]["jobs_curriculum_cleared"] == 1

    with SessionLocal() as session:
        assert session.get(Document, curriculum_id) is None
        job = session.query(EvaluationJob).one()
        assert job.curriculum_id is None
    assert not (upload_root / f"{curriculum_id}.pdf").exists()


def test_cli_writes_manifest_file(capsys, cli_env, tmp_path):
    from server.scripts.purge_curriculum import main

    engine, session_local, ephemeral, root = cli_env
    owner = _cli_owner(session_local)
    with session_local() as session:
        curriculum_id = _seed_document(
            session,
            owner_id=owner,
            source_type="curriculum",
            upload_root=root,
        )

    manifest_path = tmp_path / "purge-manifest.json"
    exit_code = main(
        ["--upload-root", str(root), "--manifest", str(manifest_path)]
    )

    assert exit_code == 0
    assert manifest_path.exists()
    written = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert written["dry_run"] is True
    assert written["curricula"][0]["document_id"] == str(curriculum_id)
    # stdout still carries the manifest.
    captured = capsys.readouterr()
    assert json.loads(captured.out)["dry_run"] is True


def test_cli_database_unconfigured_exits_two(capsys, monkeypatch):
    from server.scripts.purge_curriculum import main

    def _boom():
        raise RuntimeError("DATABASE_URL not configured")

    monkeypatch.setattr("server.scripts.purge_curriculum.get_session_factory", _boom)

    exit_code = main([])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "database unreachable" in captured.err
