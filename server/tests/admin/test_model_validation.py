"""Admin model-validation workflow tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from server.modules.admin.model_validation_service import (
    assess_model_validation_toxicity,
    sync_model_validation_criterion_results,
)
from server.modules.admin.models import ModelValidation, ModelValidationCriterionScore
from server.modules.admin.schemas import ModelValidationMetricsResponse
from server.modules.documents.models import Document, DocumentChunk
from server.modules.evaluations.models import EvaluationJob
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.tests.admin.conftest import _auth


@pytest.fixture(autouse=True)
def _model_validation_readiness(monkeypatch):
    monkeypatch.setattr(
        "server.modules.admin.router.probe_local_model_readiness", lambda: None
    )
    monkeypatch.setattr(
        "server.modules.admin.router.admission_schema_ready", lambda db: True
    )


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


def _seed_active_rubrics(
    db_session, *, include_coordinator: bool = False
) -> list[dict[str, object]]:
    expected_scores: list[dict[str, object]] = []
    target_agents = (
        ("sme", "gad", "itso", "coordinator")
        if include_coordinator
        else ("sme", "gad", "itso")
    )
    scores = {"sme": 3, "gad": 2, "itso": 1, "coordinator": 4}
    codes = {
        "sme": "SME-1",
        "gad": "GAD-1",
        "itso": "ITSO-1",
    }
    configs = {
        "sme": {
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 3,
            "threshold_3": 2,
            "threshold_2": 1,
        },
        "gad": {
            "strategy": "count_band",
            "mode": "maximum_count",
            "threshold_4": 0,
            "threshold_3": 1,
            "threshold_2": 3,
        },
        "itso": {
            "strategy": "llm_rubric_guidance",
            "guidance": "ITSO guidance",
        },
    }
    now = datetime.now(UTC)
    for agent_id in ("sme", "gad", "itso", "coordinator"):
        is_coordinator = agent_id == "coordinator"
        rubric_set = RubricSet(
            agent_id=agent_id,
            name=f"{agent_id} validation rubric",
            # Coordinator Rubric v3 == adapter_version 2, 10 criteria.
            version_number=3 if is_coordinator else 1,
            status="published",
            adapter_key=agent_id,
            adapter_version=2 if is_coordinator else 1,
            published_at=now,
        )
        db_session.add(rubric_set)
        db_session.flush()
        db_session.add(
            RubricAgentActivation(
                agent_id=agent_id,
                rubric_set_id=rubric_set.rubric_set_id,
                updated_by=None,
                updated_at=now,
            )
        )
        if is_coordinator:
            crits = _seed_coordinator_v3_criteria(db_session, rubric_set, now)
            if agent_id in target_agents:
                expected_scores.extend(
                    {
                        "agent_id": agent_id,
                        "rubric_set_id": str(rubric_set.rubric_set_id),
                        "rubric_criterion_id": str(crit.rubric_criterion_id),
                        "expected_score": scores[agent_id],
                    }
                    for crit in crits
                )
            continue
        domain = RubricDomain(
            rubric_set_id=rubric_set.rubric_set_id,
            code=f"{agent_id}-domain",
            title=f"{agent_id} domain",
            display_order=1,
        )
        db_session.add(domain)
        db_session.flush()
        criterion = RubricCriterion(
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code=codes[agent_id],
            title=f"{agent_id} criterion",
            description=f"Expected {agent_id} behavior",
            scoring_strategy=configs[agent_id]["strategy"],
            strategy_config=configs[agent_id],
            display_order=1,
        )
        db_session.add(criterion)
        db_session.flush()
        if agent_id in target_agents:
            expected_scores.append(
                {
                    "agent_id": agent_id,
                    "rubric_set_id": str(rubric_set.rubric_set_id),
                    "rubric_criterion_id": str(criterion.rubric_criterion_id),
                    "expected_score": scores[agent_id],
                }
            )
    db_session.commit()
    return expected_scores


_COORDINATOR_V3_DOMAINS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "OP",
        "Organization & Presentation",
        ("OP-01", "OP-02", "OP-03", "OP-04", "OP-05"),
    ),
    ("A", "Assessment", ("A-01", "A-02", "A-03", "A-04", "A-05")),
)


def _seed_coordinator_v3_criteria(
    db_session, rubric_set, now
) -> list[RubricCriterion]:
    """Seed the 10-criterion Coordinator Rubric v3 (OP + A domains)."""
    from server.scripts.seed_rubrics import _COORDINATOR_STRATEGY_CONFIGS

    crits: list[RubricCriterion] = []
    for order, (dcode, dtitle, ccodes) in enumerate(_COORDINATOR_V3_DOMAINS, start=1):
        domain = RubricDomain(
            rubric_set_id=rubric_set.rubric_set_id,
            code=dcode,
            title=dtitle,
            display_order=order,
        )
        db_session.add(domain)
        db_session.flush()
        for c_order, ccode in enumerate(ccodes, start=1):
            cfg = _COORDINATOR_STRATEGY_CONFIGS[ccode]
            criterion = RubricCriterion(
                rubric_domain_id=domain.rubric_domain_id,
                criterion_code=ccode,
                title=f"Coordinator {ccode}",
                description=f"Expected coordinator behavior for {ccode}",
                scoring_strategy=cfg["strategy"],
                strategy_config=cfg,
                display_order=c_order,
            )
            db_session.add(criterion)
            db_session.flush()
            crits.append(criterion)
    return crits


def _setup_validation(
    db_session,
    admin_user,
    expected_scores=None,
    program: str = "BSCS",
    include_coordinator: bool = False,
):
    """Shared helper: seed rubrics + docs + create validation, return key objects."""
    if expected_scores is None:
        expected_scores = _seed_active_rubrics(
            db_session, include_coordinator=include_coordinator
        )
    slm = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="slm",
        chroma_stored=False,
        program=program,
    )
    return expected_scores, slm


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


def test_model_validation_readiness_failure_creates_nothing(
    client, auth_cookies_admin, admin_user, db_session, monkeypatch
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    drained = []
    monkeypatch.setattr(
        "server.modules.admin.router.probe_local_model_readiness",
        lambda: (_ for _ in ()).throw(RuntimeError("unavailable")),
    )
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue",
        lambda: drained.append(True),
    )
    _auth(client, auth_cookies_admin)
    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert response.status_code == 503
    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert drained == []


def test_model_validation_admission_failure_creates_nothing(
    client, auth_cookies_admin, admin_user, db_session, monkeypatch
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    drained = []
    monkeypatch.setattr(
        "server.modules.admin.router.admission_schema_ready", lambda db: False
    )
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue",
        lambda: drained.append(True),
    )
    _auth(client, auth_cookies_admin)
    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert response.status_code == 503
    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert drained == []


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
    drained = []

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
        "server.modules.admin.router.drain_evaluation_queue",
        lambda: drained.append(True),
    )
    _auth(client, auth_cookies_admin)

    criteria_response = client.get("/api/v1/admin/model-validations/criteria")
    assert criteria_response.status_code == 200
    # 1 each for sme/gad/itso + 10 for the Coordinator v3 rubric.
    assert criteria_response.json()["total_criteria"] == 13

    # Regression check: higher version published rubric is ignored if not activated.
    sme_v2 = RubricSet(
        agent_id="sme",
        name="sme validation rubric v2",
        version_number=2,
        status="published",
        adapter_key="sme",
        adapter_version=1,
        published_at=datetime.now(UTC),
    )
    db_session.add(sme_v2)
    db_session.flush()
    sme_v2_domain = RubricDomain(
        rubric_set_id=sme_v2.rubric_set_id,
        code="sme-v2-domain",
        title="sme v2 domain",
        display_order=1,
    )
    db_session.add(sme_v2_domain)
    db_session.flush()
    db_session.add(
        RubricCriterion(
            rubric_domain_id=sme_v2_domain.rubric_domain_id,
            criterion_code="SME-V2-EXTRA",
            title="sme v2 extra criterion",
            description="Extra criterion",
            scoring_strategy="count_band",
            strategy_config={
                "strategy": "count_band",
                "mode": "minimum_count",
                "threshold_4": 3,
                "threshold_3": 2,
                "threshold_2": 1,
            },
            display_order=1,
        )
    )
    db_session.commit()

    criteria_resp_v2 = client.get("/api/v1/admin/model-validations/criteria")
    assert criteria_resp_v2.status_code == 200
    assert criteria_resp_v2.json()["total_criteria"] == 13
    sme_group = next(
        g for g in criteria_resp_v2.json()["agents"] if g["agent_id"] == "sme"
    )
    assert sme_group["rubric_version"] == 1
    assert [c["criterion_code"] for c in sme_group["criteria"]] == ["SME-1"]

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
    assert drained == [True]
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

    # Check that standard evaluation form snapshots were persisted
    snapshots = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=job.evaluation_id)
        .all()
    )
    assert len(snapshots) == 3
    assert {s.agent_id for s in snapshots} == {"sme", "gad", "itso"}

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
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)
    bad_scores = list(expected_scores)
    bad_scores[0] = dict(bad_scores[0], expected_score=5)
    response = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": bad_scores,
        },
    )
    assert response.status_code == 422


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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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
    detail_resp = client.get(f"/api/v1/admin/model-validations/{validation_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["validation_id"] == validation_id
    assert len(detail_resp.json()["bound_forms"]) == 3
    assert len(detail_resp.json()["criterion_scores"]) == 3

    # Faculty blocked
    _auth(client, auth_cookies_faculty)
    faculty_resp = client.get(f"/api/v1/admin/model-validations/{validation_id}")
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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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


def test_validation_full_requires_curriculum_and_all_four_agents(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Full validation requires explicit curriculum and all 4 agents."""
    expected_scores_4, slm = _setup_validation(
        db_session, admin_user, include_coordinator=True
    )
    curriculum_doc = _seed_document(
        db_session,
        owner_id=admin_user.user_id,
        source_type="curriculum",
        chroma_stored=True,
        program="BSCS",
    )
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
    )
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, domain: True,
    )
    _auth(client, auth_cookies_admin)

    # Missing curriculum_id when partial_without_curriculum=False -> 422
    resp_no_curr = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": False,
            "expected_scores": expected_scores_4,
        },
    )
    assert resp_no_curr.status_code == 422

    # Providing curriculum_id and all 4 agents -> 202
    resp_full = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "curriculum_id": str(curriculum_doc.document_id),
            "partial_without_curriculum": False,
            "expected_scores": expected_scores_4,
        },
    )
    assert resp_full.status_code == 202
    data = resp_full.json()
    assert data["partial_without_curriculum"] is False
    assert len(data["bound_forms"]) == 4
    # sme/gad/itso 1 each + 10 Coordinator v3 criteria.
    assert len(data["criterion_scores"]) == 13


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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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


