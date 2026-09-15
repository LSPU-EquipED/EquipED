"""Transactional Layer 3 persistence through the orchestrator seam."""

from __future__ import annotations

from uuid import uuid4

import pytest
from server.core.database import Base
from server.db.metadata import import_model_modules
from server.modules.agents.contracts import AgentEvaluationResult
from server.modules.auth.models import User, UserRole
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.exceptions import EvaluationExecutionOwnershipError
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import _persist_layer3_and_transition
from server.modules.synthesis.exceptions import EvaluationResultIntegrityError
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.models import CriterionScore as StoredScore
from server.tests.evaluations.snapshot_test_helpers import (
    make_agent_result,
    prepare_test_snapshots,
)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


def _factory():
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    import_model_modules()
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def _setup(factory):
    db = factory()
    owner_id, document_id, chunk_id, evaluation_id, token = (uuid4() for _ in range(5))
    db.add(
        User(
            user_id=owner_id,
            name="Owner",
            email=f"{owner_id}@example.test",
            role=UserRole.FACULTY,
            password_hash="x",
        )
    )
    db.add(
        Document(
            document_id=document_id,
            title="SLM",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document_id}.pdf",
            uploaded_by=owner_id,
            page_count=1,
            has_ocr_pages=False,
            processing_status="PROCESSED",
        )
    )
    db.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="evidence",
            token_count=1,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    db.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
            admission_slot=1,
            execution_token=token,
        )
    )
    db.flush()
    prepare_test_snapshots(db, evaluation_id, partial_without_curriculum=False)
    db.commit()
    return db, (owner_id, document_id, chunk_id, evaluation_id, token)


def _results(ids):
    _, document_id, chunk_id, evaluation_id, _ = ids
    return [
        make_agent_result(
            "sme",
            evaluation_id,
            document_id,
            default_score=1,
            chunk_ids_by_criterion={"A-01": (str(chunk_id),)},
            evidence_by_criterion={"A-01": ("evidence",)},
        ),
        make_agent_result("coordinator", evaluation_id, document_id, default_score=1),
        make_agent_result("gad", evaluation_id, document_id, default_score=1),
        make_agent_result("itso", evaluation_id, document_id, default_score=1),
    ]


def test_layer3_commit_failure_rolls_back_all_rows():
    factory = _factory()
    writer, ids = _setup(factory)
    observer = factory()
    calls = 0

    def fail_commit():
        nonlocal calls
        calls += 1
        writer.flush()
        assert writer.query(AgentResult).count() == 4
        assert writer.query(StoredScore).count() == 30
        assert (
            writer.query(EvaluationFlag)
            .filter(EvaluationFlag.chunk_id.isnot(None))
            .count()
            == 1
        )
        assert writer.query(EvaluationFlag).count() == 6
        assert (
            writer.get(EvaluationJob, ids[3]).status
            == EvaluationStatus.SYNTHESIZING.value
        )
        raise RuntimeError("injected commit failure")

    writer.commit = fail_commit
    with pytest.raises(RuntimeError):
        _persist_layer3_and_transition(writer, ids[3], ids[1], _results(ids), ids[4])
    assert calls == 1
    observer.expire_all()
    assert (
        observer.get(EvaluationJob, ids[3]).status == EvaluationStatus.EVALUATING.value
    )
    assert observer.query(AgentResult).count() == 0
    assert observer.query(StoredScore).count() == 0
    assert observer.query(EvaluationFlag).count() == 0


def test_layer3_success_persists_rows_and_transitions():
    factory = _factory()
    writer, ids = _setup(factory)
    calls = 0
    original_commit = writer.commit

    def counted_commit():
        nonlocal calls
        calls += 1
        original_commit()

    writer.commit = counted_commit
    _persist_layer3_and_transition(writer, ids[3], ids[1], _results(ids), ids[4])
    observer = factory()
    assert calls == 1
    assert (
        observer.get(EvaluationJob, ids[3]).status
        == EvaluationStatus.SYNTHESIZING.value
    )
    persisted_results = observer.query(AgentResult).all()
    assert len(persisted_results) == 4
    for r in persisted_results:
        assert r.form_snapshot_id is not None
    assert observer.query(StoredScore).count() == 30
    assert (
        observer.query(EvaluationFlag)
        .filter(EvaluationFlag.chunk_id.isnot(None))
        .one()
        .chunk_id
        == ids[2]
    )


def test_layer3_wrong_token_does_not_persist():
    factory = _factory()
    db, ids = _setup(factory)
    with pytest.raises(EvaluationExecutionOwnershipError):
        _persist_layer3_and_transition(db, ids[3], ids[1], _results(ids), uuid4())
    observer = factory()
    assert (
        observer.get(EvaluationJob, ids[3]).status == EvaluationStatus.EVALUATING.value
    )
    assert observer.query(AgentResult).count() == 0
    assert observer.query(StoredScore).count() == 0
    assert observer.query(EvaluationFlag).count() == 0


def test_layer3_integrity_failure_rolls_back_all_rows():
    factory = _factory()
    db, ids = _setup(factory)
    # Result missing required criteria
    bad_results = [
        AgentEvaluationResult(
            agent_name="sme",
            evaluation_id=ids[3],
            document_id=ids[1],
            subtotal=1.0,
            criterion_scores=(),
            summary="",
            model_name="test",
            processing_seconds=1.0,
            token_count=10,
            success=True,
        ),
        make_agent_result("coordinator", ids[3], ids[1]),
        make_agent_result("gad", ids[3], ids[1]),
        make_agent_result("itso", ids[3], ids[1]),
    ]
    with pytest.raises(EvaluationResultIntegrityError):
        _persist_layer3_and_transition(db, ids[3], ids[1], bad_results, ids[4])

    observer = factory()
    assert (
        observer.get(EvaluationJob, ids[3]).status == EvaluationStatus.EVALUATING.value
    )
    assert observer.query(AgentResult).count() == 0
    assert observer.query(StoredScore).count() == 0
    assert observer.query(EvaluationFlag).count() == 0
