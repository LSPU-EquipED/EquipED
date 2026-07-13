"""Admin model-validation workflow tests."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from server.modules.admin.models import ModelValidation, ModelValidationCriterionScore
from server.modules.admin.service import (
    assess_model_validation_toxicity,
    sync_model_validation_criterion_results,
)
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.rubrics.models import RubricCriterion, RubricDomain, RubricSet
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.tests.admin.conftest import _auth


class _ContextualToxicityClient:
    model = "contextual-toxicity-test-model"

    def __init__(self) -> None:
        self.prompt = ""

    def generate(self, prompt: str, **_: object) -> str:
        self.prompt = prompt
        return (
            '{"toxicity_score": 0.2, "label": "low", '
            '"explanation": "Mildly insulting phrasing was detected."}'
        )


class _InvalidToxicityClient:
    model = "invalid-test-model"

    def generate(self, prompt: str, **_: object) -> str:
        return "not valid JSON"


def _seed_document(db_session, *, owner_id, source_type: str, chroma_stored: bool):
    document = Document(
        document_id=uuid.uuid4(),
        title=f"Validation {source_type}",
        program="BSCS",
        source_type=source_type,
        file_path=f"uploads/{uuid.uuid4()}.pdf",
        uploaded_by=owner_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    db_session.add(document)
    db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=document.document_id,
            source_type=source_type,
            agent_domain="all",
            page_number=1,
            text="Benchmark content",
            token_count=2,
            chroma_stored=chroma_stored,
        )
    )
    db_session.commit()
    return document


def _seed_active_rubrics(db_session) -> list[dict[str, object]]:
    expected_scores: list[dict[str, object]] = []
    scores = {"sme": 3, "coordinator": 4, "gad": 2, "itso": 1}
    codes = {"sme": "SME-1", "coordinator": "COORD-1", "gad": "GAD-1", "itso": "ITSO-1"}
    for agent_id in ("sme", "coordinator", "gad", "itso"):
        rubric_set = RubricSet(
            agent_id=agent_id,
            name=f"{agent_id} validation rubric",
            version_number=1,
            status="active",
        )
        db_session.add(rubric_set)
        db_session.flush()
        domain = RubricDomain(
            rubric_set_id=rubric_set.rubric_set_id,
            code=f"{agent_id}-domain",
            title=f"{agent_id} domain",
            display_order=1,
        )
        db_session.add(domain)
        db_session.flush()
        db_session.add(
            RubricCriterion(
                rubric_domain_id=domain.rubric_domain_id,
                criterion_code=codes[agent_id],
                title=f"{agent_id} criterion",
                description=f"Expected {agent_id} behavior",
                display_order=1,
            )
        )
        expected_scores.append(
            {
                "agent_id": agent_id,
                "criterion_id": codes[agent_id],
                "expected_score": scores[agent_id],
            }
        )
    db_session.commit()
    return expected_scores


def test_model_validation_requires_admin(
    client: TestClient, auth_cookies_faculty
) -> None:
    _auth(client, auth_cookies_faculty)
    response = client.get("/api/v1/admin/model-validations")
    assert response.status_code == 403


def test_admin_creates_validation_without_leaking_expected_score_into_job(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    expected_scores = _seed_active_rubrics(db_session)
    slm = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="slm",
        chroma_stored=False,
    )
    curriculum = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="curriculum",
        chroma_stored=True,
    )
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    criteria_response = client.get("/api/v1/admin/model-validations/criteria")
    assert criteria_response.status_code == 200
    assert criteria_response.json()["total_criteria"] == 4

    incomplete_response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "curriculum_id": str(curriculum.document_id),
            "expected_scores": expected_scores[:-1],
        },
    )
    assert incomplete_response.status_code == 422

    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "curriculum_id": str(curriculum.document_id),
            "expected_scores": expected_scores,
        },
    )

    assert response.status_code == 202
    payload = response.json()
    assert payload["partial_without_curriculum"] is False
    assert len(payload["criterion_scores"]) == 4
    assert all(item["actual_score"] is None for item in payload["criterion_scores"])
    job = db_session.get(EvaluationJob, uuid.UUID(payload["evaluation_id"]))
    validation = db_session.get(ModelValidation, uuid.UUID(payload["validation_id"]))
    assert job is not None
    assert validation is not None
    assert not hasattr(validation, "expected_score")
    stored_scores = (
        db_session.query(ModelValidationCriterionScore)
        .filter_by(validation_id=validation.validation_id)
        .all()
    )
    assert len(stored_scores) == 4

    job.status = "COMPLETED"
    job.completed_at = job.submitted_at + timedelta(seconds=5)
    agent_result = AgentResult(
        evaluation_id=job.evaluation_id,
        document_id=slm.document_id,
        agent_name="sme",
        subtotal=4.0,
        processing_seconds=4.0,
        token_count=20,
        model_name="test-model",
        summary="The review is stupid.",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()
    db_session.add(
        CriterionScore(
            agent_result_id=agent_result.agent_result_id,
            evaluation_id=job.evaluation_id,
            document_id=slm.document_id,
            criterion_id="SME-1",
            criterion_title="Quality",
            score=4,
            justification="The generated review is otherwise useful.",
        )
    )
    db_session.commit()
    sync_model_validation_criterion_results(job.evaluation_id, db_session)
    toxicity_client = _ContextualToxicityClient()
    assess_model_validation_toxicity(
        job.evaluation_id,
        db_session,
        llm_client=toxicity_client,
    )
    assert "The review is stupid." in toxicity_client.prompt

    list_response = client.get("/api/v1/admin/model-validations")
    assert list_response.status_code == 200
    listed = list_response.json()["items"][0]
    sme_score = next(
        item for item in listed["criterion_scores"] if item["agent_id"] == "sme"
    )
    assert sme_score["expected_score"] == 3
    assert sme_score["actual_score"] == 4
    assert sme_score["absolute_error"] == 1.0
    assert listed["absolute_error"] == 1.0
    assert listed["latency_seconds"] == 5.0
    assert listed["score_perplexity"] > 1.0
    assert listed["toxicity_score"] == 0.2
    assert listed["toxicity_label"] == "low"
    assert listed["toxicity_model"] == "contextual-toxicity-test-model"
    assert "Mildly insulting" in listed["toxicity_explanation"]
    assert listed["toxicity_error"] is None

    metrics_response = client.get("/api/v1/admin/model-validations/metrics")
    assert metrics_response.status_code == 200
    metrics = metrics_response.json()
    assert metrics["completed_runs"] == 1
    assert metrics["mean_latency_seconds"] == 5.0
    assert metrics["score_perplexity"] == 2.7183
    assert metrics["mean_toxicity_score"] == 0.2
    assert metrics["confusion_matrix"][2][3] == 1

    failed_assessment = assess_model_validation_toxicity(
        job.evaluation_id,
        db_session,
        llm_client=_InvalidToxicityClient(),
    )
    assert failed_assessment is not None
    assert failed_assessment.toxicity_score is None
    assert "JSONDecodeError" in failed_assessment.toxicity_error


def test_model_validation_rejects_score_outside_institutional_scale(
    client: TestClient, auth_cookies_admin
) -> None:
    _auth(client, auth_cookies_admin)
    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(uuid.uuid4()),
            "expected_scores": [
                {
                    "agent_id": "sme",
                    "criterion_id": "SME-1",
                    "expected_score": 5,
                }
            ],
        },
    )
    assert response.status_code == 422