def test_validation_rejects_coordinator_in_partial_mode(
    client: TestClient,
    auth_cookies_admin,
    admin_user,
    db_session,
    monkeypatch,
) -> None:
    """Partial validation rejects Program Coordinator expected scores."""
    expected_scores, slm = _setup_validation(
        db_session, admin_user, include_coordinator=True
    )
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
    )
    _auth(client, auth_cookies_admin)

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,  # Contains coordinator
        },
    )
    assert resp.status_code == 422
    assert "coordinator" in str(resp.json()["detail"]).lower()


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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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

    assess_model_validation_toxicity(
        uuid.UUID(create_resp.json()["evaluation_id"]), db_session
    )
    db_session.refresh(validation)
    assert validation.toxicity_score is None
    assert validation.toxicity_label is None
    assert validation.toxicity_error is not None
    assert "not enabled" in validation.toxicity_error.lower()


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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
    )
    _auth(client, auth_cookies_admin)

    # Missing SLM document triggers 404 and rollback
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(uuid.uuid4()),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 404

    eval_count = db_session.query(EvaluationJob).count()
    assert eval_count == 0
    val_count = db_session.query(ModelValidation).count()
    assert val_count == 0
    snap_count = db_session.query(EvaluationFormSnapshot).count()
    assert snap_count == 0


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
        email="admin2@lspu.edu.ph",
        password="password123",
        role=UserRole.ADMIN,
    )
    db_session.commit()

    expected_scores, slm = _setup_validation(db_session, admin_user)
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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
        json={"email": "admin2@lspu.edu.ph", "password": "password123"},
    )
    assert login_resp.status_code == 200
    client.cookies.update(dict(login_resp.cookies))

    # Second admin can list first admin's validation
    list_resp = client.get("/api/v1/admin/model-validations")
    assert list_resp.status_code == 200
    assert list_resp.json()["total"] >= 1

    # Second admin can view the linked evaluation detail
    validation_id = create_resp.json()["validation_id"]
    detail_resp = client.get(f"/api/v1/admin/model-validations/{validation_id}")
    assert detail_resp.status_code == 200
    assert detail_resp.json()["evaluation_id"] == created_eval_id

    eval_resp = client.get(
        f"/api/v1/admin/model-validations/{validation_id}/evaluation"
    )
    assert eval_resp.status_code == 200
    assert eval_resp.json()["evaluation_id"] == created_eval_id


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
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
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


