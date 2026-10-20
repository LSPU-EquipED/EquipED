"""Real matrix response validation against sealed persisted synthetic v2 runs."""

import copy
from uuid import UUID

import pytest
from sqlalchemy import select, update

from server.modules.itso_assessments.models import ITSOAssessment
from server.modules.synthesis.itso_projection import project_itso_domain
from server.modules.synthesis.matrix import upsert_monitoring_matrix
from server.modules.synthesis.models import MonitoringMatrix

from .conftest import make_document, seed_historical_assessment


def merge_itso_projection(db, *, result):
    """Seed historical matrix fixtures without exposing a production writer."""
    domain = project_itso_domain(result)
    upsert_monitoring_matrix(
        db,
        document_id=UUID(result.document_id),
        evaluation_id=UUID(result.evaluation_id),
        evaluation_status=(
            "IN_PROGRESS" if result.execution_status == "COMPLETED" else "FAILED"
        ),
        domain_scores={"itso": domain},
        flag_count=domain["issue_count"],
        target_agent="itso",
    )


def seed_matrix(http, db, actors, owned, factory):
    doc, source = owned
    job, result = seed_historical_assessment(db, doc, actors[0], source)
    merge_itso_projection(db, result=result)
    db.commit()
    return job, result


def test_matrix_and_master_http_nullable_v2_facts(
    http, db_session, actors, owned, factory
):
    client, _ = http
    job, result = seed_matrix(http, db_session, actors, owned, factory)
    for path in (
        "/api/v1/evaluations/matrix",
        f"/api/v1/evaluations/matrix/{job.document_id}",
    ):
        response = client.get(path)
        assert response.status_code == 200, response.text
        data = response.json()
        domain = (
            data["items"][0]["domain_scores"]["itso"]
            if "items" in data
            else data["pillars"]["itso"]
        )
        assert domain["contract"] == "itso_evidence.v1"
        assert domain["evaluation_id"] == str(job.evaluation_id)
        assert domain["subtotal"] is None
        assert domain["execution_status"] == "COMPLETED"
        assert not domain["scoring_complete"]
        assert len(domain["criteria"]) == 5
        assert domain["scored_count"] == 0 and domain["unscored_count"] == 5
        assert domain["uncertainty_count"] > 0
        assert domain["criteria"][0]["score"] is None
        assert "criterion_text" not in domain["criteria"][0]
        assert "generations" not in response.text and "raw_prompt" not in response.text
        assert data.get("can_certify", False) is False


def test_same_title_program_itso_projections_keep_document_identity(
    http, db_session, actors, owned, factory
):
    from server.modules.synthesis.itso_projection import verified_matrix_domains

    client, _ = http
    first_doc, first_source = owned
    first_doc.title = "Shared SLM"
    first_doc.program = "BSCS"
    second_doc, second_source = make_document(db_session, actors[0])
    second_doc.title = "Shared SLM"
    second_doc.program = "BSCS"
    db_session.commit()
    assert first_doc.document_id != second_doc.document_id

    first_job, first_result = seed_historical_assessment(
        db_session, first_doc, actors[0], first_source
    )
    assert first_job.document_id == first_doc.document_id
    assert first_result.document_id == str(first_doc.document_id)
    merge_itso_projection(db_session, result=first_result)
    db_session.commit()
    second_job, second_result = seed_historical_assessment(
        db_session, second_doc, actors[0], second_source
    )
    assert second_job.document_id == second_doc.document_id
    assert second_result.document_id == str(second_doc.document_id)
    merge_itso_projection(db_session, result=second_result)
    db_session.commit()

    rows = list(
        db_session.scalars(
            select(MonitoringMatrix).order_by(MonitoringMatrix.document_id)
        )
    )
    assert len(rows) == 2, (
        first_doc.document_id,
        second_doc.document_id,
        first_result.document_id,
        second_result.document_id,
        [row.document_id for row in rows],
    )
    assert {row.document_id for row in rows} == {
        first_doc.document_id,
        second_doc.document_id,
    }
    for row, doc_id, job in (
        (
            next(r for r in rows if r.document_id == first_doc.document_id),
            first_doc.document_id,
            first_job,
        ),
        (
            next(r for r in rows if r.document_id == second_doc.document_id),
            second_doc.document_id,
            second_job,
        ),
    ):
        domain = verified_matrix_domains(
            db_session, domains=row.domain_scores_json, document_id=doc_id
        )["itso"]
        assert domain["evaluation_id"] == str(job.evaluation_id)

    for document_id, evaluation_id in (
        (first_doc.document_id, first_job.evaluation_id),
        (second_doc.document_id, second_job.evaluation_id),
    ):
        response = client.get(f"/api/v1/evaluations/matrix/{document_id}")
        assert response.status_code == 200, response.text
        assert response.json()["pillars"]["itso"]["evaluation_id"] == str(evaluation_id)


