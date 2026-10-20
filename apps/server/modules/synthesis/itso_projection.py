"""Typed ITSO-v2 domain projection; never coerce withheld scores to zero."""

from equiped_harness.itso.history_contracts import ITSOAssessmentResult


def project_itso_domain(result: ITSOAssessmentResult) -> dict:
    return {
        "contract": result.contract,
        "evaluation_id": result.evaluation_id,
        "criteria": [c.model_dump(mode="json") for c in result.criteria],
        "subtotal": result.subtotal,
        "max_score": 4,
        "status": "OK" if result.execution_status == "COMPLETED" else "ERROR",
        "execution_status": result.execution_status,
        "scoring_complete": result.scoring_complete,
        "scored_count": sum(c.score is not None for c in result.criteria),
        "unscored_count": sum(c.score is None for c in result.criteria),
        "issue_count": sum(len(c.concerns) for c in result.criteria),
        "uncertainty_count": sum(len(c.uncertainties) for c in result.criteria),
        "adjectival_rating": None,
    }


def merge_itso_projection(db, *, result: ITSOAssessmentResult) -> None:
    from uuid import UUID

    from server.modules.synthesis.matrix import upsert_monitoring_matrix

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


def load_verified_itso_domain(db, *, domain: dict, document_id) -> dict:
    """Matrix JSON is an index, not authority for v2 facts or identities."""
    from uuid import UUID

    from server.modules.evaluations.itso.assessment_service import (
        find_assessment,
        verified_assessment_result,
    )
    from server.modules.evaluations.itso.exceptions import ITSOError
    from server.modules.evaluations.itso.workflow_models import AssessmentRevision
    from sqlalchemy import select

    try:
        parent = find_assessment(db, UUID(domain["evaluation_id"]))
    except (KeyError, ValueError, TypeError):
        raise ITSOError("assessment_integrity_failed") from None
    if parent is None or parent.document_id != document_id:
        raise ITSOError("assessment_integrity_failed")
    revision = (
        db.scalar(
            select(AssessmentRevision).where(
                AssessmentRevision.assessment_id == parent.assessment_id,
                AssessmentRevision.revision == parent.review_revision,
            )
        )
        if parent.review_revision
        else None
    )
    if parent.review_revision and revision is None:
        raise ITSOError("assessment_integrity_failed")
    try:
        result = verified_assessment_result(db, parent, revision=revision)
    except (ValueError, LookupError):
        raise ITSOError("assessment_integrity_failed") from None
    projection = project_itso_domain(result)
    if domain != projection:
        raise ITSOError("assessment_integrity_failed")
    return projection


def verified_matrix_domains(db, *, domains, document_id):
    """Preserve historical payloads; replace v2 cache with sealed effective facts."""
    if not isinstance(domains, dict):
        return domains
    result = dict(domains)
    domain = result.get("itso", {})
    if domain.get("contract") == "itso_evidence.v1":
        result["itso"] = load_verified_itso_domain(
            db, domain=domain, document_id=document_id
        )
    return result