def test_create_model_validation_rejects_unknown_fields(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    expected_scores, slm = _setup_validation(db_session, admin_user)
    _auth(client, auth_cookies_admin)

    # Unknown field in expected_scores item
    bad_item_scores = [dict(item) for item in expected_scores]
    bad_item_scores[0]["snapshot_rubric_set_id"] = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": bad_item_scores,
        },
    )
    assert resp.status_code == 422
    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0

    # UUIDs remain valid JSON strings, while primitive request values are strict.
    string_score_items = [dict(item) for item in expected_scores]
    string_score_items[0]["expected_score"] = "3"
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": string_score_items,
        },
    )
    assert resp.status_code == 422

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": "true",
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 422
    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0

    # Unknown field in root payload
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
            "extra_root_field": "forbidden",
        },
    )
    assert resp.status_code == 422
    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0


def test_create_model_validation_rollback_on_snapshot_failure(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation
    from server.modules.admin.schemas import ModelValidationCreateRequest

    expected_scores, slm = _setup_validation(db_session, admin_user)

    def failing_persist(*args, **kwargs):
        raise RuntimeError("Simulated snapshot persistence error")

    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.persist_evaluation_form_snapshots",
        failing_persist,
    )

    req = ModelValidationCreateRequest.model_validate(
        {
            "document_id": slm.document_id,
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        }
    )

    with pytest.raises(RuntimeError, match="Simulated snapshot persistence error"):
        create_model_validation(
            req,
            created_by=admin_user.user_id,
            created_by_role="admin",
            db=db_session,
        )

    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0


