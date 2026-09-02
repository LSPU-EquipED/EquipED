"""Focused API contract tests for Model Validation endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from server.modules.documents.models import Document, DocumentChunk
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    RubricAgentActivation,
    RubricCriterion,
    RubricDomain,
    RubricSet,
)
from server.tests.admin.conftest import _auth


@pytest.fixture(autouse=True)
def _model_validation_readiness(monkeypatch):
    monkeypatch.setattr(
        "server.modules.admin.router.probe_local_model_readiness", lambda: None
    )
    monkeypatch.setattr(
        "server.modules.admin.router.admission_schema_ready", lambda db: True
    )
    monkeypatch.setattr(
        "server.modules.admin.router.drain_evaluation_queue", lambda: None
    )
    monkeypatch.setattr(
        "server.modules.documents.curriculum.service.check_chroma_availability",
        lambda doc_id, domain: True,
    )


def _seed_document(
    db_session,
    *,
    owner_id: uuid.UUID,
    source_type: str = "slm",
    program: str = "BSCS",
) -> Document:
    document = Document(
        document_id=uuid.uuid4(),
        title=f"Test {source_type} document",
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
            text="Benchmark sample content",
            token_count=5,
            chroma_stored=True,
        )
    )
    db_session.commit()
    return document


def _seed_active_forms(
    db_session,
) -> dict[str, tuple[RubricSet, list[RubricCriterion]]]:
    """Seed published and active forms for SME, Coordinator, GAD, ITSO."""
    agent_configs = {
        "sme": {
            "code": "SME-1",
            "scoring_strategy": "count_band",
            "config": {
                "strategy": "count_band",
                "mode": "minimum_count",
                "threshold_4": 3,
                "threshold_3": 2,
                "threshold_2": 1,
            },
        },
        "gad": {
            "code": "GAD-1",
            "scoring_strategy": "count_band",
            "config": {
                "strategy": "count_band",
                "mode": "maximum_count",
                "threshold_4": 0,
                "threshold_3": 1,
                "threshold_2": 3,
            },
        },
        "itso": {
            "code": "ITSO-1",
            "scoring_strategy": "llm_rubric_guidance",
            "config": {
                "strategy": "llm_rubric_guidance",
                "guidance": "ITSO compliance guidance",
            },
        },
    }
    now = datetime.now(UTC)
    result = {}
    for agent_id, info in agent_configs.items():
        rubric_set = RubricSet(
            agent_id=agent_id,
            name=f"{agent_id} Active Form v1",
            version_number=1,
            status="published",
            adapter_key=agent_id,
            adapter_version=1,
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
        domain = RubricDomain(
            rubric_set_id=rubric_set.rubric_set_id,
            code=f"{agent_id}-domain",
            title=f"{agent_id} Primary Domain",
            display_order=1,
        )
        db_session.add(domain)
        db_session.flush()
        criterion = RubricCriterion(
            rubric_domain_id=domain.rubric_domain_id,
            criterion_code=info["code"],
            title=f"{agent_id} Criterion Title",
            description=f"{agent_id} Criterion Description",
            scoring_strategy=info["scoring_strategy"],
            strategy_config=info["config"],
            display_order=1,
        )
        db_session.add(criterion)
        db_session.flush()
        result[agent_id] = (rubric_set, [criterion])

    result["coordinator"] = _seed_active_coordinator_v3(db_session, now)
    db_session.commit()
    return result


_COORDINATOR_V3_DOMAINS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    (
        "OP",
        "Organization & Presentation",
        ("OP-01", "OP-02", "OP-03", "OP-04", "OP-05"),
    ),
    ("A", "Assessment", ("A-01", "A-02", "A-03", "A-04", "A-05")),
)


def _seed_active_coordinator_v3(
    db_session, now
) -> tuple[RubricSet, list[RubricCriterion]]:
    """Seed + activate the 10-criterion Coordinator Rubric v3 (adapter_version 2)."""
    from server.scripts.seed_rubrics import _COORDINATOR_STRATEGY_CONFIGS

    rubric_set = RubricSet(
        agent_id="coordinator",
        name="Coordinator Rubric v3",
        version_number=3,
        status="published",
        adapter_key="coordinator",
        adapter_version=2,
        published_at=now,
    )
    db_session.add(rubric_set)
    db_session.flush()
    db_session.add(
        RubricAgentActivation(
            agent_id="coordinator",
            rubric_set_id=rubric_set.rubric_set_id,
            updated_by=None,
            updated_at=now,
        )
    )
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
                description=f"Coordinator criterion {ccode}",
                scoring_strategy=cfg["strategy"],
                strategy_config=cfg,
                display_order=c_order,
            )
            db_session.add(criterion)
            db_session.flush()
            crits.append(criterion)
    return rubric_set, crits


def test_get_catalog_returns_all_four_bindings_without_strategy_leak(
    client: TestClient, auth_cookies_admin, db_session
) -> None:
    """Catalog endpoint returns all four active published bindings."""
    seeded = _seed_active_forms(db_session)
    _auth(client, auth_cookies_admin)

    resp = client.get("/api/v1/admin/model-validations/criteria")
    assert resp.status_code == 200
    data = resp.json()
    # sme/gad/itso 1 each + 10 Coordinator v3 criteria.
    assert data["total_criteria"] == 13
    assert len(data["agents"]) == 4

    agent_map = {a["agent_id"]: a for a in data["agents"]}
    assert set(agent_map.keys()) == {"sme", "coordinator", "gad", "itso"}

    for agent_id, (rubric_set, criteria) in seeded.items():
        agent_dto = agent_map[agent_id]
        is_coordinator = agent_id == "coordinator"
        assert agent_dto["rubric_set_id"] == str(rubric_set.rubric_set_id)
        assert agent_dto["rubric_version"] == (3 if is_coordinator else 1)
        assert len(agent_dto["domains"]) == (2 if is_coordinator else 1)
        assert len(agent_dto["criteria"]) == len(criteria)

        crit_dtos = {c["rubric_criterion_id"]: c for c in agent_dto["criteria"]}
        for crit_obj in criteria:
            crit_dto = crit_dtos[str(crit_obj.rubric_criterion_id)]
            assert crit_dto["criterion_code"] == crit_obj.criterion_code
            assert crit_dto["title"] == crit_obj.title
            assert crit_dto["description"] == crit_obj.description
            assert crit_dto["display_order"] == crit_obj.display_order

            # Strict assertion: NO strategy configuration or scoring rules leaked
            assert "strategy_config" not in crit_dto
            assert "scoring_strategy" not in crit_dto
            assert "scoring_rule" not in crit_dto


def test_partial_validation_submission_and_snapshot_persistence(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    """Partial validation binds SME/GAD/ITSO and persists snapshots."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    _auth(client, auth_cookies_admin)

    expected_scores = [
        {
            "agent_id": agent_id,
            "rubric_set_id": str(seeded[agent_id][0].rubric_set_id),
            "rubric_criterion_id": str(seeded[agent_id][1][0].rubric_criterion_id),
            "expected_score": 3,
        }
        for agent_id in ("sme", "gad", "itso")
    ]

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["partial_without_curriculum"] is True
    assert len(data["bound_forms"]) == 3
    assert {bf["agent_id"] for bf in data["bound_forms"]} == {"sme", "gad", "itso"}
    assert len(data["criterion_scores"]) == 3

    # Check persistence of standard snapshots
    eval_id = uuid.UUID(data["evaluation_id"])
    snapshots = (
        db_session.query(EvaluationFormSnapshot).filter_by(evaluation_id=eval_id).all()
    )
    assert len(snapshots) == 3
    assert {s.agent_id for s in snapshots} == {"sme", "gad", "itso"}