@pytest.mark.parametrize(
    "tamper", ["projection", "parent", "source", "seal", "document"]
)
def test_matrix_readers_reject_unsealed_or_misbound_data(
    http, db_session, actors, owned, factory, tamper
):
    client, _ = http
    job, _ = seed_matrix(http, db_session, actors, owned, factory)
    if tamper == "projection":
        row = db_session.scalar(select(MonitoringMatrix))
        payload = copy.deepcopy(row.domain_scores_json)
        payload["itso"]["uncertainty_count"] += 1
        row.domain_scores_json = payload
    elif tamper == "parent":
        db_session.execute(
            update(ITSOAssessment).values(effective_policy_hash="f" * 64)
        )
    elif tamper == "seal":
        from server.modules.itso_assessments.workflow_models import (
            AssessmentEvidence,
        )

        for row in db_session.scalars(select(AssessmentEvidence)):
            if "result_seal" in row.payload:
                db_session.execute(
                    update(AssessmentEvidence)
                    .where(AssessmentEvidence.id == row.id)
                    .values(payload={"result_seal": {"invalid": True}})
                )
    elif tamper == "document":
        from .conftest import make_document

        other_doc, _ = make_document(db_session, actors[0])
        db_session.execute(
            update(ITSOAssessment).values(document_id=other_doc.document_id)
        )
    else:
        from server.modules.documents.source_artifacts import DocumentSourceSnapshot

        db_session.execute(
            update(DocumentSourceSnapshot).values(inventory_hash="f" * 64)
        )
    db_session.commit()
    for path in (
        "/api/v1/evaluations/matrix",
        f"/api/v1/evaluations/matrix/{job.document_id}",
    ):
        response = client.get(path)
        assert response.status_code == 409, response.text
        assert response.json()["detail"]["code"] == "assessment_integrity_failed"


def test_repeated_domain_replaces_counts_preserves_other_domains(
    http, db_session, actors, owned, factory
):
    from server.modules.synthesis.matrix import (
        _completed_domain_count,
        _composite_from_domains,
    )

    job, result = seed_matrix(http, db_session, actors, owned, factory)
    row = db_session.scalar(select(MonitoringMatrix))
    payload = copy.deepcopy(row.domain_scores_json)
    for agent in ("sme", "coordinator", "gad"):
        payload[agent] = {"criteria": [], "subtotal": 3, "max_score": 4, "status": "OK"}
    row.domain_scores_json = payload
    db_session.commit()
    criteria = list(result.criteria)
    criteria[1] = criteria[1].model_copy(
        update={"concerns": ("one", "two"), "uncertainties": ("one",)}
    )
    newer = result.model_copy(update={"criteria": tuple(criteria)})
    merge_itso_projection(db_session, result=newer)
    db_session.flush()
    first_count = row.flag_count
    merge_itso_projection(db_session, result=newer)
    db_session.flush()
    assert row.flag_count == first_count
    assert row.domain_scores_json["itso"]["issue_count"] == sum(
        len(c.concerns) for c in newer.criteria
    )
    assert row.domain_scores_json["itso"]["uncertainty_count"] == sum(
        len(c.uncertainties) for c in newer.criteria
    )
    assert row.domain_scores_json["sme"]["subtotal"] == 3
    assert row.synthesized_score is None
    assert _completed_domain_count(row.domain_scores_json) == 4
    assert _composite_from_domains(row.domain_scores_json) == (None, None, None)


def test_historical_legacy_http_shape_unchanged(http, db_session, owned):
    doc, _ = owned
    db_session.add(
        MonitoringMatrix(
            document_id=doc.document_id,
            evaluation_status="COMPLETED",
            synthesized_score=75,
            domain_scores_json={
                "itso": {
                    "criteria": [
                        {
                            "criterion_id": "ITSO-01",
                            "criterion_text": "Legacy",
                            "score": 3,
                            "justification": "Historical",
                        }
                    ],
                    "subtotal": 3,
                    "max_score": 4,
                    "status": "OK",
                }
            },
        )
    )
    db_session.commit()
    client, _ = http
    for path in (
        "/api/v1/evaluations/matrix",
        f"/api/v1/evaluations/matrix/{doc.document_id}",
    ):
        response = client.get(path)
        assert response.status_code == 200, response.text
        data = response.json()
        domain = (
            data["items"][0]["domain_scores"]["itso"]
            if "items" in data
            else data["pillars"]["itso"]
        )
        assert domain["subtotal"] == 3
        assert domain["criteria"][0]["criterion_text"] == "Legacy"
        assert domain["criteria"][0]["score"] == 3
        assert "contract" not in domain


def test_projection_dto_strict_union_never_weakens_legacy(
    http, db_session, actors, owned, factory
):
    from pydantic import TypeAdapter, ValidationError

    from server.modules.synthesis.itso_projection import project_itso_domain
    from server.modules.synthesis.schemas import MatrixDomainScoreBlock

    _, result = seed_matrix(http, db_session, actors, owned, factory)
    adapter = TypeAdapter(MatrixDomainScoreBlock)
    domain = project_itso_domain(result)
    assert adapter.validate_python(domain).subtotal is None
    with pytest.raises(ValidationError):
        adapter.validate_python(domain | {"generations": []})
    with pytest.raises(ValidationError):
        adapter.validate_python(
            {"criteria": [], "subtotal": None, "max_score": 4, "status": "OK"}
        )
