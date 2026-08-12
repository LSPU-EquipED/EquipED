"""Tests for bounded provenance persistence and fallback attribution (4.4)."""

from __future__ import annotations

from uuid import uuid4

from server.modules.admin.models import PromptVersion
from server.modules.agents.contracts import AgentEvaluationResult, CriterionScore
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.synthesis.models import AgentResult
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.agents.helpers import _seed_active_prompts

# ------------------------------------------------------------------
# Phase-1 + phase-2 provenance persistence
# ------------------------------------------------------------------


def test_provenance_persisted_with_agent_result(db_session) -> None:
    """Provenance dict should be persisted in the agent_results table."""
    owner_id = uuid4()
    document_id = uuid4()
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

    provenance: dict = {
        "precheck_version": "1",
        "precheck_result_hash": "abc123",
        "bibliography_found": True,
        "reference_count": 5,
        "intext_citation_count": 12,
        "doi_count": 3,
        "coverage_ratio": 0.5,
        "chunk_ids_ordered": ["c1", "c2", "c3"],
        "requested_model": "test-model",
        "actual_model": "test-model",
        "requested_temperature": 0.0,
        "fallback_occurred": False,
        "repair_occurred": False,
        "prompt_trimmed": False,
        "reference_context_dropped": 0,
        "summary_requested_model": "summary-model",
        "summary_actual_model": "s" * 300,
        "api_key": "secret-token-value",
    }

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=3.0,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=3,
                        justification="adequate",
                    ),
                ),
                summary="summary",
                model_name="test-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
                provenance=provenance,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    db_session.expire_all()
    result_row = db_session.get(AgentResult, result_row.agent_result_id)
    assert result_row.provenance is not None
    assert result_row.provenance["precheck_version"] == "1"
    assert result_row.provenance["bibliography_found"] is True
    assert result_row.provenance["requested_model"] == "test-model"
    assert result_row.provenance["actual_model"] == "test-model"
    assert result_row.provenance["summary_requested_model"] == "summary-model"
    assert result_row.provenance["summary_actual_model"] == "s" * 200
    assert "api_key" not in result_row.provenance
    assert "secret-token-value" not in str(result_row.provenance)


def test_provenance_fallback_attribution(db_session) -> None:
    """When fallback occurs, provenance should record both requested
    and actual model."""
    owner_id = uuid4()
    document_id = uuid4()
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

    provenance: dict = {
        "requested_model": "requested-model-v2",
        "actual_model": "fallback-model-v1",
        "fallback_occurred": True,
        "repair_occurred": False,
    }

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=2.5,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=2,
                        justification="needs improvement",
                    ),
                ),
                summary="summary",
                model_name="fallback-model-v1",
                processing_seconds=0.2,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
                provenance=provenance,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    assert result_row.provenance is not None
    assert result_row.provenance["requested_model"] == "requested-model-v2"
    assert result_row.provenance["actual_model"] == "fallback-model-v1"
    assert result_row.provenance["fallback_occurred"] is True
    # The model_name on the result should be the actual served model
    assert result_row.model_name == "fallback-model-v1"


def test_provenance_excludes_raw_text(db_session) -> None:
    """Provenance must NOT contain raw prompt text, raw SLM text,
    full chunk text, credentials, or external payloads."""
    owner_id = uuid4()
    document_id = uuid4()
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

    sensitive_provenance: dict = {
        "precheck_version": "1",
        "chunk_ids_ordered": ["c1"],
    }

    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=3.0,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=3,
                        justification="ok",
                    ),
                ),
                summary="summary",
                model_name="test-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
                provenance=sensitive_provenance,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    prov = result_row.provenance or {}
    prov_str = str(prov)

    # Provenance should contain only identifiers, counts, flags, hashes
    assert "precheck_version" in prov
    assert prov["precheck_version"] == "1"
    # Ensure no raw text fields snuck in
    for sensitive_key in [
        "prompt_text",
        "slm_text",
        "chunk_text",
        "raw_prompt",
        "credentials",
        "api_key",
    ]:
        assert sensitive_key not in prov_str


def test_historical_result_without_provenance_graceful(db_session) -> None:
    """Historical results with no provenance should return None gracefully."""
    owner_id = uuid4()
    document_id = uuid4()
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

    # Persist an AgentEvaluationResult WITHOUT provenance (historical)
    persist_agent_outputs(
        db_session,
        evaluation_id,
        document_id,
        [
            AgentEvaluationResult(
                agent_name="itso",
                evaluation_id=evaluation_id,
                document_id=document_id,
                subtotal=3.0,
                criterion_scores=(
                    CriterionScore(
                        criterion_id="c1",
                        criterion_title="Criterion 1",
                        score=3,
                        justification="ok",
                    ),
                ),
                summary="summary",
                model_name="test-model",
                processing_seconds=0.1,
                token_count=10,
                raw_response="{}",
                prompt_version_id=prompt_version_id,
                provenance=None,
            )
        ],
    )

    result_row = db_session.query(AgentResult).one()
    # Historical rows should have provenance=None
    assert result_row.provenance is None
