from server.modules.auth.service import build_authenticated_user
from server.modules.evaluations.itso.models import ITSOAssessment
from server.modules.evaluations.itso.workflow_models import AssessmentEvidence
from sqlalchemy import select, update

from .conftest import seed_historical_assessment


def test_historical_read_projects_exact_quotes_and_enforces_ownership_and_seal(
    http, db_session, actors, owned
):
    client, active = http
    doc, source = owned
    job, _ = seed_historical_assessment(db_session, doc, actors[0], source)
    db_session.commit()

    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/assessment")
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["contract"] == "itso_evidence.v1"
    assert len(data["criteria"]) == 5 and data["subtotal"] is None
    spans = [
        span
        for criterion in data["criteria"]
        for fact in criterion["evidence"]
        for span in fact["source_spans"]
    ]
    assert spans
    assert all(
        span["quote"]
        == source.canonical_text[span["start_offset"] : span["end_offset"]]
        for span in spans
    )
    assert "generations" not in data

    active["user"] = build_authenticated_user(actors[1])
    assert (
        client.get(f"/api/v1/evaluations/{job.evaluation_id}/assessment").status_code
        == 404
    )
    active["user"] = build_authenticated_user(actors[0])

    seal = next(
        row
        for row in db_session.scalars(
            select(AssessmentEvidence).where(
                AssessmentEvidence.assessment_id
                == db_session.scalar(
                    select(ITSOAssessment.assessment_id).where(
                        ITSOAssessment.evaluation_id == job.evaluation_id
                    )
                )
            )
        )
        if "result_seal" in row.payload
    )
    payload = dict(seal.payload)
    result_seal = dict(payload["result_seal"])
    result_seal["result_hash"] = "f" * 64
    payload["result_seal"] = result_seal
    db_session.execute(
        update(AssessmentEvidence)
        .where(AssessmentEvidence.id == seal.id)
        .values(payload=payload)
    )
    db_session.commit()
    response = client.get(f"/api/v1/evaluations/{job.evaluation_id}/assessment")
    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "assessment_integrity_failed"


def test_legacy_assessment_union_delegates_owned_results_without_rewriting_rows(
    http, db_session, actors
):
    from server.tests.synthesis.test_service import _seed

    client, active = http
    job = _seed(db_session, user_id=actors[0].user_id)
    direct = client.get(f"/api/v1/evaluations/{job.evaluation_id}/results")
    assert direct.status_code == 200, direct.text
    union = client.get(f"/api/v1/evaluations/{job.evaluation_id}/assessment")
    assert union.status_code == 200, union.text
    assert union.json() == {"contract": "legacy.v1", "result": direct.json()}
    assert db_session.scalar(select(ITSOAssessment.assessment_id)) is None
    active["user"] = build_authenticated_user(actors[1])
    assert (
        client.get(f"/api/v1/evaluations/{job.evaluation_id}/assessment").status_code
        == 404
    )
