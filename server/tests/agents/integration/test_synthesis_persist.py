"""Tests for synthesis persistence of agent outputs and flag creation."""

from __future__ import annotations

from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult, EvaluationFlag
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.agents.helpers import _seed_active_prompts


def test_persist_agent_outputs_creates_flags_for_low_scores(db_session) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    chunk_id = uuid4()
    evaluation_id = uuid4()
    prompt_version_id = uuid4()

    db_session.add(
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
    db_session.add(
        DocumentChunk(
            chunk_id=chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.add(
        EvaluationJob(
            evaluation_id=evaluation_id,
            document_id=document_id,
            syllabus_id=uuid4(),
            curriculum_id=uuid4(),
            status=EvaluationStatus.EVALUATING.value,
            submitted_by=owner_id,
        )
    )
    db_session.commit()

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="sme",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=1,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=1,
                        justification="needs work",
                        chunk_ids=(str(chunk_id),),
                        evidence=("evidence",),
                    ),
                    CriterionScore(
                        criterion_id="c2",
                        criterion_title="Criterion 2",
                        score=3,
                        justification="fine",
                    ),
                ),
                summary="summary",
                model_name="local-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    assert result_row.prompt_version_id == prompt_version_id
    assert db_session.query(EvaluationFlag).count() == 1
    flag = db_session.query(EvaluationFlag).one()
    assert flag.chunk_id == chunk_id
    assert flag.score == 1
    assert flag.criterion_id == "c1"


def test_persist_agent_outputs_ignores_invalid_and_missing_chunk_ids(
    db_session,
) -> None:
    owner_id = uuid4()
    document_id = uuid4()
    valid_chunk_id = uuid4()
    evaluation_id = uuid4()
    db_session.add(
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
    db_session.add(
        DocumentChunk(
            chunk_id=valid_chunk_id,
            document_id=document_id,
            source_type="slm",
            agent_domain="all",
            page_number=1,
            text="chunk text",
            token_count=2,
            is_ocr=False,
            chroma_stored=True,
        )
    )
    _seed_active_prompts(db_session)
    prompt_version_id = (
        db_session.query(PromptVersion).filter_by(agent_id="sme").one().version_id
    )
    db_session.commit()

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="sme",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=1,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=1,
                        justification="needs work",
                        chunk_ids=("not-a-uuid", str(uuid4()), str(valid_chunk_id)),
                        evidence=("evidence",),
                    ),
                ),
                summary="summary",
                model_name="local-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    assert result_row.prompt_version_id == prompt_version_id
    assert db_session.query(EvaluationFlag).count() == 1
    flag = db_session.query(EvaluationFlag).one()
    assert flag.chunk_id == valid_chunk_id
