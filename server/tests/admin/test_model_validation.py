"""Admin model-validation workflow tests."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi.testclient import TestClient
from server.modules.admin.model_validation_service import (
    assess_model_validation_toxicity,
    sync_model_validation_criterion_results,
)
from server.modules.admin.models import ModelValidation, ModelValidationCriterionScore
from server.modules.admin.schemas import ModelValidationMetricsResponse
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


def _seed_document(
    db_session,
    *,
    owner_id,
    source_type: str,
    chroma_stored: bool,
    program: str = "BSCS",
):
    document = Document(
        document_id=uuid.uuid4(),
        title=f"Validation {source_type}",
        program=program,
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
    # Coordinator is excluded from curriculum-retired validation runs, so only
    # the active evaluator agents (SME, GAD, ITSO) are benchmarked.
    scores = {"sme": 3, "gad": 2, "itso": 1}
    codes = {"sme": "SME-1", "gad": "GAD-1", "itso": "ITSO-1"}
    for agent_id in ("sme", "gad", "itso"):
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


def test_metrics_schema_tolerates_missing_agent_breakdown() -> None:
    """A staggered dev reload must not turn the metrics endpoint into a 500."""

    response = ModelValidationMetricsResponse(
        completed_runs=0,
        class_labels=["1", "2", "3", "4"],
        confusion_matrix=[[0, 0, 0, 0] for _ in range(4)],
    )

    assert response.agent_confusion_matrices == {}


def _setup_validation(
    db_session, admin_user, expected_scores=None, program: str = "BSCS"
):
    """Shared helper: seed rubrics + docs + create validation, return key objects."""
    if expected_scores is None:
        expected_scores = _seed_active_rubrics(db_session)
    slm = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="slm",
        chroma_stored=False,
        program=program,
    )
    return expected_scores, slm


def test_admin_creates_validation_without_leaking_expected_score_into_job(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    original_flush = db_session.flush
    flush_states: list[tuple[bool, bool]] = []

    def tracked_flush(*args, **kwargs):
        flush_states.append(
            (
                any(isinstance(item, EvaluationJob) for item in db_session.new),
                any(isinstance(item, ModelValidation) for item in db_session.new),
            )
        )
        return original_flush(*args, **kwargs)

    monkeypatch.setattr(db_session, "flush", tracked_flush)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    criteria_response = client.get("/api/v1/admin/model-validations/criteria")
    assert criteria_response.status_code == 200
    assert criteria_response.json()["total_criteria"] == 3

    incomplete_response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores[:-1],
        },
    )
    assert incomplete_response.status_code == 422

    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )

    assert response.status_code == 202
    assert (True, False) in flush_states
    payload = response.json()
    assert payload["partial_without_curriculum"] is True
    assert len(payload["criterion_scores"]) == 3
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
    assert len(stored_scores) == 3

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
    assert metrics["agent_confusion_matrices"]["sme"][2][3] == 1
    assert metrics["agent_confusion_matrices"]["coordinator"] == [
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
    ]

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


# ---------------------------------------------------------------------------
# Test 5: Shared-admin oversight — cross-admin access + faculty denial
# ---------------------------------------------------------------------------


def test_admin_can_detail_validation_record(
    client: TestClient,
    auth_cookies_admin,
    auth_cookies_faculty,
    admin_user,
    faculty_user,
    db_session,
    monkeypatch,
) -> None:
    """Admin can retrieve a single validation record by ID; faculty cannot."""
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)
    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert create_resp.status_code == 202
    validation_id = create_resp.json()["validation_id"]

    # Admin can detail
    detail_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}"
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["validation_id"] == validation_id

    # Faculty blocked
    _auth(client, auth_cookies_faculty)
    faculty_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}"
    )
    assert faculty_resp.status_code == 403


def test_admin_can_view_linked_evaluation(
    client: TestClient,
    auth_cookies_admin,
    auth_cookies_faculty,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Admin can open the linked evaluation through the admin-authorized path."""
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)
    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert create_resp.status_code == 202
    validation_id = create_resp.json()["validation_id"]

    eval_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}/evaluation"
    )
    assert eval_resp.status_code == 200
    data = eval_resp.json()
    assert data["evaluation_id"] == create_resp.json()["evaluation_id"]
    assert "document_id" in data
    assert "status" in data

    # Faculty blocked
    _auth(client, auth_cookies_faculty)
    faculty_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}/evaluation"
    )
    assert faculty_resp.status_code == 403


