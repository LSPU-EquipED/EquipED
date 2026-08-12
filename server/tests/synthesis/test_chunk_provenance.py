"""Persistence coverage for document-scoped evidence provenance."""

from __future__ import annotations

import json
import re
import uuid

from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import CriterionScore as StoredScore
from server.modules.synthesis.models import EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs
from sqlalchemy import event


def _fixture(db_session, user_id):
    document = Document(
        title="A", source_type="slm", file_path="a.pdf", uploaded_by=user_id
    )
    foreign = Document(
        title="B", source_type="slm", file_path="b.pdf", uploaded_by=user_id
    )
    db_session.add_all([document, foreign])
    db_session.flush()
    chunks = [
        DocumentChunk(
            document_id=document.document_id,
            source_type="slm",
            agent_domain="sme",
            text="A",
        ),
        DocumentChunk(
            document_id=foreign.document_id,
            source_type="slm",
            agent_domain="sme",
            text="B",
        ),
    ]
    db_session.add_all(chunks)
    job = EvaluationJob(document_id=document.document_id, status="EVALUATING")
    db_session.add(job)
    db_session.flush()
    return document, foreign, chunks, job


def _result(job, document, chunk_ids, score=2):
    return AgentEvaluationResult(
        agent_name="sme",
        evaluation_id=job.evaluation_id,
        document_id=document.document_id,
        subtotal=float(score),
        criterion_scores=(
            CriterionScore("c1", "Criterion", score, "reason", tuple(chunk_ids)),
        ),
        summary="summary",
        model_name="test",
        processing_seconds=0.1,
        token_count=1,
    )


def test_persists_only_owned_chunk_ids_and_flags(db_session, seeded_user):
    document, foreign, chunks, job = _fixture(db_session, seeded_user.user_id)
    unknown = uuid.uuid4()
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document.document_id,
        [
            _result(
                job,
                document,
                [chunks[0].chunk_id, chunks[1].chunk_id, unknown, "malformed"],
            ),
        ],
    )
    stored = db_session.query(StoredScore).one()
    assert json.loads(stored.chunk_ids) == [str(chunks[0].chunk_id)]
    assert [flag.chunk_id for flag in db_session.query(EvaluationFlag).all()] == [
        chunks[0].chunk_id
    ]
    assert all(
        flag.document_id == document.document_id
        for flag in db_session.query(EvaluationFlag)
    )
    assert foreign.document_id != document.document_id


def test_duplicate_valid_ids_are_stored_once(db_session, seeded_user):
    document, _, chunks, job = _fixture(db_session, seeded_user.user_id)
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document.document_id,
        [
            _result(
                job,
                document,
                [
                    str(chunks[0].chunk_id),
                    str(chunks[0].chunk_id),
                    str(chunks[1].chunk_id),
                ],
            ),
        ],
    )
    assert json.loads(db_session.query(StoredScore).first().chunk_ids) == [
        str(chunks[0].chunk_id)
    ]
    assert db_session.query(EvaluationFlag).count() == 1


def test_batch_validation_is_one_document_scoped_select(db_session, seeded_user):
    document, foreign, chunks, job = _fixture(db_session, seeded_user.user_id)
    statements = []

    def capture(_, __, statement, ___, ____, _____):
        if re.search(r"document_chunks", statement, re.I):
            statements.append(statement)

    event.listen(db_session.bind, "before_cursor_execute", capture)
    try:
        persist_agent_outputs(
            db_session,
            job.evaluation_id,
            document.document_id,
            [
                _result(job, document, [chunks[0].chunk_id]),
                _result(job, document, [chunks[1].chunk_id]),
            ],
        )
    finally:
        event.remove(db_session.bind, "before_cursor_execute", capture)
    assert len(statements) == 1
    assert re.search(r"document_id", statements[0], re.I)


def test_commit_false_and_ownership_callback(db_session, seeded_user):
    document, _, chunks, job = _fixture(db_session, seeded_user.user_id)
    calls = []
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        document.document_id,
        [_result(job, document, [chunks[0].chunk_id])],
        verify_ownership=lambda db: calls.append(db),
        commit=False,
    )
    assert len(calls) == 2
    assert db_session.query(StoredScore).count() == 1
    db_session.rollback()
    assert db_session.query(StoredScore).count() == 0
