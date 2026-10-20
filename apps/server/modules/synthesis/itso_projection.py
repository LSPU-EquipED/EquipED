"""Typed ITSO-v2 domain projection; never coerce withheld scores to zero."""

from equiped_harness.agents.itso.compatibility.contracts import ITSOAssessmentResult


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


def load_verified_itso_domain(db, *, domain: dict, document_id) -> dict:
    """Matrix JSON is an index, not authority for v2 facts or identities."""
    from uuid import UUID

    from server.modules.evaluations.exceptions import ITSOError
    from server.modules.itso_assessments.service import verified_result_for_matrix

    try:
        result = verified_result_for_matrix(
            db,
            evaluation_id=UUID(domain["evaluation_id"]),
            document_id=document_id,
        )
    except (KeyError, ValueError, TypeError):
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
