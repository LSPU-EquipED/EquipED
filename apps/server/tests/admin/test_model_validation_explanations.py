"""Validation explanations expose stored content without changing scores."""

from __future__ import annotations

import json
import uuid

import pytest
from server.modules.admin.model_validation_service import get_model_validation_detail
from server.modules.admin.models import ModelValidation, ModelValidationCriterionScore
from server.modules.documents.models import Document
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.models import AgentGeneration, AgentResult, CriterionScore


def _seed(db, owner, *, status="ok", generation=True, reasoning="Captured reasoning"):
    doc = Document(
        title="Validation source",
        source_type="slm",
        file_path="uploads/source.pdf",
        uploaded_by=owner.user_id,
    )
    db.add(doc)
    db.flush()
    job = EvaluationJob(
        document_id=doc.document_id, status="COMPLETED", target_agent="sme"
    )
    db.add(job)
    db.flush()
    result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        agent_name="sme",
        model_name="gemma-test",
        envelope_status={"envelope_0": status},
    )
    db.add(result)
    db.flush()
    actual = 1 if status == "fallback" else 2
    stored = (
        "Evaluation unverified: grounding failed"
        if status == "fallback"
        else "Stored justification"
    )
    db.add(
        CriterionScore(
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_result_id=result.agent_result_id,
            criterion_id="OP-05",
            criterion_title="Enhancement Activities",
            score=actual,
            justification=stored,
            evidence=json.dumps(["Stored source quote"]),
        )
    )
    if generation:
        payload = {
            "summary": "Summary",
            "criterion_measurements": [
                {
                    "criterion_id": "OP-05",
                    "criterion_title": "Enhancement Activities",
                    "score": actual,
                    "evidence": "Captured source quote",
                    "reasoning": reasoning,
                }
            ],
        }
        db.add(
            AgentGeneration(
                evaluation_id=job.evaluation_id,
                document_id=doc.document_id,
                agent_result_id=result.agent_result_id,
                agent_id="sme",
                unit_key="envelope_0",
                criterion_ids=["OP-05"],
                prompt_text="Original prompt",
                response_text=json.dumps(payload),
                response_json=payload,
                response_contract_key="criterion_measurements.v1",
                response_contract_version=1,
                model_name="gemma-test",
                envelope_status=status,
                prompt_sha256="a" * 64,
                response_sha256="b" * 64,
            )
        )
    validation = ModelValidation(
        evaluation_id=job.evaluation_id, created_by=owner.user_id
    )
    db.add(validation)
    db.flush()
    db.add(
        ModelValidationCriterionScore(
            validation_id=validation.validation_id,
            agent_id="sme",
            criterion_id="OP-05",
            criterion_title="Enhancement Activities",
            expected_score=3,
            actual_score=actual,
            absolute_error=abs(actual - 3),
        )
    )
    db.commit()
    return validation


@pytest.mark.parametrize("status", ["ok", "repaired"])
def test_detail_returns_captured_explanation_without_changing_metrics(
    db_session, admin_user, status
):
    validation = _seed(db_session, admin_user, status=status)
    detail = get_model_validation_detail(validation.validation_id, db_session)
    score = detail.criterion_scores[0]
    assert score.actual_score == 2
    assert score.absolute_error == 1
    assert detail.absolute_error == 1
    assert score.explanation.reasoning == "Captured reasoning"
    assert score.explanation.evidence == ["Captured source quote"]
    assert score.explanation.status == status
    assert score.explanation.model_name == "gemma-test"


def test_fallback_never_presents_synthetic_reasoning_as_model_reasoning(
    db_session, admin_user
):
    validation = _seed(
        db_session, admin_user, status="fallback", reasoning="Synthetic fallback text"
    )
    detail = get_model_validation_detail(validation.validation_id, db_session)
    explanation = detail.criterion_scores[0].explanation
    assert explanation.status == "fallback"
    assert explanation.reasoning is None
    assert explanation.stored_justification == "Evaluation unverified: grounding failed"
    assert detail.criterion_scores[0].actual_score == 1
    assert detail.absolute_error == 2


@pytest.mark.parametrize("generation", [False, True])
def test_missing_model_reasoning_is_not_reconstructed_from_justification(
    db_session, admin_user, generation
):
    validation = _seed(db_session, admin_user, generation=generation, reasoning=None)
    explanation = (
        get_model_validation_detail(validation.validation_id, db_session)
        .criterion_scores[0]
        .explanation
    )
    assert explanation.reasoning is None
    assert explanation.stored_justification == "Stored justification"
    assert explanation.status == ("ok" if generation else "unavailable")
    assert explanation.evidence == (
        ["Captured source quote"] if generation else ["Stored source quote"]
    )


def test_detail_matches_agent_and_criterion_and_does_not_write(db_session, admin_user):
    validation = _seed(db_session, admin_user)
    job = db_session.get(EvaluationJob, validation.evaluation_id)
    other = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=job.document_id,
        agent_name="gad",
        model_name="other-model",
    )
    db_session.add(other)
    db_session.flush()
    db_session.add(
        CriterionScore(
            evaluation_id=job.evaluation_id,
            document_id=job.document_id,
            agent_result_id=other.agent_result_id,
            criterion_id="OP-05",
            criterion_title="Other agent",
            score=4,
            justification="Wrong agent justification",
            evidence="Wrong agent quote",
        )
    )
    db_session.commit()
    before = db_session.query(CriterionScore).count()
    detail = get_model_validation_detail(validation.validation_id, db_session)
    assert detail.criterion_scores[0].explanation.reasoning == "Captured reasoning"
    assert db_session.query(CriterionScore).count() == before
    assert not db_session.dirty and not db_session.new


def test_missing_validation_stays_not_found(db_session):
    assert get_model_validation_detail(uuid.uuid4(), db_session) is None