def test_full_validation_submission_with_curriculum(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    """Full validation requires curriculum and binds SME, Coordinator, GAD, ITSO."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    curriculum = _seed_document(
        db_session, owner_id=admin_user.user_id, source_type="curriculum"
    )
    _auth(client, auth_cookies_admin)

    expected_scores = [
        {
            "agent_id": agent_id,
            "rubric_set_id": str(seeded[agent_id][0].rubric_set_id),
            "rubric_criterion_id": str(crit.rubric_criterion_id),
            "expected_score": 4,
        }
        for agent_id in ("sme", "coordinator", "gad", "itso")
        for crit in seeded[agent_id][1]
    ]

    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "curriculum_id": str(curriculum.document_id),
            "partial_without_curriculum": False,
            "expected_scores": expected_scores,
        },
    )
    assert resp.status_code == 202
    data = resp.json()
    assert data["partial_without_curriculum"] is False
    assert len(data["bound_forms"]) == 4
    assert {bf["agent_id"] for bf in data["bound_forms"]} == {
        "sme",
        "coordinator",
        "gad",
        "itso",
    }
    # sme/gad/itso 1 each + 10 Coordinator v3 criteria.
    assert len(data["criterion_scores"]) == 13


def test_stale_catalog_echo_rejected_under_lock(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    """Stale active revision echo is rejected under multi-agent lock."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    _auth(client, auth_cookies_admin)

    stale_scores = [
        {
            "agent_id": agent_id,
            "rubric_set_id": str(seeded[agent_id][0].rubric_set_id),
            "rubric_criterion_id": str(seeded[agent_id][1][0].rubric_criterion_id),
            "expected_score": 3,
        }
        for agent_id in ("sme", "gad", "itso")
    ]

    # Now simulate a concurrent activation of SME Revision 2
    sme_v2 = RubricSet(
        agent_id="sme",
        name="SME Revision 2",
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
        code="sme-domain-2",
        title="SME Domain 2",
        display_order=1,
    )
    db_session.add(sme_v2_domain)
    db_session.flush()
    sme_v2_crit = RubricCriterion(
        rubric_domain_id=sme_v2_domain.rubric_domain_id,
        criterion_code="SME-1",
        title="SME v2 Criterion",
        description="SME v2 Description",
        scoring_strategy="count_band",
        strategy_config={
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 3,
            "threshold_2": 2,
        },
        display_order=1,
    )
    db_session.add(sme_v2_crit)
    db_session.flush()

    # Update activation pointer to v2
    activation = db_session.get(RubricAgentActivation, "sme")
    activation.rubric_set_id = sme_v2.rubric_set_id
    db_session.commit()

    # Submitting with stale v1 rubric_set_id is rejected
    resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": stale_scores,
        },
    )
    assert resp.status_code == 422
    assert "not the current active revision" in str(resp.json()["detail"]).lower()


