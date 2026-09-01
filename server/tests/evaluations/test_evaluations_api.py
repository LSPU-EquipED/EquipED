"""Tests for owner-scoped faculty evaluation results API and form presentation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi.testclient import TestClient
from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.documents.models import Document
from server.modules.evaluations.agent_schedule import scheduled_agent_ids
from server.modules.evaluations.models import EvaluationJob, EvaluationStatus
from server.modules.rubrics.models import EvaluationFormSnapshot, RubricSet
from server.modules.rubrics.snapshots import resolve_or_reuse_evaluation_snapshots
from server.modules.synthesis.models import AgentResult, CriterionScore
from server.modules.synthesis.service import persist_agent_outputs
from server.tests.evaluations.snapshot_test_helpers import make_agent_result
from server.tests.rubrics.helpers import seed_all_rubrics


def _safe_prepare_test_snapshots(
    session,
    evaluation_id: uuid.UUID,
    *,
    partial_without_curriculum: bool = False,
):
    if session.query(RubricSet).count() == 0:
        seed_all_rubrics(session)
    scheduled_ids = scheduled_agent_ids(
        partial_without_curriculum=partial_without_curriculum
    )
    return resolve_or_reuse_evaluation_snapshots(session, evaluation_id, scheduled_ids)


def _login(client: TestClient, user) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert response.status_code == 200


def _create_document_and_job(
    db_session,
    owner_id: uuid.UUID,
    *,
    partial: bool = False,
    is_legacy: bool = False,
    status: str = EvaluationStatus.COMPLETED.value,
) -> tuple[Document, EvaluationJob]:
    doc = Document(
        document_id=uuid.uuid4(),
        title="Test Syllabus Material",
        program="BSCS",
        source_type="slm",
        file_path="/tmp/test.pdf",
        uploaded_by=owner_id,
        uploaded_at=datetime.now(UTC),
        page_count=5,
        has_ocr_pages=False,
        processing_status="PROCESSED",
    )
    db_session.add(doc)
    db_session.flush()

    job = EvaluationJob(
        evaluation_id=uuid.uuid4(),
        document_id=doc.document_id,
        submitted_by=owner_id,
        status=status,
        partial_without_curriculum=partial,
        partial_reason="Explicit no-curriculum intent" if partial else None,
        is_pre_snapshot_legacy=is_legacy,
    )
    db_session.add(job)
    db_session.commit()
    return doc, job


def _recursively_find_forbidden_keys(data: Any, forbidden: set[str]) -> list[str]:
    """Recursively traverse a parsed JSON structure to find any forbidden keys."""
    found: list[str] = []
    if isinstance(data, dict):
        for key, value in data.items():
            if key in forbidden:
                found.append(key)
            found.extend(_recursively_find_forbidden_keys(value, forbidden))
    elif isinstance(data, list):
        for item in data:
            found.extend(_recursively_find_forbidden_keys(item, forbidden))
    return found


def test_faculty_results_returns_allowlisted_presentation_and_no_private_keys(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty One",
        email="fac1@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, faculty.user_id, partial=False)
    snapshots = _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=False
    )
    snapshot_by_agent = {s.agent_id: s for s in snapshots}

    agent_results = [
        make_agent_result(agent_id, job.evaluation_id, doc.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        agent_results,
        verify_ownership=lambda db: None,
    )

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    # Verify root scorecard fields
    assert data["evaluation_id"] == str(job.evaluation_id)
    assert data["document_id"] == str(doc.document_id)
    assert data["document_title"] == "Test Syllabus Material"
    assert data["program"] == "BSCS"
    assert "synthesized_score" in data
    assert "domain_scores" in data
    assert set(data["domain_scores"].keys()) == {
        "sme",
        "gad",
        "coordinator",
        "itso",
    }
    assert "forms" in data
    assert set(data["forms"].keys()) == {"sme", "gad", "coordinator", "itso"}

    # Verify form presentation fields
    for agent_id, snapshot_dto in snapshot_by_agent.items():
        form_pres = data["forms"][agent_id]
        assert form_pres["form_snapshot_id"] == str(snapshot_dto.snapshot_id)
        assert form_pres["rubric_set_id"] == str(snapshot_dto.rubric_set_id)
        assert form_pres["version"] == snapshot_dto.form.version_number
        assert form_pres["snapshot_hash"] == snapshot_dto.snapshot_hash
        assert form_pres["adapter_key"] == snapshot_dto.adapter_key
        assert form_pres["adapter_version"] == snapshot_dto.adapter_version
        assert len(form_pres["domains"]) == len(snapshot_dto.form.domains)

        for d_idx, dom_pres in enumerate(form_pres["domains"]):
            ref_dom = snapshot_dto.form.domains[d_idx]
            assert dom_pres["rubric_domain_id"] == str(ref_dom.rubric_domain_id)
            assert dom_pres["code"] == ref_dom.code
            assert dom_pres["title"] == ref_dom.title
            assert dom_pres["display_order"] == ref_dom.display_order
            assert len(dom_pres["criteria"]) == len(ref_dom.criteria)

            for c_idx, crit_pres in enumerate(dom_pres["criteria"]):
                ref_crit = ref_dom.criteria[c_idx]
                assert crit_pres["rubric_criterion_id"] == str(
                    ref_crit.rubric_criterion_id
                )
                assert crit_pres["criterion_code"] == ref_crit.criterion_code
                assert crit_pres["title"] == ref_crit.title
                assert crit_pres["description"] == ref_crit.description
                assert crit_pres["display_order"] == ref_crit.display_order

    # Verify co-located domain score block structure and criteria
    for agent_id in ["sme", "gad", "coordinator", "itso"]:
        block = data["domain_scores"][agent_id]
        snap_dto = snapshot_by_agent[agent_id]
        assert block["form_snapshot_id"] == str(snap_dto.snapshot_id)
        assert block["rubric_set_id"] == str(snap_dto.rubric_set_id)
        assert block["version"] == snap_dto.form.version_number
        assert block["snapshot_hash"] == snap_dto.snapshot_hash
        assert block["adapter_key"] == snap_dto.adapter_key
        assert block["adapter_version"] == snap_dto.adapter_version
        assert block["domain_id"] == str(snap_dto.form.domains[0].rubric_domain_id)
        assert block["domain_name"] == snap_dto.form.domains[0].title
        assert block["domain_display_order"] == snap_dto.form.domains[0].display_order
        assert "criteria" in block
        assert len(block["criteria"]) > 0

        for crit in block["criteria"]:
            assert "rubric_criterion_id" in crit
            assert crit["rubric_criterion_id"] is not None
            assert "criterion_id" in crit
            assert "criterion_text" in crit
            assert "description" in crit
            assert crit["description"] is not None
            assert "display_order" in crit
            assert crit["display_order"] is not None
            assert "score" in crit
            assert "justification" in crit
            assert "evidence" in crit
            assert "is_ungrounded" in crit
            assert "chunk_ids" not in crit

        assert "subtotal" in block
        assert block["max_score"] == 4
        assert block["status"] == "OK"
        assert "adjectival_rating" in block
        assert "summary" in block

    # Assert recursive absolute absence of private/internal keys
    # and non-allowlisted identity
    forbidden_keys = {
        "strategy_config",
        "scoring_rule",
        "guidance",
        "prompt_text",
        "raw_response",
        "group_prompts",
        "group_responses",
        "advisory_outputs",
        "provenance",
        "chunk_ids",
    }
    leaked_keys = _recursively_find_forbidden_keys(data, forbidden_keys)
    assert not leaked_keys, (
        f"Private keys leaked in faculty presentation response: {leaked_keys}"
    )


def test_faculty_results_canonical_snapshot_order_reconstruction(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Canonical",
        email="fac-order@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, faculty.user_id, partial=False)
    snapshots = _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=False
    )
    sme_snapshot = next(s for s in snapshots if s.agent_id == "sme")
    canonical_codes = [
        c.criterion_code
        for domain in sme_snapshot.form.domains
        for c in domain.criteria
    ]

    agent_results = [
        make_agent_result(agent_id, job.evaluation_id, doc.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        agent_results,
        verify_ownership=lambda db: None,
    )

    # Scramble the database criterion score rows order
    sme_result = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job.evaluation_id, agent_name="sme")
        .one()
    )
    scores = (
        db_session.query(CriterionScore)
        .filter_by(agent_result_id=sme_result.agent_result_id)
        .all()
    )
    assert len(scores) == len(canonical_codes)

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    returned_sme_criteria = response.json()["domain_scores"]["sme"]["criteria"]
    returned_codes = [c["criterion_id"] for c in returned_sme_criteria]

    # Verify exact canonical snapshot order is preserved
    assert returned_codes == canonical_codes


def test_faculty_results_identity_and_snapshot_hash(client: TestClient, db_session):
    faculty = create_user(
        db_session,
        name="Faculty Hash",
        email="fac-hash@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, faculty.user_id, partial=False)
    snapshots = _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=False
    )
    agent_results = [
        make_agent_result(agent_id, job.evaluation_id, doc.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        agent_results,
        verify_ownership=lambda db: None,
    )

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    for snapshot in snapshots:
        form_dto = data["forms"][snapshot.agent_id]
        assert form_dto["snapshot_hash"] == snapshot.snapshot_hash
        assert form_dto["form_snapshot_id"] == str(snapshot.snapshot_id)
        assert form_dto["rubric_set_id"] == str(snapshot.rubric_set_id)
        assert form_dto["version"] == snapshot.form.version_number
        assert form_dto["adapter_key"] == snapshot.adapter_key
        assert form_dto["adapter_version"] == snapshot.adapter_version


def test_faculty_results_partial_evaluation_scheduled_forms_only(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Partial",
        email="fac-part@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, faculty.user_id, partial=True)
    snapshots = _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=True
    )
    assert len(snapshots) == 3
    assert {s.agent_id for s in snapshots} == {"sme", "gad", "itso"}

    agent_results = [
        make_agent_result(agent_id, job.evaluation_id, doc.document_id)
        for agent_id in ["sme", "gad", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        agent_results,
        verify_ownership=lambda db: None,
    )

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    assert data["is_partial"] is True
    assert data["partial_reason"] == "Explicit no-curriculum intent"
    assert set(data["domain_scores"].keys()) == {"sme", "gad", "itso"}
    assert "coordinator" not in data["domain_scores"]
    assert set(data["forms"].keys()) == {"sme", "gad", "itso"}
    assert "coordinator" not in data["forms"]


def test_faculty_results_coherent_legacy_returns_200_with_exact_label(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Legacy",
        email="fac-legacy@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=True
    )

    # Create historical AgentResult and CriterionScore rows without form_snapshot_id
    for agent_name in ["sme", "gad", "coordinator", "itso"]:
        ar = AgentResult(
            agent_result_id=uuid.uuid4(),
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            agent_name=agent_name,
            subtotal=3.0,
            processing_seconds=1.0,
            token_count=10,
            model_name="test-model",
            summary="Historical legacy output",
            success=True,
            form_snapshot_id=None,
        )
        db_session.add(ar)
        db_session.flush()

        cs = CriterionScore(
            criterion_score_id=uuid.uuid4(),
            agent_result_id=ar.agent_result_id,
            evaluation_id=job.evaluation_id,
            document_id=doc.document_id,
            criterion_id="LEGACY-01",
            criterion_title="Legacy Criterion",
            score=3,
            justification="Historical justification",
        )
        db_session.add(cs)

    db_session.commit()

    # Verify zero snapshot rows
    assert (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=job.evaluation_id)
        .count()
        == 0
    )

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    assert data["legacy_notice"] == "Legacy — form snapshot unavailable"
    assert data["forms"] == {}
    for agent_name in ["sme", "gad", "coordinator", "itso"]:
        block = data["domain_scores"][agent_name]
        assert block["form_snapshot_id"] is None
        assert block["version"] is None


def test_faculty_results_legacy_marker_true_with_zero_results_fails_integrity(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Empty Legacy",
        email="fac-empty-leg@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    _, job = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=True
    )
    # Zero AgentResults persisted with marker true -> fails integrity
    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 500
    assert (
        response.json()["detail"] == "Evaluation results failed integrity verification"
    )


def test_faculty_results_zero_results_allowed_in_preprocessing_state(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Preprocessing",
        email="fac-pre@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    _, job_submitted = _create_document_and_job(
        db_session,
        faculty.user_id,
        partial=False,
        is_legacy=False,
        status=EvaluationStatus.SUBMITTED.value,
    )
    _, job_preprocessing = _create_document_and_job(
        db_session,
        faculty.user_id,
        partial=False,
        is_legacy=False,
        status=EvaluationStatus.PREPROCESSING.value,
    )
    _, job_evaluating = _create_document_and_job(
        db_session,
        faculty.user_id,
        partial=False,
        is_legacy=False,
        status=EvaluationStatus.EVALUATING.value,
    )

    _login(client, faculty)

    # SUBMITTED: allowed empty response
    res_sub = client.get(f"/api/v1/evaluations/{job_submitted.evaluation_id}/results")
    assert res_sub.status_code == 200
    assert res_sub.json()["domain_scores"] == {}
    assert res_sub.json()["forms"] == {}

    # PREPROCESSING: allowed empty response
    res_pre = client.get(
        f"/api/v1/evaluations/{job_preprocessing.evaluation_id}/results"
    )
    assert res_pre.status_code == 200
    assert res_pre.json()["domain_scores"] == {}
    assert res_pre.json()["forms"] == {}

    # EVALUATING with 0 results: fails integrity
    res_eval = client.get(f"/api/v1/evaluations/{job_evaluating.evaluation_id}/results")
    assert res_eval.status_code == 500
    assert (
        res_eval.json()["detail"] == "Evaluation results failed integrity verification"
    )


def test_faculty_results_failed_agent_renders_error_with_form(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Failed Agent",
        email="fac-fail-agent@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, faculty.user_id, partial=True)
    _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=True
    )

    sme_res = make_agent_result("sme", job.evaluation_id, doc.document_id, success=True)
    gad_res = make_agent_result(
        "gad", job.evaluation_id, doc.document_id, success=False
    )
    itso_res = make_agent_result(
        "itso", job.evaluation_id, doc.document_id, success=True
    )

    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        [sme_res, gad_res, itso_res],
        verify_ownership=lambda db: None,
    )

    _login(client, faculty)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 200
    data = response.json()

    assert "gad" in data["forms"]
    gad_block = data["domain_scores"]["gad"]
    assert gad_block["status"] == "ERROR"
    assert gad_block["criteria"] == []
    assert gad_block["subtotal"] == 0.0


def test_faculty_results_corrupted_mixed_bindings_fails_closed(
    client: TestClient, db_session
):
    faculty = create_user(
        db_session,
        name="Faculty Corrupt",
        email="fac-corrupt@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    # Case A: is_pre_snapshot_legacy=False but AgentResult has null form_snapshot_id
    doc_a, job_a = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=False
    )
    _safe_prepare_test_snapshots(
        db_session, job_a.evaluation_id, partial_without_curriculum=False
    )
    agent_results_a = [
        make_agent_result(agent_id, job_a.evaluation_id, doc_a.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job_a.evaluation_id,
        doc_a.document_id,
        agent_results_a,
        verify_ownership=lambda db: None,
    )
    # Tamper: set one form_snapshot_id to NULL
    sme_res = (
        db_session.query(AgentResult)
        .filter_by(evaluation_id=job_a.evaluation_id, agent_name="sme")
        .one()
    )
    sme_res.form_snapshot_id = None
    db_session.commit()

    _login(client, faculty)
    res_a = client.get(f"/api/v1/evaluations/{job_a.evaluation_id}/results")
    assert res_a.status_code == 500
    assert res_a.json()["detail"] == "Evaluation results failed integrity verification"

    # Case B: is_pre_snapshot_legacy=False but snapshot row hash is tampered
    doc_b, job_b = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=False
    )
    _safe_prepare_test_snapshots(
        db_session, job_b.evaluation_id, partial_without_curriculum=False
    )
    agent_results_b = [
        make_agent_result(agent_id, job_b.evaluation_id, doc_b.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job_b.evaluation_id,
        doc_b.document_id,
        agent_results_b,
        verify_ownership=lambda db: None,
    )
    # Tamper: corrupt snapshot_hash in DB
    snap_sme = (
        db_session.query(EvaluationFormSnapshot)
        .filter_by(evaluation_id=job_b.evaluation_id, agent_id="sme")
        .one()
    )
    snap_sme.snapshot_hash = "0" * 64
    db_session.commit()

    res_b = client.get(f"/api/v1/evaluations/{job_b.evaluation_id}/results")
    assert res_b.status_code == 500
    assert res_b.json()["detail"] == "Evaluation results failed integrity verification"

    # Case C: is_pre_snapshot_legacy=False but criterion title mismatch
    doc_c, job_c = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=False
    )
    _safe_prepare_test_snapshots(
        db_session, job_c.evaluation_id, partial_without_curriculum=False
    )
    agent_results_c = [
        make_agent_result(agent_id, job_c.evaluation_id, doc_c.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job_c.evaluation_id,
        doc_c.document_id,
        agent_results_c,
        verify_ownership=lambda db: None,
    )
    # Tamper: modify criterion title in DB
    first_score = (
        db_session.query(CriterionScore)
        .filter_by(evaluation_id=job_c.evaluation_id)
        .first()
    )
    first_score.criterion_title = "Corrupted Title"
    db_session.commit()

    res_c = client.get(f"/api/v1/evaluations/{job_c.evaluation_id}/results")
    assert res_c.status_code == 500
    assert res_c.json()["detail"] == "Evaluation results failed integrity verification"

    # Case D: is_pre_snapshot_legacy=True but incoherent because has snapshot rows
    doc_d, job_d = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=True
    )
    _safe_prepare_test_snapshots(
        db_session, job_d.evaluation_id, partial_without_curriculum=False
    )
    # Add a legacy AgentResult
    ar_d = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job_d.evaluation_id,
        document_id=doc_d.document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="Historical legacy output",
        success=True,
        form_snapshot_id=None,
    )
    db_session.add(ar_d)
    db_session.commit()

    res_d = client.get(f"/api/v1/evaluations/{job_d.evaluation_id}/results")
    assert res_d.status_code == 500
    assert res_d.json()["detail"] == "Evaluation results failed integrity verification"

    # Case E: is_pre_snapshot_legacy=True but incoherent
    # because an AgentResult has non-null form_snapshot_id
    doc_e, job_e = _create_document_and_job(
        db_session, faculty.user_id, partial=False, is_legacy=True
    )
    ar_e = AgentResult(
        agent_result_id=uuid.uuid4(),
        evaluation_id=job_e.evaluation_id,
        document_id=doc_e.document_id,
        agent_name="sme",
        subtotal=3.0,
        processing_seconds=1.0,
        token_count=10,
        model_name="test-model",
        summary="Historical legacy output",
        success=True,
        form_snapshot_id=uuid.uuid4(),  # non-null in legacy job
    )
    db_session.add(ar_e)
    db_session.commit()

    res_e = client.get(f"/api/v1/evaluations/{job_e.evaluation_id}/results")
    assert res_e.status_code == 500
    assert res_e.json()["detail"] == "Evaluation results failed integrity verification"


def test_faculty_results_non_owner_returns_404_ownership_masking(
    client: TestClient, db_session
):
    owner = create_user(
        db_session,
        name="Owner User",
        email="owner@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    other_user = create_user(
        db_session,
        name="Other Faculty",
        email="other@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()

    doc, job = _create_document_and_job(db_session, owner.user_id, partial=False)
    _safe_prepare_test_snapshots(
        db_session, job.evaluation_id, partial_without_curriculum=False
    )
    agent_results = [
        make_agent_result(agent_id, job.evaluation_id, doc.document_id)
        for agent_id in ["sme", "gad", "coordinator", "itso"]
    ]
    persist_agent_outputs(
        db_session,
        job.evaluation_id,
        doc.document_id,
        agent_results,
        verify_ownership=lambda db: None,
    )

    # Login as other user
    _login(client, other_user)
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert response.status_code == 404
    assert response.json()["detail"] == "Evaluation not found"
