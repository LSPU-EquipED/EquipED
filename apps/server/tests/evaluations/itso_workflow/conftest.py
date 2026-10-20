"""Synthetic sealed ITSO rows used to exercise read-only history behavior."""

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from equiped_harness.agents.itso.compatibility.contracts import (
    ITSO_CRITERION_IDS,
    CriterionAssessment,
    EvidenceFact,
    ITSOAssessmentResult,
    SourceSpan,
    build_source_snapshot,
    text_hash,
)
from equiped_harness.agents.itso.compatibility.verification import (
    Profile,
    VerificationPlan,
)
from equiped_harness.contracts.snapshots import build_evaluation_form_snapshot
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from server.core.config import Settings, get_settings
from server.core.database import get_db_session
from server.modules.auth.dependencies import require_authenticated_user
from server.modules.auth.models import User, UserRole
from server.modules.auth.service import build_authenticated_user
from server.modules.documents.models import Document
from server.modules.documents.source_artifacts import DocumentSourceSnapshot
from server.modules.evaluations.models import EvaluationJob
from server.modules.itso_assessments.attachment_context import attachment_scope_hash
from server.modules.itso_assessments.models import ITSOAssessment
from server.modules.itso_assessments.policy_service import digest
from server.modules.itso_assessments.router import router
from server.modules.itso_assessments.workflow_models import (
    AssessmentEvidence,
    PreflightAuthorization,
)
from server.modules.rubrics.models import (
    EvaluationFormSnapshot,
    EvaluationRubricProvenance,
)
from server.modules.synthesis.router import router as synthesis_router

TEXT = (
    "Faculty ownership instrument; student consent and confidential rights license.\n"
    "References\n[1] A public work (2024) doi:10.1234/example\n"
)


@pytest.fixture()
def factory(db_session):
    return sessionmaker(bind=db_session.get_bind(), expire_on_commit=False)


@pytest.fixture()
def actors(db_session, seeded_user):
    other = User(
        name="Faculty",
        email="synthetic-faculty@example.invalid",
        password_hash="test-only",
        role=UserRole.FACULTY,
        evaluator_permissions=["itso"],
    )
    db_session.add(other)
    db_session.commit()
    return seeded_user, other