def test_faculty_cannot_list_validations(
    client: TestClient, auth_cookies_faculty
) -> None:
    """Faculty get 403 on every model-validation endpoint."""
    _auth(client, auth_cookies_faculty)
    assert client.get("/api/v1/admin/model-validations").status_code == 403
    assert client.get("/api/v1/admin/model-validations/metrics").status_code == 403
    assert client.get("/api/v1/admin/model-validations/criteria").status_code == 403


# ---------------------------------------------------------------------------
# Test 6: Curriculum-retired partial validation is always enforced
# ---------------------------------------------------------------------------


def test_validation_always_runs_partial_without_curriculum(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Every new validation run is a curriculum-retired partial evaluation.

    The service forces partial_without_curriculum=True and curriculum_id=None
    even when the request omits them or supplies a curriculum reference.
    """
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    # Omitting partial_without_curriculum still produces a partial job.
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 202
    assert resp.json()["partial_without_curriculum"] is True

    job = db_session.get(EvaluationJob, uuid.UUID(resp.json()["evaluation_id"]))
    assert job is not None
    assert job.curriculum_id is None
    assert job.partial_without_curriculum is True
    assert job.confirmed_program == "BSCS"


def test_validation_explicit_partial_without_curriculum(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Explicit partial_without_curriculum=True is accepted."""
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 202
    assert resp.json()["partial_without_curriculum"] is True


# ---------------------------------------------------------------------------
# Test 6b: Coordinator expected scores are retired for Model Validation
# ---------------------------------------------------------------------------


def test_validation_rejects_coordinator_expected_scores(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Model Validation no longer accepts Program Coordinator expected scores."""

    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    coordinator_scores = expected_scores + [
        {
            "agent_id": "coordinator",
            "criterion_id": "COORD-1",
            "expected_score": 4,
        }
    ]

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": coordinator_scores,
        },
    )
    assert resp.status_code == 422
    assert "coordinator" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Test 4: Toxicity disabled behavior (no external call, null persisted)
# ---------------------------------------------------------------------------


def test_toxicity_disabled_stores_none_with_message(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """When toxicity_assessment_enabled is False, toxicity fields stay null."""
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)
    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert create_resp.status_code == 202
    validation_id = create_resp.json()["validation_id"]
    validation = db_session.get(ModelValidation, uuid.UUID(validation_id))

    # Call toxicity assessment without an explicit client (no monkeypatch
    # of settings so toxicity_assessment_enabled defaults to False).
    assess_model_validation_toxicity(
        uuid.UUID(create_resp.json()["evaluation_id"]), db_session
    )
    db_session.refresh(validation)
    assert validation.toxicity_score is None
    assert validation.toxicity_label is None
    assert validation.toxicity_error is not None
    assert "not enabled" in validation.toxicity_error.lower()


# ---------------------------------------------------------------------------
# Test 2: Atomic creation — failure before commit rolls back everything
# ---------------------------------------------------------------------------


def test_validation_atomic_creation_rolls_back_on_failure(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """If validation creation fails, no orphan evaluation job remains."""
    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    # Trigger a failure by providing a non-existent document_id.
    # The evaluation service masks the missing SLM as a 404; this should
    # prevent the whole transaction from committing.
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(uuid.uuid4()),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 404  # SLM document not found

    # No evaluation job should exist from the failed attempt.
    eval_count = db_session.query(EvaluationJob).count()
    assert eval_count == 0


# ---------------------------------------------------------------------------
# Test 5b: Cross-admin access — second admin can view first admin's validation
# ---------------------------------------------------------------------------


def test_cross_admin_access(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
    settings,
) -> None:
    """A second admin can view a validation created by the first admin."""
    from server.modules.auth.models import UserRole
    from server.modules.auth.service import create_user

    create_user(
        db_session,
        name="Second Admin",
        email="admin2@example.com",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )

    # First admin creates the validation
    _auth(client, auth_cookies_admin)
    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert create_resp.status_code == 202
    created_eval_id = create_resp.json()["evaluation_id"]

    # Login as second admin
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin2@example.com", "password": "password123"},
    )
    assert login_resp.status_code == 200
    client.cookies.update(dict(login_resp.cookies))

    # Second admin can list first admin's validation
    list_resp = client.get("/api/v1/admin/model-validations")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Second admin can view the linked evaluation detail
    validation_id = create_resp.json()["validation_id"]
    detail_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}"
    )
    assert detail_resp.status_code == 200
    assert detail_resp.json()["evaluation_id"] == created_eval_id

    eval_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}/evaluation"
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["evaluation_id"] == created_eval_id


# ---------------------------------------------------------------------------
# Regression: summary aggregation with zero matched pairs
# ---------------------------------------------------------------------------


def test_metrics_includes_completed_run_with_zero_matched_pairs(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """All COMPLETED runs count toward run-level totals even when they have
    zero synchronized criterion pairs.  Criterion-pair-dependent metrics
    use only matched pairs.
    """
    monkeypatch.setattr(
        "server.modules.admin.router.run_evaluation_job", lambda _evaluation_id: None
    )
    _auth(client, auth_cookies_admin)

    # ── Seed rubrics once, create two SLM documents ─────────────────────
    expected_scores = _seed_active_rubrics(db_session)
    slm1 = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="slm",
        chroma_stored=False,
    )
    slm2 = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="slm",
        chroma_stored=False,
    )

    # ── Validation 1: matched run (sync SME criterion) ──────────────────
    resp1 = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm1.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp1.status_code == 202
    data1 = resp1.json()
    eval_id1 = uuid.UUID(data1["evaluation_id"])

    job1 = db_session.get(EvaluationJob, eval_id1)
    job1.status = "COMPLETED"
    job1.completed_at = job1.submitted_at + timedelta(seconds=10)
    agent_result = AgentResult(
        evaluation_id=eval_id1,
        document_id=slm1.document_id,
        agent_name="sme",
        subtotal=4.0,
        processing_seconds=4.0,
        token_count=20,
        model_name="test-model",
        summary="The review is acceptable.",
        success=True,
    )
    db_session.add(agent_result)
    db_session.flush()
    db_session.add(
        CriterionScore(
            agent_result_id=agent_result.agent_result_id,
            evaluation_id=eval_id1,
            document_id=slm1.document_id,
            criterion_id="SME-1",
            criterion_title="Quality",
            score=4,
            justification="Meets expectations.",
        )
    )
    db_session.commit()
    sync_model_validation_criterion_results(eval_id1, db_session)

    # Set toxicity on the matched run
    assess_model_validation_toxicity(
        eval_id1,
        db_session,
        llm_client=_ContextualToxicityClient(),
    )

    # ── Validation 2: COMPLETED, zero matched pairs (no sync) ──────────
    resp2 = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm2.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp2.status_code == 202
    data2 = resp2.json()
    eval_id2 = uuid.UUID(data2["evaluation_id"])

    job2 = db_session.get(EvaluationJob, eval_id2)
    job2.status = "COMPLETED"
    job2.completed_at = job2.submitted_at + timedelta(seconds=30)
    db_session.commit()

    # ── Verify metrics aggregation ──────────────────────────────────────
    metrics_resp = client.get("/api/v1/admin/model-validations/metrics")
    assert metrics_resp.status_code == 200
    metrics = metrics_resp.json()

    # Run-level totals include BOTH completed validations
    assert metrics["completed_runs"] == 2, (
        f"Expected 2 completed runs, got {metrics['completed_runs']}"
    )
    assert metrics["mean_latency_seconds"] == 20.0, (
        f"Expected latency (10+30)/2=20.0, got {metrics['mean_latency_seconds']}"
    )
    assert metrics["mean_toxicity_score"] == 0.2, (
        f"Expected toxicity 0.2 (only matched run assessed), "
        f"got {metrics['mean_toxicity_score']}"
    )

    # Criterion-pair-dependent metrics from the matched run only
    assert metrics["mean_absolute_error"] == 1.0, (
        f"Expected MAE 1.0 (only sme matched), got {metrics['mean_absolute_error']}"
    )
    assert metrics["score_perplexity"] == 2.7183, (
        f"Expected perplexity exp(1.0)=2.7183, got {metrics['score_perplexity']}"
    )
    assert metrics["confusion_matrix"][2][3] == 1, (
        f"Expected sme expected=3→actual=4 at [2][3]=1, "
        f"got {metrics['confusion_matrix']}"
    )
    assert metrics["agent_confusion_matrices"]["sme"][2][3] == 1
    # Other agents have zero matched pairs
    for agent in ("coordinator", "gad", "itso"):
        assert metrics["agent_confusion_matrices"][agent] == [
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
            [0, 0, 0, 0],
        ], f"Agent {agent} should have empty matrix"