def test_create_model_validation_rollback_on_post_job_model_construction_failure(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation
    from server.modules.admin.schemas import ModelValidationCreateRequest

    expected_scores, slm = _setup_validation(db_session, admin_user)

    def failing_model_validation(*args, **kwargs):
        raise RuntimeError("Simulated model validation construction error")

    monkeypatch.setattr(
        "server.modules.admin.model_validation_service.ModelValidation",
        failing_model_validation,
    )

    req = ModelValidationCreateRequest.model_validate(
        {
            "document_id": slm.document_id,
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        }
    )

    with pytest.raises(
        RuntimeError, match="Simulated model validation construction error"
    ):
        create_model_validation(
            req,
            created_by=admin_user.user_id,
            created_by_role="admin",
            db=db_session,
        )

    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0


def test_create_model_validation_rollback_on_post_job_criterion_failure(
    admin_user, db_session, monkeypatch
) -> None:
    from server.modules.admin.model_validation_service import create_model_validation
    from server.modules.admin.schemas import ModelValidationCreateRequest

    expected_scores, slm = _setup_validation(db_session, admin_user)

    original_add_all = db_session.add_all

    def failing_add_all(instances):
        if any(isinstance(i, ModelValidationCriterionScore) for i in instances):
            raise RuntimeError("Simulated criterion insertion failure")
        return original_add_all(instances)

    monkeypatch.setattr(db_session, "add_all", failing_add_all)

    req = ModelValidationCreateRequest.model_validate(
        {
            "document_id": slm.document_id,
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        }
    )

    with pytest.raises(RuntimeError, match="Simulated criterion insertion failure"):
        create_model_validation(
            req,
            created_by=admin_user.user_id,
            created_by_role="admin",
            db=db_session,
        )

    assert db_session.query(EvaluationJob).count() == 0
    assert db_session.query(ModelValidation).count() == 0
    assert db_session.query(EvaluationFormSnapshot).count() == 0
    assert db_session.query(ModelValidationCriterionScore).count() == 0
