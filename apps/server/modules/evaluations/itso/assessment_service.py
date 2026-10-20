"""Authenticated, read-only access to sealed historical ITSO assessments."""

from __future__ import annotations

from uuid import UUID

from equiped_harness.itso.history_contracts import ITSOAssessmentResult, SourceSpan
from server.modules.documents.source_artifact_service import load_owned_source_snapshot
from server.modules.evaluations.service import get_evaluation
from sqlalchemy import select
from sqlalchemy.orm import Session

from .exceptions import ITSOError
from .mechanical_facts import ledger_fingerprint, recompute_facts
from .models import ITSOAssessment
from .policy_service import digest
from .workflow_models import AssessmentEvidence, AssessmentRevision


def find_assessment(db: Session, evaluation_id: UUID) -> ITSOAssessment | None:
    return db.scalar(
        select(ITSOAssessment).where(ITSOAssessment.evaluation_id == evaluation_id)
    )


def _project_source_quotes(projected: dict, source) -> dict:
    """Add exact excerpts from a validated frozen source to public evidence."""
    for criterion in projected["criteria"]:
        for fact in criterion["evidence"]:
            for span in fact["source_spans"]:
                quote = source.canonical_text[span["start_offset"] : span["end_offset"]]
                source.validate_span(SourceSpan.model_validate(span), quote)
                span["quote"] = quote
    return projected


def read_assessment(
    db: Session,
    *,
    evaluation_id: UUID,
    actor_id: UUID,
    role: str,
    evaluator_permissions=None,
) -> dict | None:
    """Read an assessment only after the existing evaluation ownership check."""
    get_evaluation(
        evaluation_id,
        actor_id,
        role,
        db=db,
        evaluator_permissions=evaluator_permissions,
    )
    row = find_assessment(db, evaluation_id)
    if row is None:
        return None
    if row.result_payload is None:
        raise ITSOError("assessment_not_ready", 202)
    revision = (
        db.scalar(
            select(AssessmentRevision).where(
                AssessmentRevision.assessment_id == row.assessment_id,
                AssessmentRevision.revision == row.review_revision,
            )
        )
        if row.review_revision
        else None
    )
    if row.review_revision and revision is None:
        raise ITSOError("assessment_integrity_failed")
    payload = verified_assessment_result(db, row, revision=revision)
    projected = payload.model_dump(mode="json", exclude={"generations"})
    source = load_owned_source_snapshot(
        db,
        snapshot_id=row.source_snapshot_id,
        document_id=row.document_id,
        owner_id=row.owner_id,
    )
    projected = _project_source_quotes(projected, source)
    return projected | {
        "revision": row.review_revision,
        "effective_policy_hash": row.effective_policy_hash,
        "source_snapshot_id": str(row.source_snapshot_id),
        "form_snapshot_id": str(row.form_snapshot_id),
    }


def verified_assessment_result(db, row, *, revision=None) -> ITSOAssessmentResult:
    """Check persisted ownership, identities, mechanical facts and seals."""
    from server.modules.rubrics.snapshots import load_verified_agent_snapshot

    form = load_verified_agent_snapshot(db, row.evaluation_id, "itso")
    source = load_owned_source_snapshot(
        db,
        snapshot_id=row.source_snapshot_id,
        document_id=row.document_id,
        owner_id=row.owner_id,
    )
    payload = revision.result_payload if revision else row.result_payload
    seal = {
        "result_hash": digest(payload),
        "revision": revision.revision if revision else 0,
        "form_hash": form.snapshot_hash,
        "source_hash": source.source_hash,
        "policy_hash": row.effective_policy_hash,
        "verification_hash": ledger_fingerprint(db, row, source),
    }
    seals = db.scalars(
        select(AssessmentEvidence.payload).where(
            AssessmentEvidence.assessment_id == row.assessment_id
        )
    )
    if {"result_seal": seal} not in list(seals):
        raise ITSOError("assessment_integrity_failed")
    result = ITSOAssessmentResult.model_validate(payload)
    if (
        form.snapshot_id != row.form_snapshot_id
        or form.adapter_version != 2
        or form.adapter_key != "itso"
        or result.evaluation_id != str(row.evaluation_id)
        or result.document_id != str(row.document_id)
        or result.source_hash != row.source_hash
        or result.source_hash != source.source_hash
        or result.raw_pdf_hash != source.raw_pdf_hash
        or result.execution_status != row.execution_status
        or (
            revision is not None
            and (
                revision.source_hash != row.source_hash
                or revision.policy_hash != row.effective_policy_hash
            )
        )
    ):
        raise ITSOError("assessment_integrity_failed")
    _verify_code_facts(db, row, source, result)
    for criterion in result.criteria:
        for fact in criterion.evidence:
            for span in fact.source_spans:
                source.validate_span(span)
    return result


def reject_legacy_v2_read(
    db, *, evaluation_id: UUID, actor_id: UUID, role: str, evaluator_permissions=None
) -> None:
    if not isinstance(db, Session):
        return  # Legacy no-database mode cannot hold a durable v2 assessment.
    get_evaluation(
        evaluation_id,
        actor_id,
        role,
        db=db,
        evaluator_permissions=evaluator_permissions,
    )
    if find_assessment(db, evaluation_id) is not None:
        raise ITSOError("unsupported_version")


def _verify_code_facts(db, parent, source, result):
    expected = dict(recompute_facts(db, parent, source))
    for criterion in result.criteria:
        actual = tuple(
            fact
            for fact in criterion.evidence
            if fact.authority == "verified_mechanical"
        )
        if actual != expected.get(criterion.criterion_id, ()):
            raise ITSOError("untrusted_generated_authority", 422)
        ids = [fact.fact_id for fact in criterion.evidence]
        if len(ids) != len(set(ids)):
            raise ITSOError("untrusted_generated_authority", 422)
