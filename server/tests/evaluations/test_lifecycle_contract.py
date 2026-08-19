"""Decisive end-to-end lifecycle contract tests."""

from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

import pytest
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.agents.sme.oracle import registry
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.evaluations.orchestrator import _execute_claimed_evaluation
from server.modules.synthesis.models import MonitoringMatrix


def _job(db_session, *, partial: bool, curriculum: bool = False):
    owner = uuid4()
    document = uuid4()
    token = uuid4()
    db_session.add(
        Document(
            document_id=document,
            title="SLM",
            program="BSCS",
            source_type="slm",
            file_path=f"uploads/{document}.pdf",
            uploaded_by=owner,
            processing_status="PROCESSED",
            page_count=1,
            has_ocr_pages=False,
        )
    )
    db_session.add(
        DocumentChunk(
            chunk_id=uuid4(),
            document_id=document,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="evidence",
            token_count=1,
            is_ocr=False,
            chroma_stored=False,
        )
    )
    curriculum_id = None
    if curriculum:
        curriculum_id = uuid4()
        db_session.add(
            Document(
                document_id=curriculum_id,
                title="Curriculum",
                program="BSCS",
                source_type="curriculum",
                file_path=f"uploads/{curriculum_id}.pdf",
                uploaded_by=owner,
                processing_status="PROCESSED",
                page_count=1,
                has_ocr_pages=False,
            )
        )
    evaluation = uuid4()
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation,
            document_id=document,
            curriculum_id=curriculum_id,
            status=EvaluationStatus.PREPROCESSING.value,
            submitted_by=owner,
            admission_slot=1,
            execution_token=token,
            partial_without_curriculum=partial,
            partial_reason="test partial" if partial else None,
        )
    )
    db_session.commit()
    return evaluation, token


def _result(agent, evaluation_id, document_id, success=True):
    scores = (
        tuple(
            CriterionScore(code, code, 1, "evidence", ())
            for code in sorted(registry.REGISTERED_CODES)
        )
        if success
        else ()
    )
    return AgentEvaluationResult(
        agent_name=agent,
        evaluation_id=evaluation_id,
        document_id=document_id,
        subtotal=1 if success else 0,
        summary="ok",
        model_name=f"{agent}-test",
        processing_seconds=0,
        token_count=1,
        success=success,
        error_message=None if success else f"{agent} failed",
        criterion_scores=scores,
    )


def _run(db_session, monkeypatch, *, partial, agents, curriculum=False):
    evaluation, token = _job(db_session, partial=partial, curriculum=curriculum)
    job = db_session.get(EvaluationJob, evaluation)
    results = [
        _result(agent, evaluation, job.document_id, success)
        for agent, success in agents
    ]

    class FakeSupervisor:
        def __init__(self, *args, **kwargs):
            pass

        def run_evaluation(self, **kwargs):
            return SimpleNamespace(agent_results=list(results))

    monkeypatch.setattr(
        "server.modules.evaluations.orchestrator.Supervisor", FakeSupervisor
    )
    _execute_claimed_evaluation(evaluation, token, lambda: db_session)
    db_session.expire_all()
    return db_session.get(EvaluationJob, evaluation)


def test_full_intent_without_curriculum_fails(monkeypatch, db_session):
    job = _run(
        db_session,
        monkeypatch,
        partial=False,
        agents=[(a, True) for a in ("sme", "coordinator", "gad", "itso")],
    )
    assert job.status == EvaluationStatus.FAILED.value


def test_resumed_full_persistence_missing_coordinator_fails(monkeypatch, db_session):
    job = _run(
        db_session,
        monkeypatch,
        partial=False,
        agents=[("sme", True), ("gad", True), ("itso", True)],
    )
    assert job.status == EvaluationStatus.FAILED.value


def test_failed_coordinator_full_fails(monkeypatch, db_session):
    job = _run(
        db_session,
        monkeypatch,
        partial=False,
        agents=[("sme", True), ("coordinator", False), ("gad", True), ("itso", True)],
        curriculum=True,
    )
    assert job.status == EvaluationStatus.FAILED.value


@pytest.mark.parametrize("missing", ["sme", "gad", "itso"])
@pytest.mark.parametrize("failed", [False, True])
def test_explicit_partial_missing_or_failed_required_agent_fails(
    monkeypatch, db_session, missing, failed
):
    agents = [
        (a, not (a == missing and failed))
        for a in ("sme", "gad", "itso")
        if a != missing
    ]
    if failed:
        agents.append((missing, False))
    job = _run(db_session, monkeypatch, partial=True, agents=agents)
    assert job.status == EvaluationStatus.FAILED.value


def test_valid_explicit_partial_completes_partial(monkeypatch, db_session):
    job = _run(
        db_session,
        monkeypatch,
        partial=True,
        agents=[(a, True) for a in ("sme", "gad", "itso")],
    )
    assert job.status == EvaluationStatus.COMPLETED.value
    matrix = (
        db_session.query(MonitoringMatrix)
        .filter_by(evaluation_id=job.evaluation_id)
        .one()
    )
    assert matrix.evaluation_status == "COMPLETED_PARTIAL"


def test_valid_full_completes(monkeypatch, db_session):
    job = _run(
        db_session,
        monkeypatch,
        partial=False,
        curriculum=True,
        agents=[(a, True) for a in ("sme", "coordinator", "gad", "itso")],
    )
    assert job.status == EvaluationStatus.COMPLETED.value