def test_after_submit_activation_invariance(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    """Subsequent activation changes do not alter accepted snapshots."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    _auth(client, auth_cookies_admin)

    scores = [
        {
            "agent_id": agent_id,
            "rubric_set_id": str(seeded[agent_id][0].rubric_set_id),
            "rubric_criterion_id": str(seeded[agent_id][1][0].rubric_criterion_id),
            "expected_score": 3,
        }
        for agent_id in ("sme", "gad", "itso")
    ]

    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": scores,
        },
    )
    assert create_resp.status_code == 202
    val_id = create_resp.json()["validation_id"]

    # Retire the SME v1 rubric set and point activation elsewhere
    sme_v1 = seeded["sme"][0]
    sme_v1.status = "retired"
    sme_v1.retired_at = datetime.now(UTC)

    sme_v2 = RubricSet(
        agent_id="sme",
        name="SME Revision 2",
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
        code="sme-domain-2",
        title="SME Domain 2",
        display_order=1,
    )
    db_session.add(sme_v2_domain)
    db_session.flush()
    sme_v2_crit = RubricCriterion(
        rubric_domain_id=sme_v2_domain.rubric_domain_id,
        criterion_code="SME-1",
        title="SME v2 Criterion",
        description="SME v2 Description",
        scoring_strategy="count_band",
        strategy_config={
            "strategy": "count_band",
            "mode": "minimum_count",
            "threshold_4": 4,
            "threshold_3": 3,
            "threshold_2": 2,
        },
        display_order=1,
    )
    db_session.add(sme_v2_crit)
    db_session.flush()

    activation = db_session.get(RubricAgentActivation, "sme")
    activation.rubric_set_id = sme_v2.rubric_set_id
    db_session.commit()

    # Detail view must still reflect Revision 1 bound forms and criteria
    detail_resp = client.get(f"/api/v1/admin/model-validations/{val_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    sme_bf = next(bf for bf in detail["bound_forms"] if bf["agent_id"] == "sme")
    assert sme_bf["rubric_set_id"] == str(sme_v1.rubric_set_id)
    assert sme_bf["rubric_version"] == 1


def test_rejects_duplicate_unknown_or_cross_revision_criteria(
    client: TestClient, auth_cookies_admin, admin_user, db_session
) -> None:
    """Rejects duplicate scores, unknown UUIDs, and cross-revision criteria."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")
    _auth(client, auth_cookies_admin)

    # 1. Legacy code-only input is not a compatibility path.
    code_only = [
        {
            "agent_id": agent_id,
            "criterion_id": seeded[agent_id][1][0].criterion_code,
            "expected_score": 3,
        }
        for agent_id in ("sme", "gad", "itso")
    ]
    resp_code_only = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": code_only,
        },
    )
    assert resp_code_only.status_code == 422

    # 2. Duplicate criterion
    dup_scores = [
        {
            "agent_id": "sme",
            "rubric_set_id": str(seeded["sme"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["sme"][1][0].rubric_criterion_id),
            "expected_score": 3,
        },
        {
            "agent_id": "sme",
            "rubric_set_id": str(seeded["sme"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["sme"][1][0].rubric_criterion_id),
            "expected_score": 2,
        },
        {
            "agent_id": "gad",
            "rubric_set_id": str(seeded["gad"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["gad"][1][0].rubric_criterion_id),
            "expected_score": 2,
        },
        {
            "agent_id": "itso",
            "rubric_set_id": str(seeded["itso"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["itso"][1][0].rubric_criterion_id),
            "expected_score": 1,
        },
    ]
    resp_dup = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": dup_scores,
        },
    )
    assert resp_dup.status_code == 422
    assert "duplicate" in str(resp_dup.json()["detail"]).lower()

    # 3. Unknown criterion UUID
    unknown_scores = [
        {
            "agent_id": "sme",
            "rubric_set_id": str(seeded["sme"][0].rubric_set_id),
            "rubric_criterion_id": str(uuid.uuid4()),
            "expected_score": 3,
        },
        {
            "agent_id": "gad",
            "rubric_set_id": str(seeded["gad"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["gad"][1][0].rubric_criterion_id),
            "expected_score": 2,
        },
        {
            "agent_id": "itso",
            "rubric_set_id": str(seeded["itso"][0].rubric_set_id),
            "rubric_criterion_id": str(seeded["itso"][1][0].rubric_criterion_id),
            "expected_score": 1,
        },
    ]
    resp_unknown = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": unknown_scores,
        },
    )
    assert resp_unknown.status_code == 422
    assert "must cover every active" in str(resp_unknown.json()["detail"]).lower()


def test_faculty_rbac_denial_across_all_model_validation_endpoints(
    client: TestClient, auth_cookies_faculty, auth_cookies_admin, admin_user, db_session
) -> None:
    """Faculty receives 403 Forbidden across all model-validation routes."""
    seeded = _seed_active_forms(db_session)
    slm = _seed_document(db_session, owner_id=admin_user.user_id, source_type="slm")

    # Admin creates a validation record
    _auth(client, auth_cookies_admin)
    scores = [
        {
            "agent_id": agent_id,
            "rubric_set_id": str(seeded[agent_id][0].rubric_set_id),
            "rubric_criterion_id": str(seeded[agent_id][1][0].rubric_criterion_id),
            "expected_score": 3,
        }
        for agent_id in ("sme", "gad", "itso")
    ]
    create_resp = client.post(
        "/api/v1/admin/model-validations",
        json={
            "document_id": str(slm.document_id),
            "partial_without_curriculum": True,
            "expected_scores": scores,
        },
    )
    assert create_resp.status_code == 202
    val_id = create_resp.json()["validation_id"]

    # Faculty is denied on all endpoints
    _auth(client, auth_cookies_faculty)
    assert client.get("/api/v1/admin/model-validations/criteria").status_code == 403
    assert client.get("/api/v1/admin/model-validations").status_code == 403
    assert client.get("/api/v1/admin/model-validations/metrics").status_code == 403
    assert client.get(f"/api/v1/admin/model-validations/{val_id}").status_code == 403
    assert (
        client.get(f"/api/v1/admin/model-validations/{val_id}/evaluation").status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/admin/model-validations",
            json={
                "document_id": str(slm.document_id),
                "partial_without_curriculum": True,
                "expected_scores": scores,
            },
        ).status_code
        == 403
    )
