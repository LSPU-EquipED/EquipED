"""Progressive monitoring-matrix tests for targeted single-agent evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from server.modules.auth.models import UserRole
from server.modules.auth.service import create_user
from server.modules.evaluations.models import EvaluationJob
from server.modules.synthesis.matrix import AGENT_WEIGHTS, upsert_monitoring_matrix
from server.modules.synthesis.models import MonitoringMatrix
from server.tests.evaluations.conftest import _add_document


def _make_job(db_session, document_id, target_agent, owner_id):
    job = EvaluationJob(
        evaluation_id=uuid4(),
        document_id=document_id,
        status="COMPLETED",
        submitted_by=owner_id,
        submitted_at=datetime.now(UTC),
        target_agent=target_agent,
        partial_without_curriculum=False,
        confirmed_program="BSCS",
    )
    db_session.add(job)
    db_session.commit()
    return job


def _domain(subtotal: float) -> dict:
    return {
        "criteria": [],
        "subtotal": subtotal,
        "max_score": 4,
        "status": "OK",
        "adjectival_rating": "Very Satisfactory",
    }


def test_progressive_matrix_in_progress_until_four_domains(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="prog-matrix@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")

    subtotals = {"sme": 3.5, "gad": 4.0, "itso": 3.0, "coordinator": 2.5}
    agents = ["sme", "gad", "itso"]
    for i, agent in enumerate(agents):
        job = _make_job(db_session, slm_id, agent, owner.user_id)
        row = upsert_monitoring_matrix(
            db=db_session,
            document_id=slm_id,
            evaluation_id=job.evaluation_id,
            evaluation_status="IN_PROGRESS",
            synthesized_score=87.5,
            domain_scores={agent: _domain(subtotals[agent])},
            flag_count=1,
            target_agent=agent,
        )
        assert row.evaluation_status == "IN_PROGRESS"
        assert row.synthesized_score is None
        assert set(row.domain_scores_json.keys()) == set(agents[: i + 1])

    # Fourth domain finalizes the composite.
    job = _make_job(db_session, slm_id, "coordinator", owner.user_id)
    row = upsert_monitoring_matrix(
        db=db_session,
        document_id=slm_id,
        evaluation_id=job.evaluation_id,
        evaluation_status="IN_PROGRESS",
        synthesized_score=80.0,
        domain_scores={"coordinator": _domain(subtotals["coordinator"])},
        flag_count=2,
        target_agent="coordinator",
    )
    assert row.evaluation_status == "COMPLETED"
    assert set(row.domain_scores_json.keys()) == {
        "sme",
        "coordinator",
        "gad",
        "itso",
    }
    expected_pct = round(
        sum(AGENT_WEIGHTS[a] * (subtotals[a] / 4 * 100) for a in subtotals), 2
    )
    assert float(row.synthesized_score) == expected_pct
    # Flags accumulate across newly completed domains: 1+1+1+2 = 5.
    assert row.flag_count == 5


def test_progressive_matrix_failure_without_domains_is_failed(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="prog-fail@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job = _make_job(db_session, slm_id, "gad", owner.user_id)
    row = upsert_monitoring_matrix(
        db=db_session,
        document_id=slm_id,
        evaluation_id=job.evaluation_id,
        evaluation_status="FAILED",
        target_agent="gad",
    )
    assert row.evaluation_status == "FAILED"


def test_progressive_matrix_failure_retains_completed_domains(db_session) -> None:
    owner = create_user(
        db_session,
        name="Owner",
        email="prog-retain@lspu.edu.ph",
        password="password123",
        role=UserRole.FACULTY,
    )
    db_session.commit()
    slm_id = _add_document(db_session, owner_id=owner.user_id, source_type="slm")
    job_sme = _make_job(db_session, slm_id, "sme", owner.user_id)
    upsert_monitoring_matrix(
        db=db_session,
        document_id=slm_id,
        evaluation_id=job_sme.evaluation_id,
        evaluation_status="IN_PROGRESS",
        synthesized_score=87.5,
        domain_scores={"sme": _domain(3.5)},
        flag_count=1,
        target_agent="sme",
    )
    job_gad = _make_job(db_session, slm_id, "gad", owner.user_id)
    row = upsert_monitoring_matrix(
        db=db_session,
        document_id=slm_id,
        evaluation_id=job_gad.evaluation_id,
        evaluation_status="FAILED",
        target_agent="gad",
    )
    assert row.evaluation_status == "IN_PROGRESS"
    assert set(row.domain_scores_json.keys()) == {"sme"}
    persisted = db_session.query(MonitoringMatrix).filter_by(document_id=slm_id).one()
    assert persisted.evaluation_status == "IN_PROGRESS"