def make_document(db, owner, *, text=TEXT, file_path="synthetic.pdf"):
    doc = Document(
        title="Synthetic",
        source_type="slm",
        file_path=file_path,
        uploaded_by=owner.user_id,
        processing_status="PROCESSED",
        evaluation_readiness="READY",
    )
    db.add(doc)
    db.flush()
    source = build_source_snapshot(
        str(doc.document_id),
        text,
        ((1, 0, len(text)),),
        "synthetic.v1",
        raw_pdf_hash="a" * 64,
    )
    pages = [page.model_dump(mode="json") for page in source.pages]
    references = [reference.model_dump(mode="json") for reference in source.references]
    uncertainties = list(source.inventory_uncertainties)
    inventory_hash = hashlib.sha256(
        json.dumps(
            {
                "pages": pages,
                "references": references,
                "inventory_version": source.inventory_version,
                "inventory_complete": source.inventory_complete,
                "inventory_uncertainties": uncertainties,
            },
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    row = DocumentSourceSnapshot(
        document_id=doc.document_id,
        owner_id=owner.user_id,
        source_hash=source.raw_pdf_hash,
        canonical_hash=source.source_hash,
        extractor_version=source.extractor_version,
        canonicalization_version="synthetic.canonical.v1",
        canonical_text=source.canonical_text,
        page_map=pages,
        reference_inventory=references,
        inventory_hash=inventory_hash,
        inventory_version=source.inventory_version,
        inventory_complete=source.inventory_complete,
        inventory_uncertainties=uncertainties,
    )
    db.add(row)
    db.flush()
    return doc, row


@pytest.fixture()
def owned(db_session, actors):
    return make_document(db_session, actors[0])


@pytest.fixture()
def http(factory, actors):
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.include_router(synthesis_router, prefix="/api/v1")
    active = {
        "user": build_authenticated_user(actors[0]),
        "settings": Settings(database_url=None),
    }

    def database():
        with factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = database
    app.dependency_overrides[require_authenticated_user] = lambda: active["user"]
    app.dependency_overrides[get_settings] = lambda: active["settings"]
    with TestClient(app) as client:
        yield client, active


def synthetic_form():
    from equiped_harness.contracts import (
        CriterionDefinition,
        DomainDefinition,
        EvidenceVerificationConfig,
        FormDefinition,
    )

    return FormDefinition(
        rubric_set_id=uuid4(),
        name="Synthetic historical ITSO",
        agent_id="itso",
        adapter_key="itso",
        adapter_version=2,
        version_number=1,
        domains=(
            DomainDefinition(
                rubric_domain_id=uuid4(),
                code="ITSO",
                title="ITSO",
                display_order=1,
                criteria=tuple(
                    CriterionDefinition(
                        rubric_criterion_id=uuid4(),
                        criterion_code=code,
                        title=code,
                        description=code,
                        display_order=index,
                        strategy_config=EvidenceVerificationConfig(),
                    )
                    for index, code in enumerate(ITSO_CRITERION_IDS)
                ),
            ),
        ),
    )


def seed_historical_assessment(db, doc, owner, source_row):
    job = EvaluationJob(
        document_id=doc.document_id,
        submitted_by=owner.user_id,
        target_agent="itso",
        status="COMPLETED",
        completed_at=datetime.now(UTC),
    )
    db.add(job)
    db.flush()
    form = synthetic_form()
    form_dto = build_evaluation_form_snapshot(job.evaluation_id, form)
    db.add(
        EvaluationRubricProvenance(
            rubric_set_id=form.rubric_set_id,
            agent_id="itso",
            version_number=1,
            name=form.name,
            adapter_key="itso",
            adapter_version=2,
        )
    )
    db.flush()
    db.add(
        EvaluationFormSnapshot(
            snapshot_id=form_dto.snapshot_id,
            evaluation_id=job.evaluation_id,
            agent_id="itso",
            rubric_set_id=form.rubric_set_id,
            adapter_key="itso",
            adapter_version=2,
            snapshot_hash=form_dto.snapshot_hash,
            snapshot_payload=form_dto.snapshot_payload.model_dump(mode="json"),
        )
    )
    profile = Profile()
    policy_hash = digest([])
    effective_policy_hash = attachment_scope_hash(policy_hash, [])
    source = build_source_snapshot(
        str(doc.document_id),
        source_row.canonical_text,
        ((1, 0, len(source_row.canonical_text)),),
        source_row.extractor_version,
        raw_pdf_hash=source_row.source_hash,
    )
    disclosure = {
        "inventory_hash": source_row.inventory_hash,
        "profile": profile.model_dump(mode="json"),
        "actor_id": str(owner.user_id),
        "document_id": str(doc.document_id),
        "source_snapshot_id": str(source_row.snapshot_id),
        "source_hash": source.source_hash,
        "raw_pdf_hash": source.raw_pdf_hash,
        "effective_policy_hash": effective_policy_hash,
        "external_verification": False,
        "references": [],
        "pages": [],
        "policy_versions": [],
        "inventory_count": len(source.references),
        "attachments": [],
    }
    plan = VerificationPlan(
        scope_id="historical-read",
        source_snapshot_hash=source.source_hash,
        disclosure_hash=digest(disclosure),
        profile=profile,
        profile_hash=profile.profile_hash,
    )
    manifest = {
        "plan": plan.model_dump(mode="json"),
        "disclosure": disclosure,
    }
    auth = PreflightAuthorization(
        actor_id=owner.user_id,
        document_id=doc.document_id,
        source_snapshot_id=source_row.snapshot_id,
        source_hash=source.source_hash,
        effective_policy_hash=effective_policy_hash,
        policy_versions=[],
        manifest=manifest,
        manifest_hash=digest(manifest),
        token_hash=hashlib.sha256(uuid4().bytes).hexdigest(),
        reservation=0,
        external_verification=False,
        expires_at=datetime.now(UTC) + timedelta(days=1),
        consumed_evaluation_id=job.evaluation_id,
    )
    db.add(auth)
    db.flush()
    parent = ITSOAssessment(
        evaluation_id=job.evaluation_id,
        document_id=doc.document_id,
        owner_id=owner.user_id,
        source_snapshot_id=source_row.snapshot_id,
        source_hash=source.source_hash,
        form_snapshot_id=form_dto.snapshot_id,
        effective_policy_hash=effective_policy_hash,
        execution_status="COMPLETED",
        scoring_complete=False,
        subtotal=None,
    )
    db.add(parent)
    db.flush()
    start = source.canonical_text.index("Faculty ownership")
    quote = "Faculty ownership instrument"
    span = SourceSpan(
        source_id=str(doc.document_id),
        start_offset=start,
        end_offset=start + len(quote),
        page_number=1,
        text_hash=text_hash(quote),
    )
    fact = EvidenceFact(
        fact_id="historical-source-fact",
        predicate="ownership_context",
        value="Ownership context requires human review",
        authority="proposed_model",
        source_spans=(span,),
        origin="historical_model_output",
    )
    criteria = tuple(
        CriterionAssessment(
            criterion_id=criterion_id,
            applicability="unknown",
            evidence_state=(
                "observed" if criterion_id == "ITSO-01" else "none_supplied_or_located"
            ),
            verification="unverified",
            evidence=(fact,) if criterion_id == "ITSO-01" else (),
            uncertainties=("Requires human review",),
            score_withheld_reason="human_review_required",
        )
        for criterion_id in ITSO_CRITERION_IDS
    )
    result = ITSOAssessmentResult(
        evaluation_id=str(job.evaluation_id),
        document_id=str(doc.document_id),
        source_hash=source.source_hash,
        raw_pdf_hash=source.raw_pdf_hash,
        execution_status="COMPLETED",
        scoring_complete=False,
        criteria=criteria,
    )
    payload = result.model_dump(mode="json", exclude={"generations"})
    parent.result_payload = payload
    db.flush()
    from server.modules.itso_assessments.mechanical_facts import ledger_fingerprint

    verification_hash = ledger_fingerprint(db, parent, source)
    db.add(
        AssessmentEvidence(
            assessment_id=parent.assessment_id,
            payload={
                "result_seal": {
                    "result_hash": digest(payload),
                    "revision": 0,
                    "form_hash": form_dto.snapshot_hash,
                    "source_hash": source.source_hash,
                    "policy_hash": effective_policy_hash,
                    "verification_hash": verification_hash,
                }
            },
        )
    )
    db.flush()
    return job, result
